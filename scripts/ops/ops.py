#!/usr/bin/env python3
"""Read-only deployment gates. JSON notation is the supported YAML 1.2 subset.

No provisioning, database connection, migration or DNS write is performed here.
Exit 0: requested local checks passed; 1: failure; 2: blocked/invalid invocation.
"""

import argparse
from datetime import datetime, timedelta, timezone
import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "project": "hablas-evo-infra",
    "environment": "staging",
    "coolify.url": "https://my.golevel.ai/",
    "coolify.server_name": "VPS-US-VA-002-OP",
    "coolify.expected_server_ip": "51.81.80.55",
    "coolify.server_uuid": "hwt9rmdg9rrodfb9hilh8vcn",
    "cloudflare.organization_name": "GoLevel",
    "cloudflare.account_id": "85354ee4fc8d1c079a66f6321a5c78c5",
    "cloudflare.zone_name": "hablas.chat",
    "cloudflare.zone_id": "b0a4153d93f81cd7957e34cdfcd11e60",
    "cloudflare.frontend_customer_host_requested": "crm.hablas.chat",
    "cloudflare.frontend_customer_host_status": "OWNER_RELEASED_DNS_ABSENT_DEPLOYMENT_AUTHORIZED",
    "cloudflare.api_customer_host_requested": "api-crm.hablas.chat",
    "cloudflare.api_customer_host_status": "OWNER_RELEASED_DNS_ABSENT_DEPLOYMENT_AUTHORIZED",
    "cloudflare.availability_method": "AUTHENTICATED_CLOUDFLARE_API_AND_PUBLIC_DNS",
    "cloudflare.host_allocation_status": "AUTHORIZED_PENDING_WRITE",
    "supabase.organization_id": "hnaujighizgevlmtkycw",
    "supabase.project_ref_owner_provided": "znxlfqctnezrropcbftw",
    "supabase.project_name": "hablas-evo-staging",
    "cutover.data_migration": "OWNER_CONFIRMED_FRESH_START",
    "cutover.execution_authorization": "FULL_STAGING_AND_FINAL_DEPLOYMENT_AUTHORIZED",
    "cutover.gate_a_local_status": "LOCAL_VALIDATION_COMPLETE_REMOTE_EXECUTION_AUTHORIZED",
}
SAFETY = {
    "existing_system_must_remain_unchanged": True,
    "allow_existing_dns_update": False,
    "allow_zone_wide_change": False,
    "allow_existing_application_change": False,
    "allow_paid_resource_creation": False,
    "allow_production_cutover": True,
}


class Blocked(Exception):
    pass


def load(path):
    # Reject duplicate keys, rather than silently accepting the final value.
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Blocked("Duplicate configuration key")
            result[key] = value
        return result

    try:
        return json.loads(Path(path).read_text(), object_pairs_hook=unique)
    except (OSError, ValueError):
        raise Blocked("Configuration unreadable; use JSON notation (YAML 1.2 subset)") from None


def field(data, key):
    for part in key.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(part)
    return data


def validate_target(target):
    for key, expected in EXPECTED.items():
        if field(target, key) != expected:
            raise Blocked("Target identity mismatch: " + key)
    for key, expected in SAFETY.items():
        if field(target, "safety." + key) is not expected:
            raise Blocked("Safety policy mismatch: " + key)
    if field(target, "cutover.remote_changes_authorized") is not True:
        raise Blocked("Full staging and final deployment authorization is required")
    try:
        observed_at = datetime.fromisoformat(
            field(target, "cloudflare.availability_observed_at").replace("Z", "+00:00")
        )
    except (AttributeError, ValueError):
        raise Blocked("Cloudflare availability timestamp must be ISO-8601") from None
    if observed_at.tzinfo is None or observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise Blocked("Cloudflare availability timestamp is naive or in the future")
    cf = target["cloudflare"]
    hosts = [cf.get("frontend_candidate"), cf.get("api_candidate")]
    for host in hosts:
        if not isinstance(host, str) or not re.fullmatch(
            r"evo-(?:api-)?stg(?:-[0-9]{2})?\.hablas\.chat", host
        ):
            raise Blocked("Only new staging candidate hostnames are allowed")
    if hosts[0] == hosts[1]:
        raise Blocked("Frontend and API candidates must differ")
    return target


