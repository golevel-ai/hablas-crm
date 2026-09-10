'use strict';
const { Client } = require('pg');
const fs = require('node:fs');
async function main() {
  if (process.env.EVO_BOOTSTRAP_OWNER !== 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9') throw new Error('OWNER');
  const client = new Client({ host: process.env.POSTGRES_HOST, port: 5432, database: 'postgres',
    user: process.env.POSTGRES_USERNAME, password: process.env.POSTGRES_PASSWORD,
    ssl: { ca: fs.readFileSync('/ops/ca.crt', 'utf8'), rejectUnauthorized: true },
    connectionTimeoutMillis: 10000, query_timeout: 15000 });
  try {
    await client.connect();
    const identity = (await client.query('SELECT current_user AS role, current_schema() AS schema')).rows[0];
    if (identity.role !== 'hablas_evo_stg_main_migrator' || identity.schema !== 'public') throw new Error('ROLE');
    const role = 'hablas_evo_stg_main';
    await client.query('BEGIN');
    await client.query(`GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO ${role}`);
    await client.query(`GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO ${role}`);
    for (const table of ['schema_migrations', 'ar_internal_metadata', 'alembic_version', 'evo_core_community_schema_migrations']) {
      const exists = (await client.query('SELECT to_regclass($1) AS name', ['public.' + table])).rows[0].name;
      if (exists) await client.query(`REVOKE INSERT,UPDATE,DELETE ON public.${table} FROM ${role}`);
    }
    await client.query(`ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO ${role}`);
    await client.query(`ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO ${role}`);
    await client.query('COMMIT');
    const result = (await client.query("SELECT count(*)::int AS public_tables FROM pg_tables WHERE schemaname='public'")).rows[0];
    console.log(JSON.stringify({ status: 'PASS', scope: 'main runtime grants', ...result }));
  } finally { await client.end(); }
}
main().catch(() => { console.error('FAIL: runtime grants; details suppressed'); process.exitCode = 2; });
