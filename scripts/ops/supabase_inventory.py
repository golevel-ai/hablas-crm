#!/usr/bin/env python3
"""Bounded, metadata-only Supabase MCP client using the owner's OpenCode OAuth.

Reads only the exact supabase auth entry for the configured read_only endpoint.
Does not expose tokens, refresh credentials, query application rows or accept SQL.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib import error, parse, request

from ops import Blocked, NoRedirect, ROOT, load, validate_target


class MetadataClient:
    def __init__(self, target, auth_store):
        validate_target(target)
        self.ref = target["supabase"]["project_ref_owner_provided"]
        config = load(ROOT / "opencode.json")["mcp"]["supabase"]
        self.url = config["url"]
        url = parse.urlsplit(self.url)
        query = parse.parse_qs(url.query)
        if (url.scheme, url.netloc, url.path) != ("https", "mcp.supabase.com", "/mcp"):
            raise Blocked("Unexpected Supabase MCP origin")
        if query.get("project_ref") != [self.ref] or query.get("read_only") != ["true"]:
            raise Blocked("MCP must be scoped to the provided project and read_only=true")
        if auth_store.stat().st_mode & 0o077:
            raise Blocked("OAuth store must not be readable by group/others")
        entry = load(auth_store).get("supabase", {})
        if entry.get("serverUrl") != self.url:
            raise Blocked("OAuth credential belongs to another MCP endpoint")
        tokens = entry.get("tokens", {})
        if tokens.get("expiresAt", 0) <= time.time():
            raise Blocked("Supabase OAuth expired; authenticate using the CLI")
        self.token = tokens.get("accessToken")
        if not self.token:
            raise Blocked("Supabase OAuth access token absent")
        self.session = None
        self.sequence = 0
        self.deadline = time.monotonic() + 180
        self.opener = request.build_opener(NoRedirect())

    def rpc(self, method, params=None, notification=False):
        self.sequence += 1
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notification:
            payload["id"] = self.sequence
        headers = {"Authorization": "Bearer " + self.token, "User-Agent": "hablas-evo-inventory/1.0",
                   "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
            headers["MCP-Protocol-Version"] = "2025-03-26"
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Blocked("MCP total timeout reached")
        req = request.Request(self.url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with self.opener.open(req, timeout=min(30, remaining)) as response:
                self.session = response.headers.get("Mcp-Session-Id", self.session)
                raw = response.read(2 * 1024 * 1024 + 1)
                if notification:
                    return None
                if len(raw) > 2 * 1024 * 1024:
                    raise Blocked("MCP metadata response too large")
                if "text/event-stream" in response.headers.get("Content-Type", ""):
                    messages = [json.loads(line[5:].strip()) for line in raw.decode().splitlines()
                                if line.startswith("data:")]
                    data = next((x for x in messages if x.get("id") == self.sequence), {})
                else:
                    data = json.loads(raw)
        except error.HTTPError as exc:
            detail = ""
            try:
                body = json.loads(exc.read(8192))
                detail = str(body.get("message") or body.get("error_description") or body.get("error") or "")
                detail = detail.replace(self.token, "[redacted]")
                detail = re.sub(r"(?:sbp_|sb_secret_)[A-Za-z0-9_-]+", "[redacted]", detail)[:240]
            except (ValueError, AttributeError):
                pass
            raise Blocked("Supabase MCP HTTP " + str(exc.code) + " at " + method + ": " + detail) from None
        except (error.URLError, OSError, ValueError, TimeoutError):
            raise Blocked("Supabase MCP transport/format error (details suppressed)") from None
        if data.get("error") or data.get("id") != self.sequence or "result" not in data:
            raise Blocked("Supabase MCP did not confirm this request")
        return data["result"]

    def call(self, name, arguments):
        if name not in ("get_project_url", "execute_sql"):
            raise Blocked("Only fixed metadata tools are allowed")
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise Blocked("Supabase metadata tool reported an error")
        # Output is only the result of fixed metadata requests below, never app rows.
        return result


METADATA_SQL = """
select json_build_object(
  'database', current_database(),
  'role', current_user,
  'server_version', current_setting('server_version'),
  'vector_available', (select default_version from pg_available_extensions where name='vector'),
  'schema_table_counts', (select json_object_agg(schemaname, total) from
    (select schemaname, count(*) as total from pg_tables group by schemaname) t),
  'extensions', (select json_agg(json_build_object('name', e.extname, 'version', e.extversion,
    'schema', n.nspname)) from pg_extension e join pg_namespace n on n.oid=e.extnamespace),
  'application_schema_tables', (select json_agg(json_build_object('schema', schemaname,
    'table', tablename, 'rls', rowsecurity)) from pg_tables
    where schemaname in ('public', 'evo_crm', 'evoflow', 'hablas_evo_staging')),
  'application_schema_views', (select count(*) from pg_views where schemaname='public'),
  'application_schema_routines', (select count(*) from pg_proc p join pg_namespace n
    on n.oid=p.pronamespace where n.nspname='public')
) as deployment_metadata
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--list-tools", action="store_true", help="Show available names and schemas only")
    parser.add_argument("--dry-run", action="store_true", help="No OAuth access or network requests")
    args = parser.parse_args()
    try:
        target = validate_target(load(args.target))
        if args.dry_run:
            print("NOT_EXECUTED: scoped MCP metadata inventory; no application rows, no writes")
            return 0
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        client = MetadataClient(target, data_home / "opencode/mcp-auth.json")
        client.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                  "clientInfo": {"name": "hablas-evo-metadata", "version": "1.0.0"}})
        client.rpc("notifications/initialized", notification=True)
        tools = client.rpc("tools/list").get("tools", [])
        if args.list_tools:
            print(json.dumps([{"name": t["name"], "arguments": list(t["inputSchema"].get("properties", {}))}
                              for t in tools], indent=2))
            return 0
        names = {t["name"] for t in tools}
        if not {"get_project_url", "execute_sql"}.issubset(names):
            raise Blocked("Expected scoped metadata tools unavailable")
        identity = client.call("get_project_url", {})
        # Ref verified by endpoint scope and project URL before querying metadata.
        if "https://" + client.ref + ".supabase.co" not in json.dumps(identity):
            raise Blocked("Authenticated project URL mismatch")
        metadata = client.call("execute_sql", {"query": METADATA_SQL})
        print(json.dumps({"project_ref": client.ref, "project_url_verified": True,
                          "metadata_tool_result": metadata}, ensure_ascii=False, indent=2))
        return 0
    except Blocked as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError):
        print("BLOCKED: configuration or auth-store shape unavailable; details suppressed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