def git(*args, cwd=ROOT):
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, text=True,
            capture_output=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise Blocked("Git identity check failed (details suppressed)") from None


def validate_release():
    lock = load(ROOT / "infra/versions.lock.yml")
    if git("rev-parse", "HEAD") != lock["commit"]:
        # Infrastructure can be committed on top of the locked application tree.
        # It must not silently replace the fork, gateway or submodule revisions.
        git("merge-base", "--is-ancestor", lock["commit"], "HEAD")
        changed = git("diff", "--name-only", lock["commit"], "HEAD").splitlines()
        allowed = ("infra/", "scripts/ops/", "docs/", ".github/workflows/")
        if any(p not in (".gitignore", "opencode.json") and not p.startswith(allowed) for p in changed):
            raise Blocked("Application tree changed relative to the locked fork")
    observed = {}
    for row in git("submodule", "status", "--recursive").splitlines():
        values = row.split()
        revision = values[0]
        if revision.startswith(("-", "+", "U")):
            raise Blocked("Missing or divergent submodule")
        observed[values[1]] = revision
    if observed != lock["submodules"]:
        raise Blocked("Recursive submodule set differs from release lock")
    for path, revision in lock["submodules"].items():
        resolved = (ROOT / path).resolve()
        if ROOT not in resolved.parents:
            raise Blocked("Submodule outside repository")
        if git("rev-parse", "HEAD", cwd=resolved) != revision:
            raise Blocked("Submodule revision differs")
        if git("status", "--porcelain", "--untracked-files=normal", cwd=resolved):
            raise Blocked("Submodule has local changes; preserve and review before release")
    return lock


def preflight(target, stage):
    validate_release()
    if stage == "local":
        return {"status": "PASS", "scope": "local identity and policy checks only"}
    reasons = []
    if target["supabase"]["status"] != "VALIDATED":
        reasons.append("Supabase " + target["supabase"]["status"] + "; no connection or fallback attempted")
    if target["cloudflare"]["host_allocation_status"] != "VALIDATED":
        reasons.append("Domain allocation requires complete authenticated review")
    observed_at = datetime.fromisoformat(
        target["cloudflare"]["availability_observed_at"].replace("Z", "+00:00")
    )
    if datetime.now(timezone.utc) - observed_at.astimezone(timezone.utc) > timedelta(hours=1):
        reasons.append("Cloudflare host inventory is older than one hour")
    if not all(target["cloudflare"].get(k) for k in ("frontend_host", "api_host")):
        reasons.append("Validated hostnames absent")
    # These are known unresolved requirements, not switchable approval booleans.
    reasons.extend([
        "Release images for the current recipe and backend container tests outstanding",
        "Application deploy, restore drill, SMTP and synthetic integrations outstanding",
        "Fresh-start setup and ownership acceptance not executed",
    ])
    raise Blocked("; ".join(reasons))


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a bearer token to a login or another origin.


