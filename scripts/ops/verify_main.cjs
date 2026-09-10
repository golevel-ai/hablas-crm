'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const owner = 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9';

async function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--help')) {
    console.log('Usage: node verify_main.cjs --target PATH --pg-module PATH [--dry-run]');
    return;
  }
  const arg = name => { const i = argv.indexOf(name); return i < 0 ? null : argv[i + 1]; };
  if (!arg('--target') || !arg('--pg-module')) throw new Error('INPUT');
  execFileSync('python3', [path.join(root, 'scripts/ops/ops.py'), 'validate', '--target', arg('--target')],
    { cwd: root, stdio: 'pipe', timeout: 60000 });
  const target = JSON.parse(fs.readFileSync(arg('--target'), 'utf8'));
  const ref = target.supabase.project_ref_owner_provided;
  const connection = target.supabase.main_connection;
  if (ref !== 'znxlfqctnezrropcbftw' || target.environment !== 'staging'
      || connection.host !== 'aws-0-us-east-1.pooler.supabase.com'
      || connection.runtime_username !== 'hablas_evo_stg_main.' + ref) throw new Error('TARGET');
  if (argv.includes('--dry-run')) {
    console.log('NOT_EXECUTED: main runtime login, TLS, schema isolation and catalog privileges only');
    return;
  }
  const modulePath = fs.realpathSync(arg('--pg-module'));
  if (!modulePath.startsWith(path.join(root, '.ops-private/build/')) || !modulePath.endsWith('/node_modules/pg')) throw new Error('DRIVER');
  const secret = path.join(root, '.ops-private/secrets', ref + '-main-runtime.password');
  const stat = fs.lstatSync(secret);
  if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o077)) throw new Error('SECRET_PERMISSIONS');
  const { Client } = require(modulePath);
  const client = new Client({ host: connection.host, port: 5432, database: 'postgres',
    user: connection.runtime_username, password: fs.readFileSync(secret, 'utf8'),
    ssl: { ca: fs.readFileSync(path.join(root, 'infra/certs/supabase-root-2021.crt'), 'utf8'), rejectUnauthorized: true },
    connectionTimeoutMillis: 10000, query_timeout: 30000, statement_timeout: 30000,
    application_name: 'hablas-evo-staging-main-runtime-verification' });
  try {
    await client.connect();
    if (!client.connection.stream.authorized) throw new Error('TLS');
    await client.query('BEGIN READ ONLY');
    const row = (await client.query(`SELECT current_user AS role, current_schema() AS schema,
      (SELECT count(*)::int FROM pg_tables WHERE schemaname='public') AS public_tables,
      has_schema_privilege(current_user, 'public', 'CREATE') AS can_ddl,
      has_schema_privilege(current_user, 'hablas_evoflow_staging', 'USAGE') AS can_use_evoflow,
      has_table_privilege(current_user, (SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='auth' AND c.relname='users'), 'SELECT') AS can_read_supabase_auth,
      has_table_privilege(current_user, 'public.contacts', 'SELECT') AS can_select,
      has_table_privilege(current_user, 'public.contacts', 'INSERT') AS can_insert,
      has_table_privilege(current_user, 'public.contacts', 'UPDATE') AS can_update,
      has_table_privilege(current_user, 'public.contacts', 'DELETE') AS can_delete,
      COALESCE((SELECT bool_or(has_table_privilege(current_user, c.oid, 'INSERT')
        OR has_table_privilege(current_user, c.oid, 'UPDATE') OR has_table_privilege(current_user, c.oid, 'DELETE'))
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
        AND c.relname=ANY(ARRAY['schema_migrations','ar_internal_metadata','alembic_version','evo_core_community_schema_migrations'])), false) AS can_change_migrations,
      (SELECT count(*)::int FROM ar_internal_metadata WHERE key='hablas_evo_bootstrap_source' AND value LIKE $1) AS source_markers,
      (SELECT count(*)::int FROM alembic_version) AS alembic_versions,
      (SELECT count(*)::int FROM user_states WHERE app_name='hablas-infra-bootstrap') AS bootstrap_user_states,
      (SELECT count(*)::int FROM app_states WHERE app_name='hablas-infra-bootstrap') AS bootstrap_app_states`, [owner + '/%'])).rows[0];
    await client.query('ROLLBACK');
    if (row.role !== 'hablas_evo_stg_main' || row.schema !== 'public' || row.public_tables !== 110
        || row.can_ddl || row.can_use_evoflow || row.can_read_supabase_auth || row.can_change_migrations
        || !row.can_select || !row.can_insert || !row.can_update || !row.can_delete
        || row.source_markers !== 1 || row.alembic_versions !== 1
        || row.bootstrap_user_states || row.bootstrap_app_states) throw new Error('PRIVILEGES_OR_SCHEMA');
    console.log(JSON.stringify({ status: 'PASS', scope: 'actual main runtime role via verified TLS', ...row }, null, 2));
  } finally {
    if (client) await client.end().catch(() => {});
  }
}

main().catch(error => {
  const code = /^[A-Z0-9_]{2,80}$/.test(error.code || error.message) ? (error.code || error.message) : 'RUNTIME_CHECK_FAILED';
  console.error('BLOCKED: ' + code + '; credentials suppressed');
  process.exitCode = 2;
});
