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
import import_release
import verify_gate_a


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

    def test_remote_cutover_authorization_is_enforced(self):
        for value in (False, "true", 1, None):
            target = copy.deepcopy(self.target)
            target["cutover"]["remote_changes_authorized"] = value
            with self.assertRaises(ops.Blocked):
                ops.validate_target(target)

    def test_cloudflare_evidence_metadata_is_enforced(self):
        for key in (
            "frontend_customer_host_status",
            "api_customer_host_status",
            "availability_method",
            "host_allocation_status",
        ):
            with self.subTest(key=key):
                target = copy.deepcopy(self.target)
                target["cloudflare"][key] = "wrong-state"
                with self.assertRaises(ops.Blocked):
                    ops.validate_target(target)

        for value in (None, "not-a-time", "2999-01-01T00:00:00Z"):
            with self.subTest(timestamp=value):
                target = copy.deepcopy(self.target)
                target["cloudflare"]["availability_observed_at"] = value
                with self.assertRaises(ops.Blocked):
                    ops.validate_target(target)

    def test_apex_existing_and_wildcard_hosts_rejected(self):
        for host in ("hablas.chat", "www.hablas.chat", "evo.hablas.chat",
                     "*.hablas.chat", "crm.hablas.chat.evil.test",
                     "evo-stg.hablas.chat"):
            target = copy.deepcopy(self.target)
            target["cloudflare"]["frontend_candidate"] = host
            with self.assertRaises(ops.Blocked):
                ops.validate_target(target)

    def test_candidates_must_match_the_approved_customer_hosts(self):
        target = copy.deepcopy(self.target)
        target["cloudflare"]["api_candidate"] = target["cloudflare"]["frontend_candidate"]
        with self.assertRaises(ops.Blocked):
            ops.validate_target(target)

    def test_retired_staging_hosts_stay_recorded_and_separate(self):
        for value in (None, [], ["crm.hablas.chat"], ["evo.hablas.chat"]):
            with self.subTest(retired=value):
                target = copy.deepcopy(self.target)
                target["cloudflare"]["retired_hosts"] = value
                with self.assertRaises(ops.Blocked):
                    ops.validate_target(target)

    def test_tunnel_policy_is_enforced(self):
        for key, value in (
            ("mode", "DIRECT_ORIGIN"),
            ("name", "hablas-evo-staging"),
            ("ingress_target", "http://51.81.80.55:80"),
            ("ingress_target", "https://hablas-evo-production-gateway:80"),
            ("replicas", 1),
            ("replicas", "2"),
        ):
            with self.subTest(key=key, value=value):
                target = copy.deepcopy(self.target)
                target["cloudflare"]["tunnel"][key] = value
                with self.assertRaises(ops.Blocked):
                    ops.validate_target(target)

    def test_tunnel_block_is_required(self):
        target = copy.deepcopy(self.target)
        target["cloudflare"].pop("tunnel")
        with self.assertRaises(ops.Blocked):
            ops.validate_target(target)

    def test_origin_ports_cannot_be_closed_before_the_tunnel_exists(self):
        target = copy.deepcopy(self.target)
        target["cloudflare"]["tunnel"]["origin_ports_closed"] = True
        with self.assertRaises(ops.Blocked):
            ops.validate_target(target)

    def test_pre_rename_images_block_remote_deployment(self):
        for service in ("auth", "crm", "core", "processor", "gateway", "bot", "evoflow"):
            lock = ops.load(ops.ROOT / "infra/versions.lock.yml")
            image = lock["images"][service]
            image["reference"] = f"ghcr.io/golevel-ai/hablas-evo-staging-{service}@sha256:{'0' * 64}"
            image["verification"] = "PENDING_PRODUCTION_REBUILD"
            with patch.object(ops, "load", return_value=lock):
                reasons = ops.unverified_production_images()
            with self.subTest(service=service):
                self.assertTrue(any(r.startswith(service + " ") for r in reasons))

    def test_verified_production_images_clear_the_block(self):
        lock = ops.load(ops.ROOT / "infra/versions.lock.yml")
        digest = "@sha256:" + "0" * 64
        for service in ("auth", "crm", "core", "processor", "gateway", "bot", "evoflow"):
            image = lock["images"][service]
            image["reference"] = f"ghcr.io/golevel-ai/hablas-evo-production-{service}{digest}"
            image["verification"] = "ANONYMOUS_PULL_AND_DIGEST_VERIFIED"
        with patch.object(ops, "load", return_value=lock):
            self.assertEqual(ops.unverified_production_images(), [])

    def test_unverified_digest_under_the_right_package_still_blocks(self):
        lock = ops.load(ops.ROOT / "infra/versions.lock.yml")
        digest = "@sha256:" + "0" * 64
        for service in ("auth", "crm", "core", "processor", "gateway", "bot", "evoflow"):
            image = lock["images"][service]
            image["reference"] = f"ghcr.io/golevel-ai/hablas-evo-production-{service}{digest}"
            image["verification"] = "PENDING_PRODUCTION_REBUILD"
        with patch.object(ops, "load", return_value=lock):
            reasons = ops.unverified_production_images()
        self.assertTrue(all("not verified after the rename" in r for r in reasons))
        self.assertEqual(len(reasons), 7)

    def test_release_import_preserves_independent_image_pins(self):
        lock = ops.load(ops.ROOT / "infra/versions.lock.yml")
        images = {service: {} for service in import_release.RECIPES}
        import_release.preserve_independent_images(lock["images"], images)
        self.assertEqual(images["evolution_go"], lock["images"]["evolution_go"])

    def test_release_import_keeps_existing_application_pending_rollout(self):
        self.assertEqual(
            import_release.image_status(True),
            "PUBLISHED_APPLICATION_IMAGES_VERIFIED_PENDING_ROLLOUT",
        )

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

    def test_gate_a_rejects_equivalent_broad_auth_locations(self):
        for location in (
            "location /auth {",
            "location ^~ /auth/ {",
            "location ~ ^/auth(?:/|$) {",
            "location ~* ^/auth/ {",
        ):
            with self.subTest(location=location):
                self.assertTrue(verify_gate_a.has_broad_auth_location(location))
        self.assertFalse(verify_gate_a.has_broad_auth_location(
            "location ~ ^/api/v1/auth(?:/|$) {"
        ))

    def test_gate_a_requires_one_explicit_true_force_ssl(self):
        self.assertTrue(verify_gate_a.compose_forces_ssl('  FORCE_SSL: "true"\n'))
        for value in ('false', '"false"', '0', 'off', '${FORCE_SSL:-false}', ''):
            with self.subTest(value=value):
                self.assertFalse(verify_gate_a.compose_forces_ssl(
                    f"  FORCE_SSL: {value}\n"
                ))

    def test_gate_a_requires_fail_closed_rails_ssl_assignment(self):
        secure = "\n".join((
            "ssl_enforced = ActiveModel::Type::Boolean.new.cast(ENV.fetch('FORCE_SSL', 'true'))",
            "config.assume_ssl = ssl_enforced",
            "config.force_ssl = ssl_enforced",
        ))
        self.assertTrue(verify_gate_a.production_enforces_ssl(secure))
        self.assertFalse(verify_gate_a.production_enforces_ssl(
            secure.replace(
                "ssl_enforced = ActiveModel::Type::Boolean.new.cast(ENV.fetch('FORCE_SSL', 'true'))",
                "ssl_enforced = false",
            )
        ))

    def test_ci_remote_writes_are_policy_gated(self):
        workflow = (ops.ROOT / ".github/workflows/build-production.yml").read_text()
        self.assertIn("- infra/environment.target.yml", workflow)
        self.assertIn("remote_writes_authorized={'true' if remote_writes_authorized else 'false'}", workflow)
        self.assertIn("if: steps.plan.outputs.remote_writes_authorized == 'true'", workflow)
        self.assertIn(
            "if: needs.verify.outputs.remote_writes_authorized == 'true' && "
            "needs.verify.outputs.build_images == 'true'",
            workflow,
        )

    def test_ci_publishes_only_production_images_and_origins(self):
        workflow = (ops.ROOT / ".github/workflows/build-production.yml").read_text()
        self.assertNotIn("hablas-evo-staging-", workflow)
        self.assertNotIn("evo-api-stg.hablas.chat", workflow)
        self.assertIn("ghcr.io/golevel-ai/hablas-evo-production-", workflow)
        self.assertIn("VITE_API_URL: https://api-crm.hablas.chat", workflow)
        self.assertIn("VITE_APP_ENV: production", workflow)

    def test_compose_files_carry_no_staging_identifiers(self):
        for name in ("compose.app.yml", "compose.data.yml"):
            with self.subTest(compose=name):
                text = (ops.ROOT / "infra/coolify" / name).read_text()
                body = "\n".join(
                    line for line in text.splitlines() if not line.lstrip().startswith("#")
                )
                self.assertNotIn("staging", body)
                self.assertNotIn("_stg_", body)


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

    def test_inventory_includes_final_customer_hosts(self):
        target = ops.load(ops.ROOT / "infra/environment.target.yml")
        account_id = target["cloudflare"]["account_id"]
        zone_id = target["cloudflare"]["zone_id"]
        client = self.client()

        def collection(path, _per_page):
            if path.endswith("/dns_records"):
                return [{"id": "final-api-record", "name": "api-crm.hablas.chat"}]
            if path.endswith("/workers/scripts"):
                return [{"id": "hablas-evo-frontend-production"}]
            return []

        with patch.object(client, "get", side_effect=[
            {"result": {"id": account_id, "name": "GoLevel"}},
            {"result": {"id": zone_id, "name": "hablas.chat",
                        "account": {"id": account_id}, "status": "active"}},
            {"result": {"value": "full"}},
        ]), patch.object(client, "collection", side_effect=collection):
            result = ops.inventory_domains(target, client)

        self.assertIn({"kind": "dns", "id": "final-api-record",
                       "host": "api-crm.hablas.chat"}, result["conflicts"])
        self.assertTrue(result["worker_name_collision"])
        self.assertEqual(result["worker_name_collisions"], ["hablas-evo-frontend-production"])


if __name__ == "__main__":
    unittest.main()
