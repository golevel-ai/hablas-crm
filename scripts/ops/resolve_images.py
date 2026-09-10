#!/usr/bin/env python3
"""Resolve explicit OCI tags to verified linux/amd64 manifests; no image pulls/deploys.

The optional --write creates infra/build/oci.lock.json exclusively, never upserts it.
Registry bearer tokens are anonymous, short-lived and remain only in memory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib import error, parse, request

from ops import Blocked, NoRedirect, ROOT, load, validate_target

IMAGES = {
    "auth_base": "library/ruby:3.4.4-slim",
    "crm_node": "library/node:23-alpine",
    "crm_ruby": "library/ruby:3.4.4-alpine3.21",
    "core_go": "library/golang:1.24.4-alpine",
    "alpine": "library/alpine:3.20",
    "processor_python": "library/python:3.11-slim",
    "bot_go": "library/golang:1.24-alpine",
    "flow_node": "library/node:20-slim",
    "gateway_nginx": "library/nginx:1.28-alpine",
    "redis": "library/redis:7.4-alpine",
    "rabbitmq": "library/rabbitmq:3.13-alpine",
    "clickhouse": "clickhouse/clickhouse-server:25.8-alpine",
}
ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json", "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])


def get(url, headers=None):
    req = request.Request(url, headers={"User-Agent": "hablas-evo-image-lock/1.0", **(headers or {})})
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=30) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise Blocked("Registry response too large")
            return raw, response.headers
    except error.HTTPError as exc:
        raise Blocked("Registry HTTP " + str(exc.code)) from None
    except (OSError, TimeoutError):
        raise Blocked("Registry unavailable") from None


def resolve(tag):
    repository, version = tag.rsplit(":", 1)
    auth, _ = get("https://auth.docker.io/token?" + parse.urlencode(
        {"service": "registry.docker.io", "scope": "repository:" + repository + ":pull"}))
    token = json.loads(auth)["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": ACCEPT}
    raw, _ = get("https://registry-1.docker.io/v2/" + repository + "/manifests/" + version, headers)
    index = json.loads(raw)
    candidates = [item for item in index.get("manifests", [])
                  if item.get("platform", {}).get("os") == "linux"
                  and item.get("platform", {}).get("architecture") == "amd64"]
    if len(candidates) != 1:
        raise Blocked("Registry did not provide one linux/amd64 platform manifest")
    digest = candidates[0]["digest"]
    manifest, _ = get("https://registry-1.docker.io/v2/" + repository + "/manifests/" + digest, headers)
    if "sha256:" + hashlib.sha256(manifest).hexdigest() != digest:
        raise Blocked("Registry manifest digest mismatch")
    return {"source_tag": tag, "platform": "linux/amd64",
            "reference": "docker.io/" + repository + "@" + digest,
            "manifest_digest": digest, "status": "MANIFEST_VERIFIED_NOT_RUNTIME_TESTED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        validate_target(load(args.target))
        if args.dry_run:
            print(json.dumps({"status": "NOT_EXECUTED", "tags": IMAGES}, indent=2))
            return 0
        resolved = {}
        for name, tag in IMAGES.items():
            resolved[name] = resolve(tag)
            print(name + ": " + resolved[name]["reference"], flush=True)
        if args.write:
            with (ROOT / "infra/build/oci.lock.json").open("x") as out:
                json.dump({"schema_version": 1, "images": resolved}, out, indent=2)
                out.write("\n")
        return 0
    except (Blocked, OSError, KeyError, ValueError) as exc:
        print("BLOCKED: " + (str(exc) if isinstance(exc, Blocked) else "image lock incomplete or already exists"), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
