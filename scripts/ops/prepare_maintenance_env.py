#!/usr/bin/env python3
"""Prepare owner-bound operator inputs; generated data Compose masks them from data containers."""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import quote

from ops import Blocked, ROOT, load, validate_release, validate_target
from prepare_builds import recipe_digest


def private_write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        target = validate_target(load(args.target))
        lock = validate_release()
        manifest = load(ROOT / 'infra/deployment-manifest.yml')
        if args.dry_run:
            print('NOT_EXECUTED: prepare dedicated application keys and masked operator-only inputs')
            return 0
        if lock.get('release', {}).get('recipe_sha256') != recipe_digest():
            raise Blocked('Current build recipe must be published and verified before preparing maintenance')
        owner = manifest['ownership_marker']
        directory = ROOT / '.ops-private/secrets'
        app_file = directory / 'application-keys.json'
        if app_file.exists():
            app = load(app_file)
            if app['owner'] != owner or app_file.stat().st_mode & 0o077:
                raise Blocked('Application key ownership or permissions mismatch')
        else:
            values = {key: secrets.token_hex(32) for key in ('JWT_SECRET_KEY', 'DOORKEEPER_JWT_SECRET_KEY',
                      'EVOAI_CRM_API_TOKEN', 'BOT_RUNTIME_SECRET', 'AUTH_APIKEY_INTEGRATION_LOCAL')}
            values['SECRET_KEY_BASE'] = secrets.token_hex(64)
            values['ENCRYPTION_KEY'] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
            app = {'owner': owner, 'values': values}
            private_write(app_file, app)
        data_file = ROOT / '.ops-private/coolify/data-env.json'
        data = load(data_file)
        if data['owner'] != owner or data['resource_uuid'] != manifest['coolify']['data_uuid']:
            raise Blocked('Data resource ownership mismatch')
        ref = target['supabase']['project_ref_owner_provided']
        password_file = directory / (ref + '-main-migrator.password')
        if password_file.stat().st_mode & 0o077:
            raise Blocked('Migration credential permissions must be 0600')
        password = password_file.read_text()
        connection = target['supabase']['main_connection']
        user = connection['migration_username']
        ops = {'OWNER': owner, 'PROJECT_REF': ref, 'DB_HOST': connection['host'], 'DB_PORT': '5432',
               'DB_NAME': 'postgres', 'DB_USER': user, 'DB_PASSWORD': password,
               'REDIS_HOST': manifest['coolify']['internal_dns']['redis'],
               'REDIS_PASSWORD': data['values']['REDIS_PASSWORD'],
               'CA_BASE64': base64.b64encode((ROOT / 'infra/certs/supabase-root-2021.crt').read_bytes()).decode(),
               **app['values']}
        for service in ('crm', 'auth', 'core', 'processor', 'evoflow'):
            ops[service.upper() + '_IMAGE'] = lock['images'][service]['reference']
        query = 'sslmode=verify-full&sslrootcert=/ops/ca.crt'
        ops['DB_DSN'] = f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{connection['host']}:5432/postgres?{query}"
        for key, value in ops.items():
            if '\n' in value or '\r' in value:
                raise Blocked('Operator environment values must be single-line')
            data['values']['EVO_OPS_' + key] = value
        private_write(data_file, data)
        print('PREPARED: operator inputs in protected file; render/apply per-container masks BEFORE updating Coolify env')
        return 0
    except (Blocked, OSError, KeyError, ValueError) as exc:
        print('BLOCKED: ' + (str(exc) if isinstance(exc, Blocked) else 'maintenance configuration incomplete'), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
