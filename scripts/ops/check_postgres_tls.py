#!/usr/bin/env python3
"""Verify PostgreSQL SSLRequest + TLS peer identity without sending credentials."""
import argparse
import json
from pathlib import Path
import socket
import ssl
import struct
import sys

from ops import Blocked, ROOT, load, validate_target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--mode", choices=("session", "direct"), required=True)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        target = validate_target(load(args.target))
        if target["supabase"]["project_identity_status"] != "VERIFIED_PROJECT_URL_AND_DASHBOARD":
            raise Blocked("Project identity must be verified before network checks")
        connection = target["supabase"]["main_connection" if args.mode == "session" else "direct_connection"]
        host, port = connection["host"], connection["port"]
        if not host.endswith(".supabase.com") and not host.endswith(".supabase.co"):
            raise Blocked("Unexpected PostgreSQL hostname")
        if port != 5432 or not 1 <= args.timeout <= 30:
            raise Blocked("Unexpected PostgreSQL port or timeout")
        if args.dry_run:
            print(json.dumps({"status": "NOT_EXECUTED", "host": host, "port": port}))
            return 0
        context = ssl.create_default_context(cafile=str(ROOT / "infra/certs/supabase-root-2021.crt"))
        with socket.create_connection((host, port), timeout=args.timeout) as raw:
            raw.sendall(struct.pack("!II", 8, 80877103))
            if raw.recv(1) != b"S":
                raise Blocked("Endpoint did not accept PostgreSQL SSLRequest")
            with context.wrap_socket(raw, server_hostname=host) as connection:
                certificate = connection.getpeercert()
                print(json.dumps({"status": "PASS", "scope": "TLS only; no PostgreSQL login",
                                  "host": host, "tls_version": connection.version(),
                                  "issuer": certificate.get("issuer"),
                                  "certificate_expires": certificate.get("notAfter")}))
        return 0
    except ssl.SSLCertVerificationError:
        print("FAIL: peer certificate or hostname verification failed", file=sys.stderr)
        return 1
    except (Blocked, OSError, KeyError, ValueError) as exc:
        print("BLOCKED: " + (str(exc) if isinstance(exc, Blocked) else "TLS connection unavailable"), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
