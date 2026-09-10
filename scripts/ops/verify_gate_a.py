#!/usr/bin/env python3
"""Verify security-critical Gate A transformations in generated build contexts."""

import argparse
from pathlib import Path
import re
import sys


def require(path, text):
    content = path.read_text()
    if text not in content:
        raise ValueError(f"required Gate A contract missing from {path.name}")
    return content


def has_broad_auth_location(content):
    return re.search(
        r"^\s*location\s+(?:(?:=|\^~|~\*?)\s+)?(?:\^)?/auth(?:[/\s({$]|\\)",
        content,
        re.MULTILINE,
    ) is not None


def compose_forces_ssl(compose):
    values = re.findall(r"^\s*FORCE_SSL\s*:\s*([^\s#]+)", compose, re.MULTILINE)
    return values == ['"true"']


def production_enforces_ssl(content):
    return all(text in content for text in (
        "ssl_enforced = ActiveModel::Type::Boolean.new.cast(ENV.fetch('FORCE_SSL', 'true'))",
        "config.assume_ssl = ssl_enforced",
        "config.force_ssl = ssl_enforced",
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-root", type=Path, required=True)
    parser.add_argument("--compose", type=Path, required=True)
    args = parser.parse_args()

    auth = args.context_root / "auth"
    gateway = args.context_root / "gateway"
    try:
        production = require(
            auth / "config/environments/production.rb",
            "ENV.fetch('ACTIVE_STORAGE_SERVICE') { GlobalConfigService.load('ACTIVE_STORAGE_SERVICE', 'local') }",
        )
        dynamic = require(
            auth / "config/initializers/active_storage_dynamic_service.rb",
            "service_name = ENV.fetch('ACTIVE_STORAGE_SERVICE') {",
        )
        if not production_enforces_ssl(production):
            raise ValueError("Auth production SSL switch no longer fails closed")
        require(
            auth / "config/initializers/doorkeeper.rb",
            "force_ssl_in_redirect_uri ActiveModel::Type::Boolean.new.cast(ENV.fetch('FORCE_SSL', Rails.env.production?.to_s))",
        )
        storage = auth / "config/storage.yml"
        storage_text = storage.read_text()
        for key in (
            "STORAGE_ACCESS_KEY_ID",
            "STORAGE_SECRET_ACCESS_KEY",
            "STORAGE_REGION",
            "STORAGE_BUCKET_NAME",
            "STORAGE_ENDPOINT",
        ):
            if not re.search(
                rf"ENV\.fetch\('{key}'(?:, 'auto')?\) if "
                r"ENV\.fetch\('ACTIVE_STORAGE_SERVICE', 'local'\) == 's3_compatible'",
                storage_text,
            ):
                raise ValueError(f"conditional environment storage contract missing for {key}")
        gateway_config = (gateway / "default.conf.template").read_text()
        require(gateway / "default.conf.template", "location ~ ^/api/v1/campaigns(?:/|$)")
        require(gateway / "default.conf.template", "proxy_set_header X-Forwarded-Proto https;")
        require(gateway / "00-cors.conf.template", '"${FRONTEND_ORIGIN}" $http_origin;')
        compose = args.compose.read_text()

        forbidden = "GlobalConfigService.load('ACTIVE_STORAGE_SERVICE', ENV.fetch('ACTIVE_STORAGE_SERVICE', 'local'))"
        if forbidden in production or forbidden in dynamic:
            raise ValueError("database storage setting still overrides the deployment environment")
        if "GlobalConfigService.load('STORAGE_" in storage_text:
            raise ValueError("database values still override deployment R2 settings")
        if has_broad_auth_location(gateway_config):
            raise ValueError("unsafe broad Devise route must not be exposed")
        if not compose_forces_ssl(compose):
            raise ValueError("Auth FORCE_SSL must be explicitly true exactly once")
        if '"X-Forwarded-Proto: https"' not in compose:
            raise ValueError("Auth HTTP health check must declare external HTTPS")
    except (OSError, ValueError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2

    print("PASS: Gate A Auth HTTPS/storage and gateway routing contracts verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
