#!/usr/bin/env python3
"""Materialize public Compose configs for Coolify's inline Compose UI.

Optional dedicated credentials are stored only in an owner-bound 0600 local file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
import yaml

from ops import Blocked, ROOT, load, validate_release, validate_target


class Dumper(yaml.SafeDumper):
    pass


def text(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value, style='|' if '\n' in value else None)


Dumper.add_representer(str, text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--prepare-env', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        validate_target(load(args.target))
        lock = validate_release()
        source = ROOT / 'infra/coolify/compose.data.yml'
        compose = yaml.safe_load(source.read_text())
        manifest = load(ROOT / 'infra/deployment-manifest.yml')
        public_values = {'DEPLOYMENT_OWNER': manifest['ownership_marker']}
        for name in ('redis', 'rabbitmq', 'clickhouse'):
            public_values[name.upper() + '_IMAGE'] = lock['images'][name]['reference']
        def materialize(value):
            if isinstance(value, dict):
                return {key: materialize(item) for key, item in value.items()}
            if isinstance(value, list):
                return [materialize(item) for item in value]
            if isinstance(value, str):
                match = re.fullmatch(r'\$\{([A-Z_]+):\?[^}]*\}', value)
                if match and match[1] in public_values:
                    return public_values[match[1]]
            return value
        compose = materialize(compose)
        # Coolify 4.3.18 unconditionally injects env_file: .env into every service.
        # Explicit non-empty masks override env_file for keys this service does not use.
        # Empty strings are unsafe here: this Coolify version replaces them from its DB.
        env_file = ROOT / '.ops-private/coolify/data-env.json'
        global_keys = set(public_values) | {'REDIS_PASSWORD', 'RABBITMQ_PASSWORD', 'RABBITMQ_ERLANG_COOKIE', 'CLICKHOUSE_PASSWORD'}
        if env_file.exists():
            stored = load(env_file)
            if stored.get('owner') != manifest['ownership_marker']:
                raise Blocked('Environment file ownership mismatch')
            global_keys.update(stored['values'])
        for service in compose['services'].values():
            environment = service.setdefault('environment', {})
            used = set(environment)
            for value in environment.values():
                if isinstance(value, str):
                    used.update(re.findall(r'\$\{([A-Z_]+)', value))
            for key in sorted(global_keys - used):
                environment[key] = 'unused-in-this-container'
        for config in compose['configs'].values():
            filename = (source.parent / config.pop('file')).resolve()
            if ROOT / 'infra' not in filename.parents:
                raise Blocked('Configuration path outside infra')
            config['content'] = filename.read_text()
        rendered = yaml.dump(compose, Dumper=Dumper, sort_keys=False)
        digest = hashlib.sha256(rendered.encode()).hexdigest()
        if args.dry_run:
            print(json.dumps({'status': 'NOT_EXECUTED', 'compose_sha256': digest, 'services': list(compose['services'])}))
            return 0
        directory = ROOT / '.ops-private/coolify'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        output = directory / ('data-compose-' + digest + '.yml')
        if output.exists() and output.read_text() != rendered:
            raise Blocked('Existing rendered configuration differs')
        if not output.exists():
            output.write_text(rendered)
        if args.prepare_env:
            manifest = load(ROOT / 'infra/deployment-manifest.yml')
            uuid = manifest['coolify'].get('data_uuid')
            if not uuid:
                raise Blocked('Record the new Coolify resource UUID before preparing credentials')
            secret_file = directory / 'data-env.json'
            if secret_file.exists():
                stored = load(secret_file)
                if stored.get('owner') != manifest['ownership_marker'] or stored.get('resource_uuid') != uuid:
                    raise Blocked('Existing credentials belong to another resource')
                if secret_file.stat().st_mode & 0o077:
                    raise Blocked('Credential file permissions must be 0600')
            else:
                values = {'DEPLOYMENT_OWNER': manifest['ownership_marker']}
                for service in ('redis', 'rabbitmq', 'clickhouse'):
                    values[service.upper() + '_IMAGE'] = lock['images'][service]['reference']
                for name in ('REDIS_PASSWORD', 'RABBITMQ_PASSWORD', 'RABBITMQ_ERLANG_COOKIE', 'CLICKHOUSE_PASSWORD'):
                    values[name] = secrets.token_hex(32)
                fd = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as out:
                    json.dump({'owner': manifest['ownership_marker'], 'resource_uuid': uuid, 'values': values}, out, indent=2)
            print('PREPARED: owner-bound data credentials; values suppressed')
        print(json.dumps({'status': 'RENDERED_NOT_DEPLOYED', 'compose_sha256': digest, 'path': str(output.relative_to(ROOT))}))
        return 0
    except (Blocked, OSError, KeyError, ValueError) as exc:
        print('BLOCKED: ' + (str(exc) if isinstance(exc, Blocked) else 'configuration preparation failed'), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
