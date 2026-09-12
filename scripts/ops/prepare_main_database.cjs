'use strict';
// Provision only new least-privilege roles and the required vector extension.
// Actual Rails/Core/Processor schema bootstrap is a separate, verified operation.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const ROOT = path.resolve(__dirname, '../..');
const ref = 'znxlfqctnezrropcbftw';
const roles = { migrator: 'hablas_evo_prod_main_migrator', runtime: 'hablas_evo_prod_main' };
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const literal = value => "'" + value.replaceAll("'", "''") + "'";
function secret(file) {
  const st = fs.lstatSync(file);
  if (!st.isFile() || st.isSymbolicLink() || (st.mode & 0o077)) throw new Error('SECRET_PERMISSIONS');
  return fs.readFileSync(file, 'utf8');
}
function scram(password) {
  const salt = crypto.randomBytes(16);
  const salted = crypto.pbkdf2Sync(password, salt, 4096, 32, 'sha256');
  const client = crypto.createHmac('sha256', salted).update('Client Key').digest();
  const stored = crypto.createHash('sha256').update(client).digest('base64');
  const server = crypto.createHmac('sha256', salted).update('Server Key').digest('base64');
  return `SCRAM-SHA-256$4096:${salt.toString('base64')}$${stored}:${server}`;
}
async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help')) { console.log('Usage: node prepare_main_database.cjs --target PATH --pg-module PATH --dry-run|--apply'); return; }
  const arg = key => { const i = args.indexOf(key); return i < 0 ? null : args[i + 1]; };
  if (!arg('--target') || !arg('--pg-module') || args.includes('--apply') === args.includes('--dry-run')) throw new Error('INPUT');
  execFileSync('python3', [path.join(ROOT, 'scripts/ops/ops.py'), 'validate', '--target', arg('--target')], { stdio: 'pipe', timeout: 60000 });
  const target = read(arg('--target'));
  const file = path.join(ROOT, 'infra/deployment-manifest.yml');
  const manifest = read(file);
  const flowOid = manifest.supabase.evoflow?.schema_oid;
  if (target.supabase.project_ref_owner_provided !== ref || target.environment !== 'production'
      || manifest.supabase.project_ref_owner_provided !== ref
      || manifest.supabase.evoflow?.status !== 'MIGRATED_RUNTIME_VERIFIED'
      || !Number.isInteger(flowOid)) throw new Error('TARGET');
  if (args.includes('--dry-run')) {
    console.log(JSON.stringify({ status: 'NOT_EXECUTED', project_ref: ref, roles, main_schema: 'public',
      extension: 'vector in extensions', existing_tables_action: 'none' }, null, 2));
    return;
  }
  const modulePath = fs.realpathSync(arg('--pg-module'));
  if (!modulePath.startsWith(path.join(ROOT, '.ops-private/build/')) || !modulePath.endsWith('/node_modules/pg')) throw new Error('DRIVER');
  const { Client } = require(modulePath);
  const connection = target.supabase.main_connection;
  if (connection.host !== 'aws-0-us-east-1.pooler.supabase.com' || connection.admin_username !== 'postgres.' + ref) throw new Error('HOST');
  const directory = path.join(ROOT, '.ops-private/secrets');
  const client = new Client({ host: connection.host, port: 5432, database: 'postgres', user: connection.admin_username,
    password: secret(path.join(directory, ref + '-admin.password')),
    ssl: { ca: fs.readFileSync(path.join(ROOT, 'infra/certs/supabase-root-2021.crt'), 'utf8'), rejectUnauthorized: true },
    connectionTimeoutMillis: 10000, query_timeout: 30000, statement_timeout: 30000,
    application_name: 'hablas-evo-production-main-access' });
  let locked = false;
  try {
    await client.connect();
    if (!client.connection.stream.authorized) throw new Error('TLS');
    locked = (await client.query("SELECT pg_try_advisory_lock(hashtextextended('hablas-evo-infra/production/database',0)) AS locked")).rows[0].locked;
    if (!locked) throw new Error('LOCK_BUSY');
    const before = (await client.query(`SELECT
      (SELECT count(*)::int FROM pg_roles WHERE rolname=ANY($1)) AS existing_roles,
      (SELECT count(*)::int FROM pg_tables WHERE schemaname='public') AS public_tables,
      (SELECT oid FROM pg_namespace WHERE nspname='hablas_evoflow_production') AS flow_oid,
      (SELECT count(*)::int FROM hablas_evoflow_production.migrations) AS flow_migrations`, [Object.values(roles)])).rows[0];
    if (before.existing_roles || before.public_tables || before.flow_oid !== flowOid || before.flow_migrations !== 17) throw new Error('BASELINE_OR_NAME_COLLISION');
    const passwords = {};
    for (const kind of Object.keys(roles)) {
      const destination = path.join(directory, ref + '-prod-main-' + kind + '.password');
      if (fs.existsSync(destination)) throw new Error('SECRET_EXISTS_REQUIRES_REVIEW');
      passwords[kind] = crypto.randomBytes(32).toString('hex');
      fs.writeFileSync(destination, passwords[kind], { mode: 0o600, flag: 'wx' });
    }
    await client.query('BEGIN');
    try {
      for (const kind of Object.keys(roles)) {
        const name = roles[kind];
        const limit = kind === 'migrator' ? 3 : 40;
        await client.query(`CREATE ROLE ${name} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT ${limit} PASSWORD ${literal(scram(passwords[kind]))}`);
        await client.query(`COMMENT ON ROLE ${name} IS ${literal(manifest.ownership_marker)}`);
        await client.query(`ALTER ROLE ${name} IN DATABASE postgres SET search_path TO public, extensions`);
      }
      await client.query(`GRANT USAGE, CREATE ON SCHEMA public TO ${roles.migrator}`);
      await client.query(`GRANT USAGE ON SCHEMA public, extensions TO ${roles.migrator}, ${roles.runtime}`);
      await client.query('CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions');
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    const observed = (await client.query("SELECT oid,rolname,rolsuper,rolcreatedb,rolcreaterole,rolconnlimit,shobj_description(oid,'pg_authid') AS owner FROM pg_roles WHERE rolname=ANY($1)", [Object.values(roles)])).rows;
    const vector = (await client.query("SELECT e.extversion,n.nspname AS schema FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'")).rows[0];
    manifest.supabase.main = { status: 'ROLES_READY_SCHEMA_PENDING', schema: 'public', roles: observed, vector };
    for (const kind of Object.keys(roles)) manifest.secret_refs.push(`local-file:.ops-private/secrets/${ref}-prod-main-${kind}.password`);
    const temporary = file + '.tmp';
    fs.writeFileSync(temporary, JSON.stringify(manifest, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
    fs.renameSync(temporary, file);
    console.log(JSON.stringify({ status: 'PASS', scope: 'new main roles and vector only', roles: observed, vector,
      public_tables_before: 0, flow_migrations_preserved: 17 }, null, 2));
  } finally {
    if (locked) await client.query("SELECT pg_advisory_unlock(hashtextextended('hablas-evo-infra/production/database',0))").catch(() => {});
    await client.end().catch(() => {});
  }
}
main().catch(error => {
  const code = /^[A-Z0-9_]{2,80}$/.test(error.code || error.message) ? (error.code || error.message) : 'PREPARATION_FAILED';
  console.error('BLOCKED: ' + code + '; secrets suppressed, no destructive rollback');
  process.exitCode = 2;
});