class Cloudflare:
    def __init__(self, token, timeout=20, total_timeout=300):
        if not token or re.search(r"placeholder|example|changeme|^<", token, re.I):
            raise Blocked("CLOUDFLARE_API_TOKEN absent or placeholder; use approved credential")
        self.token = token
        self.timeout = timeout
        self.deadline = time.monotonic() + total_timeout
        self.opener = request.build_opener(NoRedirect())

    def get(self, path):
        if not path.startswith(("/accounts/", "/zones/")) or ".." in path:
            raise Blocked("Unexpected API path")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Blocked("Inventory total timeout reached")
        req = request.Request(
            "https://api.cloudflare.com/client/v4" + path,
            headers={"Authorization": "Bearer " + self.token, "Accept": "application/json"},
            method="GET",
        )
        try:
            with self.opener.open(req, timeout=min(self.timeout, remaining)) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024:
                    raise Blocked("Inventory response exceeds bounded size")
                data = json.loads(raw)
        except error.HTTPError as exc:
            raise Blocked("Inventory API HTTP " + str(exc.code) + "; visibility incomplete") from None
        except (error.URLError, TimeoutError, ValueError, OSError):
            raise Blocked("Inventory API unavailable or malformed response") from None
        if not isinstance(data, dict) or data.get("success") is not True:
            raise Blocked("Inventory API did not confirm success")
        return data

    def collection(self, path, per_page=50):
        rows = []
        previous = None
        for page in range(1, 101):
            separator = "&" if "?" in path else "?"
            data = self.get(path + separator + parse.urlencode({"page": page, "per_page": per_page}))
            result = data.get("result")
            if not isinstance(result, list):
                raise Blocked("Inventory collection has unexpected shape")
            fingerprint = json.dumps(result, sort_keys=True)
            if result and fingerprint == previous:
                raise Blocked("Inventory pagination repeated a page")
            previous = fingerprint
            rows.extend(result)
            info = data.get("result_info") or {}
            total = info.get("total_count")
            pages = info.get("total_pages")
            if pages is not None and page >= pages:
                if total is not None and len(rows) != total:
                    raise Blocked("Inventory pagination count mismatch")
                return rows
            if total is not None and len(rows) >= total:
                if len(rows) != total:
                    raise Blocked("Inventory pagination overlap")
                return rows
            if not info and len(result) < per_page:
                return rows
            if not result:
                raise Blocked("Inventory pagination ended without proving completeness")
        raise Blocked("Inventory pagination limit reached")


def covers(pattern, host):
    """Conservative hostname matching, including Workers route wildcard syntax."""
    if not isinstance(pattern, str):
        return False
    pattern = pattern.lower().removeprefix("https://").removeprefix("http://")
    pattern = pattern.split("/", 1)[0].rstrip(".")
    return fnmatch.fnmatchcase(host.lower(), pattern)


def inventory_domains(target, client):
    cf = target["cloudflare"]
    a, z = cf["account_id"], cf["zone_id"]
    account = client.get("/accounts/" + a)["result"]
    zone = client.get("/zones/" + z)["result"]
    if (account.get("id"), account.get("name")) != (a, "GoLevel"):
        raise Blocked("Authenticated Cloudflare account mismatch")
    if (zone.get("id"), zone.get("name"), zone.get("account", {}).get("id")) != (z, "hablas.chat", a):
        raise Blocked("Authenticated Cloudflare zone mismatch")
    if zone.get("status") != "active":
        raise Blocked("Zone is not active")
    paths = {
        "dns": f"/zones/{z}/dns_records",
        "routes": f"/zones/{z}/workers/routes",
        "domains": f"/accounts/{a}/workers/domains",
        "workers": f"/accounts/{a}/workers/scripts",
        "pages": f"/accounts/{a}/pages/projects",
        "tunnels": f"/accounts/{a}/cfd_tunnel?is_deleted=false",
        "load_balancers": f"/zones/{z}/load_balancers",
        "zone_rulesets": f"/zones/{z}/rulesets",
        "account_rulesets": f"/accounts/{a}/rulesets",
        "page_rules": f"/zones/{z}/pagerules",
        "access": f"/accounts/{a}/access/apps",
    }
    collections = {key: client.collection(path, 10 if key == "pages" else 50)
                   for key, path in paths.items()}
    candidates = [
        cf["frontend_candidate"],
        cf["api_candidate"],
        cf["frontend_customer_host_requested"],
        cf["api_customer_host_requested"],
    ]
    conflicts = []
    def check(kind, identifier, patterns):
        for host in candidates:
            if any(covers(pattern, host) for pattern in patterns):
                conflicts.append({"kind": kind, "id": identifier, "host": host})

    for kind, prop in (("dns", "name"), ("routes", "pattern"), ("domains", "hostname"),
                       ("load_balancers", "name"), ("access", "domain")):
        for item in collections[kind]:
            patterns = [item.get(prop)]
            if kind == "access":
                patterns += [x.get("uri") for x in item.get("destinations", [])]
            check(kind, item.get("id"), patterns)
    for item in collections["pages"]:
        # List-projects domain field must be visible, not assumed empty.
        if not isinstance(item.get("domains"), list):
            raise Blocked("Pages domain inventory incomplete")
        check("pages", item.get("id"), item["domains"])
    for item in collections["tunnels"]:
        if item.get("config_src") != "cloudflare":
            raise Blocked("Locally managed Tunnel requires host configuration inventory")
        config = client.get(f"/accounts/{a}/cfd_tunnel/{item['id']}/configurations")["result"]
        ingress = field(config, "config.ingress")
        if not isinstance(ingress, list):
            raise Blocked("Tunnel ingress inventory incomplete")
        check("tunnel", item["id"], [x.get("hostname") for x in ingress])
    rule_counts = {}
    for scope, identifier in (("zone", z), ("account", a)):
        for item in collections[scope + "_rulesets"]:
            detail = client.get(f"/{scope}s/{identifier}/rulesets/{item['id']}")["result"]
            if not isinstance(detail.get("rules"), list):
                raise Blocked("Ruleset details incomplete")
            rule_counts[item["id"]] = len(detail["rules"])
    reserved_worker_names = {"hablas-evo-frontend-staging", "hablas-evo-frontend-production"}
    worker_name_collisions = sorted(
        x.get("id") for x in collections["workers"] if x.get("id") in reserved_worker_names
    )
    worker_collision = bool(worker_name_collisions)
    ssl = client.get(f"/zones/{z}/settings/ssl")["result"].get("value")
    # Expressions/lists/managed rules, Coolify and parent cookies need review.
    # No rule-expression evaluator can safely treat mere absence of a substring as clearance.
    return {
        "status": "BLOCKED" if conflicts or worker_collision else "REVIEW_REQUIRED",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "account_id": a, "zone_id": z, "candidates": candidates,
        "counts": {key: len(value) for key, value in collections.items()},
        "ruleset_rule_counts": rule_counts, "conflicts": conflicts,
        "worker_name_collision": worker_collision,
        "worker_name_collisions": worker_name_collisions,
        "zone_ssl_mode": ssl,
        "remaining": ["Review rule expressions and referenced lists securely",
                      "Complete Coolify/proxy domain inventory and parent-cookie audit",
                      "Validate hostname-only TLS and staging Access",
                      "Revalidate immediately before writing; this report does not allocate hosts"],
    }


