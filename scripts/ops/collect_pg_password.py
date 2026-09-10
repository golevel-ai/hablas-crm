#!/usr/bin/env python3
"""Collect the owner's PostgreSQL password via a local masked macOS dialog.

No secret in chat, command arguments, stdout or Git. Exclusive 0600 local file.
Does not reset a password or perform any remote request.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

from ops import Blocked, ROOT, load, validate_target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        target = validate_target(load(args.target))
        supabase = target["supabase"]
        if supabase.get("project_identity_status") != "VERIFIED_PROJECT_URL_AND_DASHBOARD":
            raise Blocked("Verify the Supabase project before collecting its credential")
        ref = supabase["project_ref_owner_provided"]
        if not re.fullmatch(r"[a-z]{20}", ref):
            raise Blocked("Unexpected project ref")
        parent = ROOT / ".ops-private/secrets"
        destination = parent / (ref + "-admin.password")
        if destination.exists():
            raise Blocked("Credential file already exists; it will not be overwritten")
        if args.dry_run:
            print("NOT_EXECUTED: local masked dialog; exclusive 0600 secret file, no remote writes")
            return 0
        if sys.platform != "darwin":
            raise Blocked("Masked dialog requires macOS; use the approved vault instead")
        for directory in (ROOT / ".ops-private", parent):
            if directory.is_symlink():
                raise Blocked("Secret directory must not be a symlink")
            directory.mkdir(mode=0o700, exist_ok=True)
            if directory.stat().st_uid != os.getuid():
                raise Blocked("Secret directory must belong to this user")
            directory.chmod(0o700)
        script = (
            'text returned of (display dialog "Senha PostgreSQL existente do projeto hablas-crm (' + ref + '). '
            'Uso: validar conexao e preparar migrations. A senha sera guardada localmente com permissao 0600, '
            'fora do Git. Nao use a chave sb_secret da API." with title "OpenCode - Supabase staging" '
            'default answer "" with hidden answer buttons {"Cancelar", "Guardar"} default button "Guardar" '
            'cancel button "Cancelar")'
        )
        result = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=300)
        if result.returncode:
            raise Blocked("Password input cancelled or local dialog unavailable")
        password = result.stdout.rstrip(b"\r\n")
        if not password or b"\n" in password or password.startswith(b"sb_secret_"):
            raise Blocked("Expected a PostgreSQL password, not an API key")
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(password)
        print("CAPTURED: PostgreSQL credential stored locally with mode 0600; value not displayed")
        return 0
    except (Blocked, OSError, subprocess.SubprocessError, KeyError):
        print("BLOCKED: credential not collected; no existing password reset or overwritten", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
