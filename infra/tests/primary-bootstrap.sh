#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" ]]; then
  printf '%s\n' 'CI-only disposable PostgreSQL/Redis bootstrap test. Requires CRM_IMAGE and AUTH_IMAGE.'
  exit 0
fi
if [[ "${GITHUB_ACTIONS:-}" != true || "${RUNNER_OS:-}" != Linux || -z "${GITHUB_RUN_ID:-}" ]]; then
  printf '%s\n' 'BLOCKED: this test runs only on the isolated Linux CI runner' >&2
  exit 2
fi
if [[ "${1:-}" == "--dry-run" ]]; then
  printf '%s\n' 'NOT_EXECUTED: new local CI network/containers, no Supabase connection or credentials'
  exit 0
fi
: "${CRM_IMAGE:?}" "${AUTH_IMAGE:?}" "${CORE_IMAGE:?}" "${PROCESSOR_IMAGE:?}"
ROOT=$(git rev-parse --show-toplevel)
PREFIX="hablas-evo-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT:-1}"
PG_ID=''
REDIS_ID=''
NETWORK_ID=''
cleanup() {
  if [[ -n "$PG_ID" ]]; then docker rm -f "$PG_ID" >/dev/null; fi
  if [[ -n "$REDIS_ID" ]]; then docker rm -f "$REDIS_ID" >/dev/null; fi
  if [[ -n "$NETWORK_ID" ]]; then docker network rm "$NETWORK_ID" >/dev/null; fi
}
trap cleanup EXIT
PG_IMAGE=$(python3 -c "import json; print(json.load(open('infra/tests/images.lock.json'))['postgres']['reference'])")
REDIS_IMAGE=$(python3 -c "import json; print(json.load(open('infra/build/oci.lock.json'))['images']['redis']['reference'])")
NETWORK_ID=$(docker network create --internal "$PREFIX")
PG_ID=$(docker run -d --rm --name "$PREFIX-pg" --network "$NETWORK_ID" --network-alias pg --memory 512m --cpus 1 \
  -e POSTGRES_PASSWORD=local-ci-only-password "$PG_IMAGE")
REDIS_ID=$(docker run -d --rm --name "$PREFIX-redis" --network "$NETWORK_ID" --network-alias redis --memory 128m --cpus 0.25 "$REDIS_IMAGE")
for attempt in $(seq 1 30); do
  if docker exec "$PG_ID" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$PG_ID" pg_isready -U postgres
# All values below are synthetic and confined to this internal CI network.
SECRET_KEY_BASE=$(openssl rand -hex 64)
JWT_SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python3 -c 'import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')
COMMON=(--rm --network "$NETWORK_ID" --memory 2g --cpus 1 --entrypoint bundle
  --mount "type=bind,source=$ROOT/infra/tests,target=/ops,readonly"
  --mount "type=bind,source=$ROOT/scripts/ops/bootstrap_crm.rb,target=/bootstrap_crm.rb,readonly"
  --mount "type=bind,source=$ROOT/scripts/ops/bootstrap_processor_alembic.py,target=/processor-alembic.py,readonly"
  --mount "type=bind,source=$ROOT/scripts/ops/bootstrap_processor.py,target=/processor-bootstrap.py,readonly"
  -e RAILS_ENV=production -e RUN_MIGRATIONS=false -e INFRA_LOCAL_SCHEMA_TEST=true
  -e EVO_BOOTSTRAP_OWNER=hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9
  -e POSTGRES_HOST=pg -e POSTGRES_PORT=5432 -e POSTGRES_DATABASE=postgres
  -e POSTGRES_USERNAME=postgres -e POSTGRES_PASSWORD=local-ci-only-password
  -e PGSSLMODE=disable -e REDIS_URL=redis://redis:6379/0
  -e "SECRET_KEY_BASE=$SECRET_KEY_BASE" -e "JWT_SECRET_KEY=$JWT_SECRET_KEY"
  -e "DOORKEEPER_JWT_SECRET_KEY=$JWT_SECRET_KEY"
  -e "EVO_AI_ENCRYPTION_KEY=$ENCRYPTION_KEY" -e "EVOAI_CRM_API_TOKEN=$JWT_SECRET_KEY"
  -e FRONTEND_URL=https://frontend.invalid -e BACKEND_URL=https://api.invalid
  -e CORS_ORIGINS=https://frontend.invalid -e ACTIVE_STORAGE_SERVICE=local
  -e DISABLE_TELEMETRY=true -e ENABLE_ACCOUNT_SIGNUP=false)
docker run "${COMMON[@]}" "$CRM_IMAGE" exec rails runner /bootstrap_crm.rb
# Test the native migration path, not the upstream blanket history-stamping command.
docker run "${COMMON[@]}" "$AUTH_IMAGE" exec rails db:migrate
docker run "${COMMON[@]}" --entrypoint ./migrate -e PGPASSWORD=local-ci-only-password "$CORE_IMAGE" \
  -database 'postgres://postgres@pg:5432/postgres?sslmode=disable&x-migrations-table=evo_core_community_schema_migrations' -path ./migrations up
PROCESSOR_DSN='postgresql://postgres:local-ci-only-password@pg:5432/postgres?sslmode=disable'
docker run "${COMMON[@]}" --entrypoint python -e "POSTGRES_CONNECTION_STRING=$PROCESSOR_DSN" "$PROCESSOR_IMAGE" /processor-alembic.py
docker run "${COMMON[@]}" --entrypoint python -e "POSTGRES_CONNECTION_STRING=$PROCESSOR_DSN" "$PROCESSOR_IMAGE" /processor-bootstrap.py
docker run "${COMMON[@]}" -e INFRA_TEST_PHASE=crm-write "$CRM_IMAGE" exec rails runner /ops/primary-schema-probe.rb
docker run "${COMMON[@]}" -e INFRA_TEST_PHASE=auth-read-write "$AUTH_IMAGE" exec rails runner /ops/primary-schema-probe.rb
docker run "${COMMON[@]}" -e INFRA_TEST_PHASE=crm-read "$CRM_IMAGE" exec rails runner /ops/primary-schema-probe.rb
docker run "${COMMON[@]}" "$CRM_IMAGE" exec rails runner /bootstrap_crm.rb
docker run "${COMMON[@]}" -e INFRA_TEST_PHASE=crm-read "$CRM_IMAGE" exec rails runner /ops/primary-schema-probe.rb
printf '%s\n' 'PASS: disposable primary Rails bootstrap and cross-service model contract'
