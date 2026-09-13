'use strict';
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');

async function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--help')) {
    console.log('Usage: node verify_evoflow.cjs --target PATH --context GENERATED_EVOFLOW_CONTEXT [--dry-run]');
    return;
  }
  const arg = name => { const i = argv.indexOf(name); return i < 0 ? null : argv[i + 1]; };
  if (!arg('--target') || !arg('--context')) throw new Error('INPUT');
  const target = JSON.parse(fs.readFileSync(arg('--target'), 'utf8'));
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'infra/deployment-manifest.yml'), 'utf8'));
  const ref = target.supabase.project_ref_owner_provided;
  if (ref !== 'znxlfqctnezrropcbftw' || target.environment !== 'production'
      || target.supabase.evoflow_schema !== 'hablas_evoflow_production') throw new Error('TARGET');
  if (argv.includes('--dry-run')) { console.log('NOT_EXECUTED: scoped runtime login and catalog privileges only'); return; }
  const context = fs.realpathSync(arg('--context'));
  if (!context.startsWith(path.join(root, '.ops-private/build/')) || !context.endsWith('/evoflow')) throw new Error('CONTEXT');
  const { DataSource } = require(path.join(context, 'node_modules/typeorm'));
  const { postgresOptions } = require(path.join(context, 'deployment-postgres.cjs'));
  const secret = path.join(root, '.ops-private/secrets', ref + '-prod-flow.password');
  if ((fs.lstatSync(secret).mode & 0o077) || fs.lstatSync(secret).isSymbolicLink()) throw new Error('SECRET_PERMISSIONS');
  const options = postgresOptions({ POSTGRES_DB_HOST: target.supabase.main_connection.host, POSTGRES_DB_PORT: '5432',
    POSTGRES_DB_DATABASE: 'postgres', POSTGRES_DB_USERNAME: 'hablas_evo_prod_flow.' + ref,
    POSTGRES_DB_PASSWORD: fs.readFileSync(secret, 'utf8'), POSTGRES_DB_SCHEMA: 'hablas_evoflow_production',
    POSTGRES_SSLMODE: 'verify-full', PGSSLROOTCERT: path.join(root, 'infra/certs/supabase-root-2021.crt'), POSTGRES_POOL_MAX: '1' });
  const source = new DataSource({ ...options, entities: [path.join(context, 'dist/**/*.entity.js')] });
  let runner;
  try {
    await source.initialize();
    runner = source.createQueryRunner();
    await runner.query('BEGIN READ ONLY');
    const [row] = await runner.query(`SELECT current_user AS role, current_schema() AS schema,
      (SELECT oid FROM pg_namespace WHERE nspname=current_schema()) AS schema_oid,
      has_schema_privilege(current_user, current_schema(), 'CREATE') AS can_ddl,
      has_table_privilege(current_user, (SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='auth' AND c.relname='users'), 'SELECT') AS can_read_supabase_auth,
      has_table_privilege(current_user, 'hablas_evoflow_production.migrations', 'SELECT') AS can_read_migration_metadata,
      has_table_privilege(current_user, 'hablas_evoflow_production.migrations', 'INSERT,UPDATE,DELETE,TRUNCATE') AS can_change_migrations,
      has_table_privilege(current_user, 'hablas_evoflow_production.contacts', 'SELECT') AS can_select,
      has_table_privilege(current_user, 'hablas_evoflow_production.contacts', 'INSERT') AS can_insert,
      has_table_privilege(current_user, 'hablas_evoflow_production.contacts', 'UPDATE') AS can_update,
      has_table_privilege(current_user, 'hablas_evoflow_production.contacts', 'DELETE') AS can_delete,
      (SELECT count(*)::int FROM contacts) AS contacts`);
    await runner.query('ROLLBACK');
    if (row.role !== 'hablas_evo_prod_flow' || row.schema !== 'hablas_evoflow_production'
        || row.schema_oid !== manifest.supabase.evoflow.schema_oid || row.can_ddl
        || row.can_read_supabase_auth || !row.can_read_migration_metadata || row.can_change_migrations
        || !row.can_select || !row.can_insert || !row.can_update || !row.can_delete) throw new Error('PRIVILEGES');
    console.log(JSON.stringify({ status: 'PASS', scope: 'actual Supabase runtime role via verified TLS', ...row }, null, 2));
  } finally {
    if (runner) await runner.release();
    if (source.isInitialized) await source.destroy();
  }
}

main().catch(error => {
  const code = /^[A-Z0-9_]{2,80}$/.test(error.code || error.message) ? (error.code || error.message) : 'RUNTIME_CHECK_FAILED';
  console.error('BLOCKED: ' + code + '; credentials suppressed');
  process.exitCode = 2;
});
