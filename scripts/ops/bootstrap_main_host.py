#!/usr/bin/env python3
"""Run the locked primary bootstrap on the approved host, using temporary containers.

Coolify remains the workload controller. These are one-shot maintenance processes,
with a host flock and a live PostgreSQL advisory-lock keeper. No docker compose up.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import select
import stat
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qsl, quote, unquote, urlsplit

RESOURCE = 'nrvbltvkzmzvivrbkldjok6y'
OWNER = 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9'
DIRECTORY = Path('/data/coolify/services') / RESOURCE
STAGE = 'START'
SCRIPT_SHA256 = {
    'database_lock.cjs': '2d390a8ee0173efda750a6fbf696db04e9bfea3faed19fe734586120e8aa1051',
    'bootstrap_crm.rb': '1705476477b19d45244cdf1fee3965bb7b0d998a69f22a7ccebf08b95e66a7ed',
    'bootstrap_processor_alembic.py': 'a2441bc7465822686af0958e6bc9a4d9c51e3c07bc13ca0fe8f9433fdfb5e786',
    'bootstrap_processor.py': '690d3f5d687b13e31774ea579a49f49ef808232db95ddd05bfb35a0a59de22b6',
    'grant_main_runtime.cjs': '690c52272b832b69e5cfece7efad6d4e696c892b5ac496b211d493753d59ed6a',
    'verify_main_completion.cjs': '13d6451b3815a901929410f785994a5c69c17ff2d9d1525cea16f4b4cd0b93a5',
}


def main():
    global STAGE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scripts', type=Path, required=True, help='Directory of reviewed public operation scripts')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.dry_run:
        print('NOT_EXECUTED: host flock + DB lock; CRM schema, Auth migrations, Core, Processor, seeds and grants')
        return 0
    STAGE = 'HOST_IDENTITY'
    if os.geteuid() != 0 or sys.platform != 'linux':
        raise RuntimeError('Approved Linux host and privileged maintenance access required')
    addresses = subprocess.check_output(['ip', '-4', '-o', 'addr', 'show'], text=True)
    if '51.81.80.55/' not in addresses:
        raise RuntimeError('Server identity mismatch')
    STAGE = 'ENVIRONMENT_READ'
    variables = {}
    for line in (DIRECTORY / '.env').read_text().splitlines():
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        variables[key] = value
    ops = {key.removeprefix('EVO_OPS_'): value for key, value in variables.items() if key.startswith('EVO_OPS_')}
    STAGE = 'OPERATOR_IDENTITY'
    if ops.get('OWNER') != OWNER or ops.get('PROJECT_REF') != 'znxlfqctnezrropcbftw':
        raise RuntimeError('Operator credential ownership mismatch')
    if ops.get('DB_USER') != 'hablas_evo_prod_main_migrator.znxlfqctnezrropcbftw':
        raise RuntimeError('Use the dedicated migration role')
    dsn = urlsplit(ops.get('DB_DSN', ''))
    query = dict(parse_qsl(dsn.query, keep_blank_values=True))
    if (dsn.scheme != 'postgresql' or dsn.hostname != ops.get('DB_HOST') or dsn.port != 5432
            or dsn.path != '/postgres' or unquote(dsn.username or '') != ops.get('DB_USER')
            or unquote(dsn.password or '') != ops.get('DB_PASSWORD')
            or len(parse_qsl(dsn.query, keep_blank_values=True)) != len(query)
            or query != {'sslmode': 'verify-full', 'sslrootcert': '/ops/ca.crt'}):
        raise RuntimeError('Processor DSN does not match the locked database identity')
    STAGE = 'SCRIPT_PATH'
    scripts = args.scripts.resolve()
    if DIRECTORY not in scripts.parents:
        raise RuntimeError('Operation scripts must belong to this resource directory')
    directory_info = scripts.lstat()
    if not stat.S_ISDIR(directory_info.st_mode) or scripts.is_symlink() or directory_info.st_uid != 0 or directory_info.st_mode & 0o022:
        raise RuntimeError('Operation script directory ownership or permissions mismatch')
    for filename, expected in SCRIPT_SHA256.items():
        script = scripts / filename
        info = script.lstat()
        if not stat.S_ISREG(info.st_mode) or script.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError('Operation script ownership or permissions mismatch')
        if hashlib.sha256(script.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Operation script digest mismatch')
    completion = DIRECTORY / '.main-bootstrap-complete.json'
    has_completion = completion.exists()
    if has_completion:
        info = completion.lstat()
        document = json.loads(completion.read_text())
        if (not stat.S_ISREG(info.st_mode) or completion.is_symlink() or info.st_uid != 0 or info.st_mode & 0o077
                or document != {'owner': OWNER, 'project_ref': 'znxlfqctnezrropcbftw', 'public_tables': 110}):
            raise RuntimeError('Bootstrap completion marker mismatch')
    STAGE = 'HOST_LOCK'
    lockfile = (DIRECTORY / '.main-bootstrap.lock').open('w')
    fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    STAGE = 'WORK_DIRECTORY'
    operation = 'hablas-evo-bootstrap-' + secrets.token_hex(6)
    work = DIRECTORY / operation
    work.mkdir(mode=0o700)
    ca = work / 'ca.crt'
    ca.write_bytes(base64.b64decode(ops['CA_BASE64'], validate=True))
    ca.chmod(0o644)
    native = {
        'POSTGRES_HOST': ops['DB_HOST'], 'POSTGRES_PORT': '5432', 'POSTGRES_DATABASE': 'postgres',
        'POSTGRES_USERNAME': ops['DB_USER'], 'POSTGRES_PASSWORD': ops['DB_PASSWORD'],
        'PGPASSWORD': ops['DB_PASSWORD'], 'PGSSLMODE': 'verify-full', 'PGSSLROOTCERT': '/ops/ca.crt',
        'PGOPTIONS': '-c search_path=public,extensions', 'POSTGRES_CONNECTION_STRING': ops['DB_DSN'],
        'REDIS_URL': 'redis://:' + quote(ops['REDIS_PASSWORD'], safe='') + '@' + ops['REDIS_HOST'] + ':6379/0',
        'RAILS_ENV': 'production', 'RUN_MIGRATIONS': 'false', 'ACTIVE_STORAGE_SERVICE': 'local',
        'DISABLE_TELEMETRY': 'true', 'ENABLE_ACCOUNT_SIGNUP': 'false',
        'FRONTEND_URL': 'https://frontend.bootstrap.invalid', 'BACKEND_URL': 'https://api.bootstrap.invalid',
        'CORS_ORIGINS': 'https://frontend.bootstrap.invalid', 'EVO_BOOTSTRAP_OWNER': OWNER,
    }
    for key in ('SECRET_KEY_BASE', 'ENCRYPTION_KEY', 'JWT_SECRET_KEY', 'DOORKEEPER_JWT_SECRET_KEY',
                'EVOAI_CRM_API_TOKEN', 'BOT_RUNTIME_SECRET', 'AUTH_APIKEY_INTEGRATION_LOCAL'):
        native[key] = ops[key]
    native['EVO_AI_ENCRYPTION_KEY'] = ops['ENCRYPTION_KEY']
    STAGE = 'ENVIRONMENT_FILE'
    envfile = work / 'main.env'
    try:
        fd = os.open(envfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as out:
            for key, value in native.items():
                if '\n' in value or '\r' in value:
                    raise RuntimeError('Unexpected multiline operator input')
                out.write(key + '=' + value + '\n')
    except BaseException:
        envfile.unlink(missing_ok=True)
        ca.unlink(missing_ok=True)
        work.rmdir()
        fcntl.flock(lockfile, fcntl.LOCK_UN)
        lockfile.close()
        raise
    sensitive = [v for k, v in native.items() if re.search('PASSWORD|SECRET|TOKEN|ENCRYPTION_KEY|CONNECTION_STRING|REDIS_URL', k)]
    sensitive += [quote(v, safe='') for v in sensitive]
    def redact(value):
        for secret in sorted(set(sensitive), key=len, reverse=True):
            if secret:
                value = value.replace(secret, '[REDACTED]')
        return value
    def command(name, image, argv, memory='2g'):
        if not re.fullmatch(r'ghcr.io/golevel-ai/hablas-evo-production-[a-z]+@sha256:[a-f0-9]{64}', image):
            raise RuntimeError('Image must be a verified immutable project image')
        result = ['docker', 'run', '--rm', '--name', name, '--network', 'coolify', '--memory', memory,
                  '--cpus', '1', '--log-driver', 'none', '--label', 'io.golevel.owner=' + OWNER,
                  '--label', 'io.golevel.operation=' + operation, '--env-file', str(envfile),
                  '--mount', f'type=bind,source={ca},target=/ops/ca.crt,readonly']
        for filename in SCRIPT_SHA256:
            result += ['--mount', f'type=bind,source={scripts / filename},target=/ops/{filename},readonly']
        result += ['-e', 'NODE_PATH=/app/node_modules', '--entrypoint', argv[0], image, *argv[1:]]
        return result
    keeper = None
    keeper_name = None
    try:
        STAGE = 'COMPLETION_CHECK'
        verification = subprocess.run(command(operation + '-completion-check', ops['EVOFLOW_IMAGE'],
                                  ['node', '/ops/verify_main_completion.cjs'], '256m'),
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        if verification.returncode == 0:
            if not has_completion:
                temporary = completion.with_suffix('.tmp')
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as out:
                    json.dump({'owner': OWNER, 'project_ref': 'znxlfqctnezrropcbftw', 'public_tables': 110}, out)
                    out.write('\n')
                temporary.replace(completion)
            print('PASS: primary bootstrap already reconciled; destructive seeds were not repeated')
            return 0
        if has_completion:
            raise RuntimeError('Completion marker exists but database verification failed')
        STAGE = 'LOCK_CONTAINER_START'
        keeper_name = operation + '-lock'
        keeper_command = command(keeper_name, ops['EVOFLOW_IMAGE'], ['node', '/ops/database_lock.cjs'], '256m')
        keeper_command.insert(3, '-i')
        keeper = subprocess.Popen(keeper_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def drain_keeper():
            for line in keeper.stderr:
                print(redact(line), end='', flush=True)
        keeper_reader = threading.Thread(target=drain_keeper, daemon=True)
        keeper_reader.start()
        STAGE = 'DATABASE_LOCK'
        if not select.select([keeper.stdout], [], [], 90)[0] or keeper.stdout.readline().strip() != 'LOCKED':
            raise RuntimeError('Database lock was not acquired')
        print('LOCKED: approved host and database operation', flush=True)
        core_url = 'postgres://' + quote(ops['DB_USER'], safe='') + '@' + ops['DB_HOST'] + ':5432/postgres?sslmode=verify-full&sslrootcert=/ops/ca.crt&x-migrations-table=evo_core_community_schema_migrations'
        phases = [
            ('crm-schema', 'CRM_IMAGE', ['bundle', 'exec', 'rails', 'runner', '/ops/bootstrap_crm.rb']),
            ('auth-migrate', 'AUTH_IMAGE', ['bundle', 'exec', 'rails', 'db:migrate']),
            ('core-migrate', 'CORE_IMAGE', ['./migrate', '-database', core_url, '-path', './migrations', 'up']),
            ('processor-alembic', 'PROCESSOR_IMAGE', ['python', '/ops/bootstrap_processor_alembic.py']),
            ('processor-schema', 'PROCESSOR_IMAGE', ['python', '/ops/bootstrap_processor.py']),
            ('crm-seed', 'CRM_IMAGE', ['bundle', 'exec', 'rails', 'db:seed']),
            ('auth-seed', 'AUTH_IMAGE', ['bundle', 'exec', 'rails', 'db:seed']),
            ('runtime-grants', 'EVOFLOW_IMAGE', ['node', '/ops/grant_main_runtime.cjs']),
            ('completion-verify', 'EVOFLOW_IMAGE', ['node', '/ops/verify_main_completion.cjs']),
        ]
        for phase, image, argv in phases:
            STAGE = 'PHASE_' + phase.upper().replace('-', '_')
            if keeper.poll() is not None:
                raise RuntimeError('Database lock lost; promotion blocked')
            print('START: ' + phase, flush=True)
            name = operation + '-' + phase
            process = subprocess.Popen(command(name, ops[image], argv), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            def drain():
                for line in process.stdout:
                    print(redact(line), end='', flush=True)
            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            deadline = time.monotonic() + 900
            while process.poll() is None:
                if keeper.poll() is not None or time.monotonic() > deadline:
                    subprocess.run(['docker', 'stop', '--time', '5', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                    process.wait(timeout=20)
                    raise RuntimeError('Phase stopped after lock loss or timeout')
                time.sleep(1)
            reader.join(timeout=5)
            if process.returncode:
                raise RuntimeError('Phase failed: ' + phase)
            print('PASS: ' + phase, flush=True)
        temporary = completion.with_suffix('.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump({'owner': OWNER, 'project_ref': 'znxlfqctnezrropcbftw', 'public_tables': 110}, out)
            out.write('\n')
        temporary.replace(completion)
        print('PASS: primary bootstrap completed; application promotion still requires the remaining preflight checks')
    finally:
        if keeper:
            if keeper.stdin:
                keeper.stdin.close()
            try:
                keeper.wait(timeout=15)
            except subprocess.TimeoutExpired:
                subprocess.run(['docker', 'stop', '--time', '5', keeper_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        envfile.unlink(missing_ok=True)
        ca.unlink(missing_ok=True)
        work.rmdir()
        fcntl.flock(lockfile, fcntl.LOCK_UN)
        lockfile.close()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('BLOCKED: primary bootstrap stopped at ' + STAGE
              + '; no schema reset, no promotion; inspect sanitized phase output', file=sys.stderr)
        sys.exit(2)
