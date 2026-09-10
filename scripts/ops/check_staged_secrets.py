#!/usr/bin/env python3
"""Audit staged files without displaying any matching secret value."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    paths = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z', '--diff-filter=ACMRT'], cwd=ROOT).split(b'\0')
    secrets = [p.read_bytes() for p in (ROOT / '.ops-private/secrets').glob('*.password') if p.is_file()]
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
