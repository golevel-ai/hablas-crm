#!/usr/bin/env python3
"""Generate deployment build contexts from pinned git archives + reviewed overlays.

No checkout/submodule edits, image build, registry publication or remote changes.
Contexts are exclusive, locally generated under .ops-private/build/<recipe>/<service>.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

from ops import Blocked, ROOT, git, load, validate_release, validate_target

RECIPES = {
    "auth": ("evo-auth-service-community", "Dockerfile"),
    "crm": ("evo-ai-crm-community", "docker/Dockerfile"),
    "core": ("evo-ai-core-service-community", "Dockerfile"),
    "processor": ("evo-ai-processor-community", "Dockerfile"),
    "bot": ("evo-bot-runtime", "Dockerfile"),
    "evoflow": ("evo-flow-community", "Dockerfile"),
    "gateway": ("nginx", "Dockerfile"),
}
BASE_IMAGES = {
    "auth": {"ruby:$RUBY_VERSION-slim": ("auth_base", 1)},
    "crm": {"node:23-alpine": ("crm_node", 1), "ruby:3.4.4-alpine3.21": ("crm_ruby", 2)},
    "core": {"golang:1.24.4-alpine": ("core_go", 1), "alpine:latest": ("alpine", 1)},
    "processor": {"python:3.11-slim": ("processor_python", 1)},
    "bot": {"golang:1.24-alpine": ("bot_go", 1), "alpine:3.20": ("alpine", 1)},
    "evoflow": {"node:20-slim": ("flow_node", 2)},
    "gateway": {"nginx:alpine": ("gateway_nginx", 1)},
}


def recipe_digest():
    digest = hashlib.sha256()
    paths = [Path(__file__).resolve(), *sorted((ROOT / "infra/build").glob("*"))]
    for path in paths:
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def replace(path, old, new, count=1):
    text = path.read_text()
    if text.count(old) != count:
        raise Blocked("Overlay source does not match expected contract: " + path.name)
    path.write_text(text.replace(old, new))


def archive(source, destination, subtree=False):
    cwd = ROOT if subtree else source
    tree = "HEAD:nginx" if subtree else "HEAD"
    try:
        raw = subprocess.run(["git", "archive", "--format=tar", tree], cwd=cwd,
                             capture_output=True, check=True, timeout=60).stdout
    except subprocess.SubprocessError:
        raise Blocked("Unable to archive pinned source") from None
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for member in tar.getmembers():
            path = destination / member.name
            if member.name.startswith("/") or ".." in Path(member.name).parts:
                raise Blocked("Unsafe path in git archive")
            if not (member.isfile() or member.isdir()):
                raise Blocked("Non-regular entry in git archive requires explicit review")
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as data:
                    path.write_bytes(data.read())
                path.chmod(member.mode & 0o777)


def copy_overlay(destination, name, relative):
    path = destination / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((ROOT / "infra/build" / name).read_bytes())


def transform(service, destination):
    if service in ("auth", "crm"):
        copy_overlay(destination, "rails-entrypoint.sh", "infra/rails-entrypoint.sh")
        copy_overlay(destination, "sidekiq-health.rb", "infra/sidekiq-health.rb")
        database = destination / "config/database.yml"
        replace(database, "  encoding: unicode\n", "  encoding: unicode\n"
                "  sslmode: <%= ENV.fetch('PGSSLMODE') %>\n"
                "  sslrootcert: <%= ENV.fetch('PGSSLROOTCERT', '/etc/ssl/certs/ca-certificates.crt') %>\n")
        session = destination / "config/initializers/session_store.rb"
        if service == "auth":
            replace(session, "_evo_auth_service_session", "_hablas_evo_prod_auth_session")
            production = destination / "config/environments/production.rb"
            replace(production,
                    "GlobalConfigService.load('ACTIVE_STORAGE_SERVICE', ENV.fetch('ACTIVE_STORAGE_SERVICE', 'local'))",
                    "ENV.fetch('ACTIVE_STORAGE_SERVICE') { GlobalConfigService.load('ACTIVE_STORAGE_SERVICE', 'local') }")
            dynamic_storage = destination / "config/initializers/active_storage_dynamic_service.rb"
            replace(dynamic_storage,
                    "service_name = GlobalConfigService.load(\n"
                    "          'ACTIVE_STORAGE_SERVICE',\n"
                    "          ENV.fetch('ACTIVE_STORAGE_SERVICE', 'local')\n"
                    "        ).presence || 'local'",
                    "service_name = ENV.fetch('ACTIVE_STORAGE_SERVICE') {\n"
                    "          GlobalConfigService.load('ACTIVE_STORAGE_SERVICE', 'local')\n"
                    "        }.presence || 'local'")
            storage = destination / "config/storage.yml"
            replace(storage,
                    "  access_key_id: <%= GlobalConfigService.load('STORAGE_ACCESS_KEY_ID', ENV.fetch('STORAGE_ACCESS_KEY_ID', '')) rescue ENV.fetch('STORAGE_ACCESS_KEY_ID', '') %>",
                    "  access_key_id: <%= ENV.fetch('STORAGE_ACCESS_KEY_ID') if ENV.fetch('ACTIVE_STORAGE_SERVICE', 'local') == 's3_compatible' %>")
            replace(storage,
                    "  secret_access_key: <%= GlobalConfigService.load('STORAGE_ACCESS_SECRET', ENV.fetch('STORAGE_SECRET_ACCESS_KEY', '')) rescue ENV.fetch('STORAGE_SECRET_ACCESS_KEY', '') %>",
                    "  secret_access_key: <%= ENV.fetch('STORAGE_SECRET_ACCESS_KEY') if ENV.fetch('ACTIVE_STORAGE_SERVICE', 'local') == 's3_compatible' %>")
            replace(storage,
                    "  region: <%= GlobalConfigService.load('STORAGE_REGION', ENV.fetch('STORAGE_REGION', 'auto')) rescue ENV.fetch('STORAGE_REGION', 'auto') %>",
                    "  region: <%= ENV.fetch('STORAGE_REGION', 'auto') if ENV.fetch('ACTIVE_STORAGE_SERVICE', 'local') == 's3_compatible' %>")
            replace(storage,
                    "  bucket: <%= GlobalConfigService.load('STORAGE_BUCKET_NAME', ENV.fetch('STORAGE_BUCKET_NAME', '')) rescue ENV.fetch('STORAGE_BUCKET_NAME', '') %>",
                    "  bucket: <%= ENV.fetch('STORAGE_BUCKET_NAME') if ENV.fetch('ACTIVE_STORAGE_SERVICE', 'local') == 's3_compatible' %>")
            replace(storage,
                    "  endpoint: <%= GlobalConfigService.load('STORAGE_ENDPOINT', ENV.fetch('STORAGE_ENDPOINT', '')) rescue ENV.fetch('STORAGE_ENDPOINT', '') %>",
                    "  endpoint: <%= ENV.fetch('STORAGE_ENDPOINT') if ENV.fetch('ACTIVE_STORAGE_SERVICE', 'local') == 's3_compatible' %>")
            helper = destination / "app/controllers/concerns/auth_helper.rb"
            text = helper.read_text()
            start, end = text.index("  def cookie_domain\n"), text.index("  def render_unauthorized(")
            text = text[:start] + "  def cookie_domain\n    nil # Host-only for this isolated production deployment.\n  end\n\n" + text[end:]
            # Remove existing debug statements that reveal token prefixes.
            text = "\n".join(line for line in text.splitlines()
                             if "header value (first" not in line and "token value (first" not in line
                             and "Using refresh token from cookie:" not in line) + "\n"
            helper.write_text(text)
            for relative in ("app/controllers/concerns/auth_helper.rb", "app/controllers/api/v1/auth_controller.rb",
                             "config/initializers/doorkeeper_token_lookup.rb"):
                path = destination / relative
                path.write_text(path.read_text().replace("_evo_rt", "_hablas_evo_prod_rt")
                                .replace("_evo_at", "_hablas_evo_prod_at"))
            lookup = destination / "config/initializers/doorkeeper_token_lookup.rb"
            replace(lookup, "            return cookies['refresh_token'] if cookies['refresh_token'].present?\n", "")
        else:
            replace(session, "key: '_evolution_session', same_site: :lax",
                    "key: '_hablas_evo_prod_crm_session', secure: true, httponly: true, same_site: :lax")
            qrcodes = destination / "app/controllers/api/v1/evolution_go/qrcodes_controller.rb"
            for prefix in ("parsed_response['data']", "parsed_response"):
                for field, legacy in (("qrcode", "Qrcode"), ("code", "Code")):
                    replace(qrcodes, f"{prefix}['{legacy}']",
                            f"{prefix}['{field}'] || {prefix}['{legacy}']")
    elif service == "processor":
        copy_overlay(destination, "processor-postgres-tls.py", "src/config/postgres_tls.py")
        main = destination / "src/main.py"
        replace(main, "Base.metadata.create_all(bind=engine, tables=_tables_to_create, checkfirst=True)",
                "# Deployment schema is managed exclusively by the migration executor.\n"
                "# Never issue DDL while importing the runtime application.")
        database = destination / "src/config/database.py"
        replace(database, "    pool_pre_ping=True,", "    pool_size=5,\n    max_overflow=0,\n"
                "    pool_timeout=10,\n    pool_pre_ping=True,")
        dockerfile = destination / "Dockerfile"
        replace(dockerfile, 'CMD ["sh", "-c", "alembic upgrade head && python -m scripts.run_seeders && uvicorn src.main:app --host $HOST --port $PORT"]',
                'CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]')
        artifact = destination / "src/services/adk/artifacts/minio_artifact_service.py"
        text = artifact.read_text()
        start = text.index("    def _ensure_bucket_exists(self) -> None:")
        end = text.index("    def _file_has_user_namespace", start)
        artifact.write_text(text[:start] +
                            "    def _ensure_bucket_exists(self) -> None:\n"
                            "        # The private bucket must be provisioned separately with restricted credentials.\n"
                            "        if not self.client.bucket_exists(self.bucket_name):\n"
                            "            raise RuntimeError('Configured artifact bucket does not exist')\n\n" + text[end:])
        provider = destination / "src/services/service_providers.py"
        text = provider.read_text()
        start = text.index("def get_async_db_url(")
        end = text.index("# Initialize artifacts service using the factory")
        provider.write_text(text[:start] +
                            "from src.config.postgres_tls import async_connection_options\n\n"
                            "def get_async_db_url(db_url: str) -> str:\n"
                            "    return async_connection_options(db_url)[0]\n\n"
                            "async_db_url, connect_args = async_connection_options(os.environ['POSTGRES_CONNECTION_STRING'])\n"
                            "session_service = DatabaseSessionService(\n"
                            "    db_url=async_db_url, connect_args=connect_args,\n"
                            "    pool_pre_ping=True, pool_recycle=1800,\n"
                            "    pool_size=5, max_overflow=0, pool_timeout=10,\n"
                            ")\n\n" + text[end:])
    elif service == "evoflow":
        copy_overlay(destination, "evoflow-postgres.cjs", "deployment-postgres.cjs")
        (destination / "src/database/ormconfig.ts").write_text(
            "import { DataSource } from 'typeorm';\nimport 'dotenv/config';\n"
            "const { postgresOptions } = require('../../deployment-postgres.cjs');\n"
            "export const AppDataSource = new DataSource({\n  ...postgresOptions(),\n"
            "  entities: ['dist/**/*.entity.js'],\n  migrations: ['dist/database/migrations/*.js'],\n});\n")
        dockerfile = destination / "Dockerfile"
        replace(dockerfile, "COPY src/ ./src/", "COPY src/ ./src/\nCOPY deployment-postgres.cjs ./deployment-postgres.cjs")
        replace(dockerfile, "COPY --from=builder --chown=nestjs:nodejs /app/dist ./dist",
                "COPY --from=builder --chown=nestjs:nodejs /app/dist ./dist\n"
                "COPY --from=builder --chown=nestjs:nodejs /app/deployment-postgres.cjs ./deployment-postgres.cjs")
        migration = destination / "src/database/migrations/1757009500000-AddWaitingStatusToJourneySession.ts"
        replace(migration, "WHERE typname = 'journey_sessions_status_enum'",
                "WHERE typname = 'journey_sessions_status_enum' AND typnamespace = current_schema()::regnamespace", 2)
        replace(migration, "WHERE table_name='journey_sessions'",
                "WHERE table_schema=current_schema() AND table_name='journey_sessions'", 2)
    elif service == "gateway":
        conf = destination / "default.conf.template"
        replace(conf, "    set $auth_service", "    set $evoflow_service http://${EVOFLOW_UPSTREAM};\n    set $auth_service")
        replace(conf, "    server_name _;", "    server_name _;\n"
                "    if ($hablas_origin_denied) { return 403; }\n"
                "    if ($request_method = OPTIONS) { return 204; }\n"
                "    proxy_hide_header Access-Control-Allow-Origin;\n"
                "    proxy_hide_header Access-Control-Allow-Credentials;\n"
                "    proxy_hide_header Access-Control-Allow-Headers;\n"
                "    proxy_hide_header Access-Control-Allow-Methods;\n"
                "    add_header Access-Control-Allow-Origin $hablas_cors_origin always;\n"
                "    add_header Access-Control-Allow-Credentials true always;\n"
                "    add_header Access-Control-Allow-Methods 'GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD' always;\n"
                "    add_header Access-Control-Allow-Headers $http_access_control_request_headers always;\n"
                "    add_header Vary Origin always;\n"
                "    add_header Cache-Control no-store always;")
        replace(conf, "    location ~ ^/api/v1/ {", "    # Campaigns use EvoFlow directly; segments/journeys still use the CRM proxy.\n"
                "    location ~ ^/api/v1/campaigns(?:/|$) {\n"
                "        proxy_pass $evoflow_service$request_uri;\n"
                "        proxy_set_header Host $host;\n"
                "        proxy_set_header X-Real-IP $remote_addr;\n"
                "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
                "        proxy_set_header X-Forwarded-Proto https;\n"
                "        proxy_set_header Authorization $http_authorization;\n"
                "        proxy_set_header api_access_token $http_api_access_token;\n"
                "        proxy_http_version 1.1;\n"
                "        proxy_read_timeout 300;\n"
                "    }\n\n    location ~ ^/api/v1/ {")
        copy_overlay(destination, "gateway-cors.conf.template", "00-cors.conf.template")
        dockerfile = destination / "Dockerfile"
        replace(dockerfile, 'ENV NGINX_ENVSUBST_FILTER="^(AUTH|CRM|CORE|PROCESSOR|BOT_RUNTIME)_UPSTREAM$"',
                'ENV NGINX_ENVSUBST_FILTER="^((AUTH|CRM|CORE|PROCESSOR|BOT_RUNTIME|EVOFLOW)_UPSTREAM|(FRONTEND|API)_ORIGIN)$"')
        replace(dockerfile, "EXPOSE 3030", "COPY 00-cors.conf.template /etc/nginx/templates/00-cors.conf.template\n\nEXPOSE 3030")
    images = load(ROOT / "infra/build/oci.lock.json")["images"]
    dockerfile = destination / RECIPES[service][1]
    for original, (name, count) in BASE_IMAGES[service].items():
        pinned = images[name]
        if pinned["platform"] != "linux/amd64" or "@sha256:" not in pinned["reference"]:
            raise Blocked("Base-image manifest is not pinned to linux/amd64")
        replace(dockerfile, "FROM " + original, "FROM " + pinned["reference"], count)
    if service == "core":
        replace(dockerfile, "github.com/golang-migrate/migrate/v4/cmd/migrate@latest",
                "github.com/golang-migrate/migrate/v4/cmd/migrate@v4.18.3")


def generate(service, dry_run=False):
    lock = validate_release()
    path, dockerfile = RECIPES[service]
    if service == "gateway" and git("status", "--porcelain", "--", "nginx"):
        raise Blocked("Gateway has local source changes; review before archiving")
    recipe = recipe_digest()
    destination = ROOT / ".ops-private/build" / recipe / service
    source_sha = lock["commit"] if service == "gateway" else lock["submodules"][path]
    manifest = {"service": service, "source_path": path, "source_commit": source_sha,
                "infrastructure_commit": git("rev-parse", "HEAD"),
                "recipe_sha256": recipe, "dockerfile": dockerfile, "platform": "linux/amd64"}
    if dry_run:
        return {**manifest, "status": "NOT_EXECUTED"}
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    archive(ROOT / path, destination, subtree=service == "gateway")
    transform(service, destination)
    manifest["files_sha256"] = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(destination.rglob("*")) if p.is_file()}
    (destination / "hablas-build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {k: v for k, v in manifest.items() if k != "files_sha256"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--service", choices=[*RECIPES, "all"], required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        validate_target(load(args.target))
        services = list(RECIPES) if args.service == "all" else [args.service]
        for service in services:
            print(json.dumps(generate(service, args.dry_run)))
        return 0
    except FileExistsError:
        print("BLOCKED: context exists; preserve it and validate its manifest instead of overwriting", file=sys.stderr)
        return 2
    except (Blocked, OSError, ValueError) as exc:
        print("BLOCKED: " + (str(exc) if isinstance(exc, Blocked) else "context generation failed"), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
