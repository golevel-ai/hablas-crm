'use strict';

// Read-only verification with the actual node-postgres dependency from the build context.
// Never logs a password, connection URI, environment dump or unfiltered driver error.
const fs = require('node:fs');
const path = require('node:path');

async function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--help')) {
    console.log('Usage: node check_postgres_login.cjs --target PATH --pg-module BUILD_CONTEXT/node_modules/pg [--mode session|direct] [--dry-run]');
    return;
  }
  const get = (key, fallback) => { const i = argv.indexOf(key); return i < 0 ? fallback : argv[i + 1]; };
  const root = path.resolve(__dirname, '../..');
  const targetPath = get('--target');
  const modulePath = get('--pg-module');
  const mode = get('--mode', 'session');
  if (!targetPath || !modulePath || !['session', 'direct'].includes(mode)) throw new Error('INPUT');
  const target = JSON.parse(fs.readFileSync(targetPath, 'utf8'));
  const supabase = target.supabase;
  if (target.project !== 'hablas-evo-infra' || target.environment !== 'staging'
      || supabase.project_ref_owner_provided !== 'znxlfqctnezrropcbftw'
      || supabase.project_identity_status !== 'VERIFIED_PROJECT_URL_AND_DASHBOARD') throw new Error('TARGET');
  const connection = supabase[mode === 'session' ? 'main_connection' : 'direct_connection'];
  const expected = mode === 'session'
    ? { host: 'aws-0-us-east-1.pooler.supabase.com', user: 'postgres.znxlfqctnezrropcbftw' }
    : { host: 'db.znxlfqctnezrropcbftw.supabase.co', user: 'postgres' };
  if (connection.port !== 5432 || connection.host !== expected.host
      || connection.admin_username !== expected.user) throw new Error('HOST');
  if (argv.includes('--dry-run')) {
    console.log('NOT_EXECUTED: PostgreSQL login + fixed catalog queries inside READ ONLY transaction');
    return;
  }
  const resolvedModule = fs.realpathSync(modulePath);
  if (!resolvedModule.startsWith(path.join(root, '.ops-private/build/')) || !resolvedModule.endsWith('/node_modules/pg')) {
    throw new Error('DRIVER_PATH');
  }
  const { Client } = require(resolvedModule);
  const secretPath = path.join(root, '.ops-private/secrets', supabase.project_ref_owner_provided + '-admin.password');
  const info = fs.lstatSync(secretPath);
  if (!info.isFile() || info.isSymbolicLink() || (info.mode & 0o077) !== 0) throw new Error('SECRET_PERMISSIONS');
  const client = new Client({
    host: connection.host, port: connection.port, database: connection.database,
    user: connection.admin_username, password: fs.readFileSync(secretPath, 'utf8'),
    ssl: { ca: fs.readFileSync(path.join(root, 'infra/certs/supabase-root-2021.crt'), 'utf8'), rejectUnauthorized: true },
    connectionTimeoutMillis: 10000, query_timeout: 10000, statement_timeout: 10000,
    application_name: 'hablas-evo-readonly-preflight',
  });
  try {
    await client.connect();
    if (!client.connection.stream.authorized) throw new Error('TLS');
    await client.query('BEGIN READ ONLY');
    const identity = await client.query(`SELECT current_database() AS database, current_user AS role,
      current_setting('server_version') AS server_version,
      (SELECT count(*)::int FROM pg_tables WHERE schemaname='public') AS public_tables,
      EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector') AS vector_installed`);
    const permissions = await client.query('SELECT rolcreatedb, rolcreaterole, rolsuper FROM pg_roles WHERE rolname=current_user');
    await client.query('ROLLBACK');
    console.log(JSON.stringify({ status: 'PASS', scope: 'admin login and metadata only; no migrations',
      mode, host: connection.host, tls_verified: true, identity: identity.rows[0],
      admin_permissions: permissions.rows[0] }, null, 2));
  } finally {
    await client.end().catch(() => {});
  }
}

main().catch(error => {
  const code = /^[0-9A-Z_]{2,40}$/.test(error.code || error.message) ? (error.code || error.message) : 'CONNECTION_FAILED';
  console.error('BLOCKED: PostgreSQL verification failed (' + code + '); secret and driver details suppressed');
  process.exitCode = 2;
});
