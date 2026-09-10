"""Safety regressions: wrong destination, hidden conflicts, missing visibility.

No requests are sent and no database or remote infrastructure is created.
Run: python3 -m unittest discover -s scripts/ops -p 'test_*.py' -v
"""

import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import ops


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.target = ops.load(ops.ROOT / "infra/environment.target.yml")

    def test_wrong_server_account_and_zone_fail(self):
        for group, key in (("coolify", "server_uuid"), ("coolify", "expected_server_ip"),
                           ("cloudflare", "account_id"), ("cloudflare", "zone_id")):
            with self.subTest(key=key):
                target = copy.deepcopy(self.target)
                target[group][key] = "wrong-destination"
                with self.assertRaises(ops.Blocked):
                    ops.validate_target(target)

    def test_wrong_supabase_project_fails(self):
        for key in ("organization_id", "project_ref_owner_provided", "project_name"):
            with self.subTest(key=key):
                target = copy.deepcopy(self.target)
                target["supabase"][key] = "wrong-destination"
                with self.assertRaises(ops.Blocked):
                    ops.validate_target(target)

    def test_cannot_relax_safety_with_truthy_strings(self):
        for value in (True, "false", 0, None):
            target = copy.deepcopy(self.target)
            target["safety"]["allow_existing_dns_update"] = value
            with self.assertRaises(ops.Blocked):
                ops.validate_target(target)

    def test_apex_existing_and_wildcard_hosts_rejected(self):
        for host in ("hablas.chat", "www.hablas.chat", "evo.hablas.chat",
                     "*.hablas.chat", "evo-stg.hablas.chat.evil.test"):
            target = copy.deepcopy(self.target)
            target["cloudflare"]["frontend_candidate"] = host
            with self.assertRaises(ops.Blocked):
                ops.validate_target(target)

    def test_supabase_pending_stops_remote_before_any_api_call(self):
        self.target["supabase"]["status"] = "PENDING_OWNER_INPUT"
        with patch.object(ops, "validate_release", return_value={}), \
             patch.object(ops.Cloudflare, "get", side_effect=AssertionError("network forbidden")):
            with self.assertRaisesRegex(ops.Blocked, "Supabase PENDING_OWNER_INPUT"):
                ops.preflight(self.target, "remote")

    def test_no_database_fallback_even_if_hostnames_are_set(self):
        target = copy.deepcopy(self.target)
        target["supabase"]["status"] = "PENDING_OWNER_INPUT"
        target["cloudflare"].update(host_allocation_status="VALIDATED",
                                    frontend_host="evo-stg.hablas.chat",
                                    api_host="evo-api-stg.hablas.chat")
        with patch.object(ops, "validate_release", return_value={}):
            with self.assertRaisesRegex(ops.Blocked, "no connection or fallback attempted"):
                ops.preflight(target, "remote")

    def test_cli_requires_explicit_target(self):
        result = subprocess.run(["python3", str(Path(ops.__file__)), "preflight"],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)


class InventoryTests(unittest.TestCase):
    def client(self):
        return ops.Cloudflare("synthetic-test-credential-never-sent")

    def test_reads_conflict_on_second_page(self):
        client = self.client()
        pages = [
            {"result": [{"name": "unrelated.test"}],
             "result_info": {"page": 1, "total_pages": 2, "total_count": 2}},
            {"result": [{"name": "evo-stg.hablas.chat"}],
             "result_info": {"page": 2, "total_pages": 2, "total_count": 2}},
        ]
        with patch.object(client, "get", side_effect=pages) as get:
            result = client.collection("/zones/test/dns_records", per_page=1)
        self.assertEqual(get.call_count, 2)
        self.assertTrue(any(ops.covers(x["name"], "evo-stg.hablas.chat") for x in result))

    def test_repeating_pagination_is_not_complete_inventory(self):
        client = self.client()
        page = {"result": [{"id": "same"}], "result_info": {"total_count": 3}}
        with patch.object(client, "get", return_value=page):
            with self.assertRaisesRegex(ops.Blocked, "repeated"):
                client.collection("/zones/test/dns_records", per_page=1)

    def test_partial_page_count_fails(self):
        client = self.client()
        with patch.object(client, "get", return_value={
            "result": [], "result_info": {"total_pages": 1, "total_count": 10}
        }):
            with self.assertRaisesRegex(ops.Blocked, "mismatch"):
                client.collection("/zones/test/dns_records")

    def test_missing_permissions_are_never_empty_list(self):
        client = self.client()
        with patch.object(client, "get", side_effect=ops.Blocked("Inventory API HTTP 403")):
            with self.assertRaisesRegex(ops.Blocked, "403"):
                client.collection("/zones/test/workers/routes")

    def test_parent_wildcards_and_routes_cover_candidate(self):
        for pattern in ("*.hablas.chat", "*hablas.chat/*", "https://*.hablas.chat/private/*"):
            self.assertTrue(ops.covers(pattern, "evo-stg.hablas.chat"))
        self.assertFalse(ops.covers("hablas.chat/*", "evo-stg.hablas.chat"))
        self.assertFalse(ops.covers("www.hablas.chat/*", "evo-stg.hablas.chat"))

    def test_no_token_never_attempts_request(self):
        with patch.object(ops.request, "build_opener", side_effect=AssertionError("network forbidden")):
            with self.assertRaises(ops.Blocked):
                ops.Cloudflare(None)

    def test_account_mismatch_blocks_before_resource_inventory(self):
        target = ops.load(ops.ROOT / "infra/environment.target.yml")
        client = self.client()
        with patch.object(client, "get", side_effect=[
            {"result": {"id": target["cloudflare"]["account_id"], "name": "Other"}},
            {"result": {}},
        ]), patch.object(client, "collection", side_effect=AssertionError("wrong account")):
            with self.assertRaisesRegex(ops.Blocked, "account mismatch"):
                ops.inventory_domains(target, client)


if __name__ == "__main__":
    unittest.main()
