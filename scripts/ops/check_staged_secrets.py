#!/usr/bin/env python3
"""Audit staged files without displaying any matching secret value."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    paths = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z', '--diff-filter=ACMRT'], cwd=ROOT).split(b'\0')
    secrets = [p.read_bytes() for p in (ROOT / '.ops-private/secrets').glob('*.password') if p.is_file()]
    sensitive_key = re.compile(r'PASSWORD|SECRET|TOKEN|ENCRYPTION_KEY|COOKIE|CA_BASE64|DB_DSN|ACCESS_KEY_ID')
    for private in list((ROOT / '.ops-private/secrets').glob('*.json')) + [ROOT / '.ops-private/coolify/data-env.json']:
        if not private.is_file():
            continue
        def collect(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if sensitive_key.search(key.upper()) and isinstance(child, str) and child:
                        secrets.append(child.encode())
                    else:
                        collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
        collect(json.loads(private.read_text()))
    patterns = [rb'sb_secret_[A-Za-z0-9_-]{20,}', rb'gh[pousr]_[A-Za-z0-9]{25,}',
                rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
    failures = []
    checked = 0
    for raw in paths:
        if not raw:
            continue
        name = raw.decode()
        checked += 1
        if name.startswith(('.ops-private/', '.playwright-mcp/')) or name == 'infra/deployment-manifest.yml':
            failures.append(name)
            continue
        index_entry = subprocess.check_output(['git', 'ls-files', '--stage', '--', name], cwd=ROOT).split()
        if index_entry and index_entry[0] == b'160000':
            continue
        data = subprocess.check_output(['git', 'show', ':' + name], cwd=ROOT)
        if any(secret and secret in data for secret in secrets) or any(re.search(pattern, data) for pattern in patterns):
            failures.append(name)
    if failures:
        print('BLOCKED: sensitive content or private evidence detected in staged paths: ' + ', '.join(failures))
        return 2
    print(f'PASS: {checked} staged files checked; no collected password, API secret or private key detected')
    return 0


if __name__ == '__main__':
    sys.exit(main())
