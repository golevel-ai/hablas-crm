#!/usr/bin/env python3
"""Verify CI image receipts and anonymous GHCR pulls, then record immutable digests.

No registry writes or deployment. --write changes local manifests only.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib import error, parse, request

from ops import Blocked, NoRedirect, ROOT, load, validate_release, validate_target
from prepare_builds import RECIPES, recipe_digest


def get(url, headers=None):
    req = request.Request(url, headers={"User-Agent": "hablas-evo-release-preflight/1.0", **(headers or {})})
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=20) as response:
            data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise Blocked("Registry response exceeds limit")
            return data
    except error.HTTPError as exc:
        raise Blocked("Anonymous GHCR access failed: HTTP " + str(exc.code)) from None
    except (OSError, TimeoutError):
        raise Blocked("Registry unavailable") from None


def verify_public(reference):
    if not re.fullmatch(r"ghcr\.io/golevel-ai/hablas-evo-staging-[a-z]+@sha256:[a-f0-9]{64}", reference):
        raise Blocked("Unexpected registry namespace or mutable reference")
    repository, digest = reference.removeprefix("ghcr.io/").split("@")
    token = json.loads(get("https://ghcr.io/token?" + parse.urlencode(
        {"service": "ghcr.io", "scope": "repository:" + repository + ":pull"})))["token"]
    manifest = get("https://ghcr.io/v2/" + repository + "/manifests/" + digest, {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json",
    })
    if "sha256:" + hashlib.sha256(manifest).hexdigest() != digest:
        raise Blocked("Published image digest differs from CI receipt")
    candidates = [x for x in json.loads(manifest).get("manifests", [])
                  if x.get("platform", {}).get("architecture") == "amd64"
                  and x.get("platform", {}).get("os") == "linux"]
    if len(candidates) != 1:
        raise Blocked("Published image lacks a unique linux/amd64 manifest")


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x") as out:
        json.dump(value, out, indent=2)
        out.write("\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Verify only local artifact identities; no network or writes")
    args = parser.parse_args()
    try:
        validate_target(load(args.target))
        lock = validate_release()
        if not re.fullmatch(r"[a-f0-9]{40}", args.commit) or not args.run_id.isdigit():
            raise Blocked("Invalid CI identity")
        images = {}
        expected_recipe = recipe_digest()
        for filename in args.artifacts.glob("image-*/image-*.json"):
            image = load(filename)
            service = image["service"]
            if service not in RECIPES or service in images:
                raise Blocked("Unexpected or duplicate image receipt")
            expected_source = lock["commit"] if service == "gateway" else lock["submodules"][RECIPES[service][0]]
            if image["source_commit"] != expected_source or image["infrastructure_commit"] != args.commit \
                    or image["recipe_sha256"] != expected_recipe or image["platform"] != "linux/amd64":
                raise Blocked("CI image provenance does not match local release inputs")
            if not image["reference"].startswith("ghcr.io/golevel-ai/hablas-evo-staging-" + service + "@"):
                raise Blocked("Receipt points to another package")
            images[service] = image
        if set(images) != set(RECIPES):
            raise Blocked("Seven application image receipts are required")
        if args.dry_run:
            print("NOT_EXECUTED: seven local receipts match source/recipe; no registry access or writes")
            return 0
        run = json.loads(subprocess.check_output([
            "gh", "run", "view", args.run_id, "--repo", "golevel-ai/hablas-crm", "--json", "status,conclusion,headSha,url"
        ], timeout=30))
        if run["status"] != "completed" or run["conclusion"] != "success" or run["headSha"] != args.commit:
            raise Blocked("CI run did not successfully build this commit")
        for service, image in images.items():
            verify_public(image["reference"])
            image["verification"] = "ANONYMOUS_PULL_AND_DIGEST_VERIFIED"
            print("PASS: " + service + " public linux/amd64 manifest matches CI digest", flush=True)
        for service in ("redis", "rabbitmq", "clickhouse"):
            images[service] = load(ROOT / "infra/build/oci.lock.json")["images"][service]
        if args.write:
            if lock.get("release", {}).get("infrastructure_commit") not in (None, args.commit):
                raise Blocked("Another release is already recorded; preserve it before promotion")
            lock["images"] = images
            lock["image_status"] = "PUBLISHED_APPLICATION_IMAGES_VERIFIED_NOT_DEPLOYED"
            lock["release"] = {"infrastructure_commit": args.commit, "recipe_sha256": expected_recipe,
                               "ci_run_id": args.run_id, "ci_url": run["url"]}
            save(ROOT / "infra/versions.lock.yml", lock)
            manifest_path = ROOT / "infra/deployment-manifest.yml"
            manifest = load(manifest_path)
            manifest["release"] = lock["release"]
            manifest["images"] = {name: image["reference"] for name, image in images.items()}
            save(manifest_path, manifest)
            manifest_path.chmod(0o600)
        return 0
    except (Blocked, OSError, KeyError, ValueError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + (str(exc) if isinstance(exc, Blocked) else "release receipt/configuration error"), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
