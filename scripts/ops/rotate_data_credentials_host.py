#!/usr/bin/env python3
"""Rotate or verify the new data stack credentials without printing values."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

RESOURCE = 'nrvbltvkzmzvivrbkldjok6y'
OWNER = 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9'
DIRECTORY = Path('/data/coolify/services') / RESOURCE
CONTAINERS = {
    'redis': 'hablas-evo-staging-redis-' + RESOURCE,
    'rabbitmq': 'hablas-evo-staging-rabbitmq-' + RESOURCE,
    'clickhouse': 'hablas-evo-staging-clickhouse-' + RESOURCE,
}


def run(argv, operation, **kwargs):
    try:
        return subprocess.run(argv, check=True, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=60, **kwargs)
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError(operation) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-before-restart', action='store_true')
    parser.add_argument('--apply-cookie-before-restart', action='store_true')
    parser.add_argument('--verify-after-restart', action='store_true')
    parser.add_argument('--pending-env', type=Path)
    args = parser.parse_args()
    if sum((args.apply_before_restart, args.apply_cookie_before_restart,
            args.verify_after_restart)) != 1:
        raise RuntimeError('Select exactly one mode')
    if os.geteuid() != 0 or sys.platform != 'linux':
        raise RuntimeError('Approved Linux host required')
    if '51.81.80.55/' not in subprocess.check_output(['ip', '-4', '-o', 'addr', 'show'], text=True):
        raise RuntimeError('Server identity mismatch')
    values = {}
    pending = DIRECTORY / 'ops/pending-data-env.json'
    if args.pending_env:
        if args.verify_after_restart or args.pending_env.resolve() != pending:
            raise RuntimeError('PENDING_PATH')
        info = pending.lstat()
        if not pending.is_file() or pending.is_symlink() or info.st_mode & 0o077:
            raise RuntimeError('PENDING_PERMISSIONS')
        document = json.loads(pending.read_text())
        if document.get('owner') != OWNER or document.get('resource_uuid') != RESOURCE:
            raise RuntimeError('PENDING_IDENTITY')
        values = document['values']
    else:
        for line in (DIRECTORY / '.env').read_text().splitlines():
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                values[key] = value[1:-1] if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"" else value
    required = ('DEPLOYMENT_OWNER', 'REDIS_PASSWORD', 'RABBITMQ_PASSWORD',
                'RABBITMQ_ERLANG_COOKIE', 'CLICKHOUSE_PASSWORD')
    if values.get('DEPLOYMENT_OWNER') != OWNER or any(not values.get(key) for key in required):
        raise RuntimeError('Environment ownership or values mismatch')
    for container in CONTAINERS.values():
        observed = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
        if observed['Config']['Labels'].get('io.golevel.owner') != OWNER or not observed['State']['Running']:
            raise RuntimeError('Container ownership or state mismatch')
    if args.apply_before_restart:
        run(['docker', 'exec', CONTAINERS['rabbitmq'], 'rabbitmqctl', 'change_password',
             'hablas-evo-staging', values['RABBITMQ_PASSWORD']], 'RABBITMQ_PASSWORD_CHANGE')
        clickhouse_verify = '''set -eu
IFS= read -r NEXT
clickhouse-client --user "$CLICKHOUSE_USER" --password "$NEXT" --query 'SELECT 1' | grep -qx 1
'''
        current = subprocess.run(['docker', 'exec', '-i', CONTAINERS['clickhouse'], 'sh', '-ec', clickhouse_verify],
                                 input=values['CLICKHOUSE_PASSWORD'] + '\n', text=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        if current.returncode:
            print('NOTICE: ClickHouse credential will be materialized by the replacement container')
        print('PASS: RabbitMQ live credential rotated; deploy only this Coolify stack next')
        return 0
    if args.apply_cookie_before_restart:
        cookie_change = '''set -eu
IFS= read -r NEXT
umask 077
printf %s "$NEXT" > /var/lib/rabbitmq/.erlang.cookie.next
chown rabbitmq:rabbitmq /var/lib/rabbitmq/.erlang.cookie.next
chmod 400 /var/lib/rabbitmq/.erlang.cookie.next
mv /var/lib/rabbitmq/.erlang.cookie.next /var/lib/rabbitmq/.erlang.cookie
'''
        run(['docker', 'exec', '-u', '0', '-i', CONTAINERS['rabbitmq'], 'sh', '-ec', cookie_change],
            'RABBITMQ_COOKIE_CHANGE', input=values['RABBITMQ_ERLANG_COOKIE'] + '\n', text=True)
        print('PASS: RabbitMQ cookie file rotated atomically; restart only this Coolify stack now')
        return 0
    checks = [
        ('REDIS_CHECK', CONTAINERS['redis'], '''set -eu
IFS= read -r NEXT
REDISCLI_AUTH="$NEXT" redis-cli ping | grep -qx PONG
''', values['REDIS_PASSWORD']),
        ('CLICKHOUSE_CHECK', CONTAINERS['clickhouse'], '''set -eu
IFS= read -r NEXT
clickhouse-client --user "$CLICKHOUSE_USER" --password "$NEXT" --query 'SELECT 1' | grep -qx 1
''', values['CLICKHOUSE_PASSWORD']),
        ('RABBITMQ_PASSWORD_CHECK', CONTAINERS['rabbitmq'], '''set -eu
IFS= read -r NEXT
rabbitmqctl authenticate_user hablas-evo-staging "$NEXT"
''', values['RABBITMQ_PASSWORD']),
        ('RABBITMQ_COOKIE_CHECK', CONTAINERS['rabbitmq'], '''set -eu
IFS= read -r NEXT
test "$(tr -d '\\n' < "$HOME/.erlang.cookie")" = "$NEXT"
''', values['RABBITMQ_ERLANG_COOKIE']),
    ]
    for operation, container, script, value in checks:
        run(['docker', 'exec', '-i', container, 'sh', '-ec', script],
            operation, input=value + '\n', text=True)
    for name, container in CONTAINERS.items():
        observed = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
        environment = dict(item.split('=', 1) for item in observed['Config']['Env'] if '=' in item)
        if observed['HostConfig']['PortBindings']:
            raise RuntimeError('Unexpected published port')
        if any(value != 'unused-in-this-container' for key, value in environment.items() if key.startswith('EVO_OPS_')):
            raise RuntimeError('Operator value reached data container')
        other = set(required) - {'DEPLOYMENT_OWNER'}
        own = {'redis': {'REDIS_PASSWORD'}, 'rabbitmq': {'RABBITMQ_PASSWORD', 'RABBITMQ_ERLANG_COOKIE'},
               'clickhouse': {'CLICKHOUSE_PASSWORD'}}[name]
        for key in other - own:
            if environment.get(key) != 'unused-in-this-container':
                raise RuntimeError('Cross-service credential reached container')
    if pending.exists():
        document = json.loads(pending.read_text())
        if any(values[key] != document['values'][key] for key in required):
            raise RuntimeError('PENDING_NOT_APPLIED')
        pending.unlink()
    print('PASS: rotated data credentials, cookie, health access, masks and private ports verified')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], str) and exc.args[0].replace('_', '').isalnum() else type(exc).__name__
        print('BLOCKED: data credential operation failed (' + code + '); values suppressed', file=sys.stderr)
        sys.exit(2)
