'use strict';
const fs = require('node:fs');
const { Client } = require('pg');
const OWNER = 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9';

async function main() {
  if (process.env.EVO_BOOTSTRAP_OWNER !== OWNER
      || process.env.POSTGRES_USERNAME !== 'hablas_evo_stg_main_migrator.znxlfqctnezrropcbftw') throw new Error('TARGET');
  const client = new Client({ host: process.env.POSTGRES_HOST, port: 5432, database: 'postgres',
    user: process.env.POSTGRES_USERNAME, password: process.env.POSTGRES_PASSWORD,
    ssl: { ca: fs.readFileSync('/ops/ca.crt', 'utf8'), rejectUnauthorized: true },
    connectionTimeoutMillis: 10000, query_timeout: 15000, statement_timeout: 15000 });
  try {
    await client.connect();
    if (!client.connection.stream.authorized) throw new Error('TLS');
    await client.query('BEGIN READ ONLY');
    const row = (await client.query(`SELECT current_user AS role, current_schema() AS schema,
      (SELECT count(*)::int FROM pg_tables WHERE schemaname='public') AS public_tables,
      has_schema_privilege('hablas_evo_stg_main', 'public', 'CREATE') AS runtime_can_ddl,
      has_schema_privilege('hablas_evo_stg_main', 'hablas_evoflow_staging', 'USAGE') AS runtime_can_use_evoflow,
      has_table_privilege('hablas_evo_stg_main', (SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='auth' AND c.relname='users'), 'SELECT') AS runtime_can_read_auth,
      has_table_privilege('hablas_evo_stg_main', 'public.contacts', 'SELECT') AS runtime_can_select,
      has_table_privilege('hablas_evo_stg_main', 'public.contacts', 'INSERT') AS runtime_can_insert,
      has_table_privilege('hablas_evo_stg_main', 'public.contacts', 'UPDATE') AS runtime_can_update,
      has_table_privilege('hablas_evo_stg_main', 'public.contacts', 'DELETE') AS runtime_can_delete,
      COALESCE((SELECT bool_or(has_table_privilege('hablas_evo_stg_main', c.oid, 'INSERT')
        OR has_table_privilege('hablas_evo_stg_main', c.oid, 'UPDATE')
        OR has_table_privilege('hablas_evo_stg_main', c.oid, 'DELETE'))
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
        AND c.relname=ANY(ARRAY['schema_migrations','ar_internal_metadata','alembic_version','evo_core_community_schema_migrations'])), false) AS runtime_can_change_migrations,
      (SELECT count(*)::int FROM ar_internal_metadata WHERE key='hablas_evo_bootstrap_source' AND value LIKE $1) AS source_markers,
      (SELECT count(*)::int FROM alembic_version) AS alembic_versions,
      (SELECT count(*)::int FROM user_states WHERE app_name='hablas-infra-bootstrap') AS bootstrap_user_states,
      (SELECT count(*)::int FROM app_states WHERE app_name='hablas-infra-bootstrap') AS bootstrap_app_states`, [OWNER + '/%'])).rows[0];
    await client.query('ROLLBACK');
    if (row.role !== 'hablas_evo_stg_main_migrator' || row.schema !== 'public' || row.public_tables !== 110
        || row.runtime_can_ddl || row.runtime_can_use_evoflow || row.runtime_can_read_auth
        || !row.runtime_can_select || !row.runtime_can_insert || !row.runtime_can_update || !row.runtime_can_delete
        || row.runtime_can_change_migrations || row.source_markers !== 1 || row.alembic_versions !== 1
        || row.bootstrap_user_states || row.bootstrap_app_states) throw new Error('STATE');
    console.log('PASS: completed primary schema and runtime grants reconciled');
  } finally {
    await client.end().catch(() => {});
  }
}

main().catch(error => {
  const code = /^[0-9A-Z_]{2,40}$/.test(error.code || error.message) ? (error.code || error.message) : 'COMPLETION_CHECK';
  console.error('BLOCKED: primary completion verification failed (' + code + '); details suppressed');
  process.exitCode = 2;
});
