'use strict';
const { Client } = require('pg');
const fs = require('node:fs');
const owner = 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9';
const key = "hashtextextended('hablas-evo-infra/staging/database',0)";
async function main() {
  if (process.env.EVO_BOOTSTRAP_OWNER !== owner
      || process.env.POSTGRES_HOST !== 'aws-0-us-east-1.pooler.supabase.com'
      || process.env.POSTGRES_USERNAME !== 'hablas_evo_stg_main_migrator.fizdiennudpyqrzmdukm') throw new Error('TARGET');
  const client = new Client({ host: process.env.POSTGRES_HOST, port: 5432, database: 'postgres',
    user: process.env.POSTGRES_USERNAME, password: process.env.POSTGRES_PASSWORD,
    ssl: { ca: fs.readFileSync('/ops/ca.crt', 'utf8'), rejectUnauthorized: true },
    connectionTimeoutMillis: 10000, query_timeout: 5000, statement_timeout: 5000 });
  await client.connect();
  const row = (await client.query(`SELECT pg_try_advisory_lock(${key}) AS locked`)).rows[0];
  if (!row.locked) { await client.end(); throw new Error('LOCK_BUSY'); }
  console.log('LOCKED');
  let closing = false;
  const close = async code => {
    if (closing) return;
    closing = true;
    clearInterval(timer);
    await client.query(`SELECT pg_advisory_unlock(${key})`).catch(() => {});
    await client.end().catch(() => {});
    process.exit(code);
  };
  const timer = setInterval(() => {
    client.query('SELECT 1').catch(() => { console.error('LOCK_LOST'); void close(2); });
  }, 10000);
  client.on('error', () => { console.error('LOCK_LOST'); void close(2); });
  process.stdin.resume();
  process.stdin.on('end', () => { void close(0); });
  process.on('SIGTERM', () => { void close(2); });
}
main().catch(() => { console.error('LOCK_FAILED'); process.exitCode = 2; });