def domain_report(result):
    return "\n".join([
        "# Alocação de domínios — " + result["status"], "",
        "Owner: hablas-evo-infra / staging", "",
        "Inventário GET sanitizado; não autoriza publicação.", "",
        "```json", json.dumps(result, ensure_ascii=False, indent=2), "```", "",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("validate", "preflight", "preflight-domain"))
    parser.add_argument("--target", required=True, type=Path, help="Explicit environment.target.yml")
    parser.add_argument("--stage", choices=("local", "remote"), default="local")
    parser.add_argument("--timeout", type=int, default=20, help="Per-request API timeout, 1–60 seconds")
    parser.add_argument("--report", type=Path, help="Create a NEW sanitized domain Markdown report; never overwrite")
    parser.add_argument("--dry-run", action="store_true", help="Validate locally; no API calls or report writes")
    args = parser.parse_args()
    try:
        if not 1 <= args.timeout <= 60:
            raise Blocked("Timeout must be between 1 and 60 seconds")
        target = validate_target(load(args.target))
        if args.operation in ("validate", "preflight"):
            result = preflight(target, args.stage)
            print(json.dumps(result))
            return 0
        if args.dry_run:
            print(json.dumps({"status": "NOT_EXECUTED", "scope": "domain GET plan only",
                              "account_id": target["cloudflare"]["account_id"],
                              "zone_id": target["cloudflare"]["zone_id"]}))
            return 0
        client = Cloudflare(os.environ.get("CLOUDFLARE_API_TOKEN"), args.timeout)
        result = inventory_domains(target, client)
        if args.report:
            # Exclusive creation preserves the reviewed baseline and previous reports.
            fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as out:
                out.write(domain_report(result))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2  # Inventory completed does not mean publication is cleared.
    except Blocked as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2
    except (KeyError, TypeError, OSError, ValueError):
        print("FAIL: Invalid configuration, API shape or output path; details suppressed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
