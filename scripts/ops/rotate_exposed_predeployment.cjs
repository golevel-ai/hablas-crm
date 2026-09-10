'use strict';
// One-time predeployment rotation after operator-only values were printed accidentally.
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const ROOT = path.resolve(__dirname, '../..');
const REF = 'znxlfqctnezrropcbftw';
const OWNER = 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9';
const ROLE = 'hablas_evo_stg_main_migrator';
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const literal = value => "'" + value.replaceAll("'", "''") + "'";
function secret(file) {
  const info = fs.lstatSync(file);
  if (!info.isFile() || info.isSymbolicLink() || info.mode & 0o077) throw new Error('SECRET_PERMISSIONS');
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
function fernetKey() {
  return crypto.randomBytes(32).toString('base64').replaceAll('+', '-').replaceAll('/', '_');
}
function stage(file, value) {
  const temporary = file + '.rotation';
  fs.writeFileSync(temporary, value, { mode: 0o600, flag: 'wx' });
  return temporary;
}
async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--self-test')) {
    const key = fernetKey();
    if (key.length !== 44 || !key.endsWith('=') || Buffer.from(key, 'base64url').length !== 32) throw new Error('FERNET_KEY');
    console.log('PASS: padded 32-byte Fernet key generation');
    return;
  }
  const arg = key => { const i = args.indexOf(key); return i < 0 ? null : args[i + 1]; };
  if (!arg('--target') || !arg('--pg-module') || !args.includes('--apply')) throw new Error('INPUT');
  execFileSync('python3', [path.join(ROOT, 'scripts/ops/ops.py'), 'validate', '--target', arg('--target')],
    { cwd: ROOT, stdio: 'pipe', timeout: 60000 });
  const target = read(arg('--target'));
  const manifest = read(path.join(ROOT, 'infra/deployment-manifest.yml'));
  const mainStatus = manifest.supabase.main.status;
  if (target.supabase.project_ref_owner_provided !== REF || manifest.ownership_marker !== OWNER
      || !['ROLES_READY_SCHEMA_PENDING', 'BOOTSTRAPPED_RUNTIME_VERIFIED'].includes(mainStatus)
      || manifest.coolify.app_uuid !== null) throw new Error('TARGET');
  const modulePath = fs.realpathSync(arg('--pg-module'));
  if (!modulePath.startsWith(path.join(ROOT, '.ops-private/build/')) || !modulePath.endsWith('/node_modules/pg')) throw new Error('DRIVER');
  const directory = path.join(ROOT, '.ops-private/secrets');
  const destination = path.join(directory, REF + '-main-migrator.password');
  const nextPassword = crypto.randomBytes(32).toString('hex');
  const passwordTemporary = stage(destination, nextPassword);
  const appFile = path.join(directory, 'application-keys.json');
  const app = read(appFile);
  if (app.owner !== OWNER || fs.lstatSync(appFile).mode & 0o077) throw new Error('APP_KEYS');
  const values = {};
  for (const key of ['JWT_SECRET_KEY', 'DOORKEEPER_JWT_SECRET_KEY', 'EVOAI_CRM_API_TOKEN',
                     'BOT_RUNTIME_SECRET', 'AUTH_APIKEY_INTEGRATION_LOCAL']) values[key] = crypto.randomBytes(32).toString('hex');
  values.SECRET_KEY_BASE = crypto.randomBytes(64).toString('hex');
  values.ENCRYPTION_KEY = fernetKey();
  const appTemporary = stage(appFile, JSON.stringify({ owner: OWNER, values }, null, 2) + '\n');
  const dataFile = path.join(ROOT, '.ops-private/coolify/data-env.json');
  const data = read(dataFile);
  if (data.owner !== OWNER || fs.lstatSync(dataFile).mode & 0o077) throw new Error('DATA_ENV');
  for (const key of Object.keys(data.values)) if (key.startsWith('EVO_OPS_')) delete data.values[key];
  for (const key of ['REDIS_PASSWORD', 'RABBITMQ_PASSWORD', 'RABBITMQ_ERLANG_COOKIE', 'CLICKHOUSE_PASSWORD']) {
    data.values[key] = crypto.randomBytes(32).toString('hex');
  }
  const dataTemporary = stage(dataFile, JSON.stringify(data, null, 2) + '\n');
  const connection = target.supabase.main_connection;
  if (connection.host !== 'aws-0-us-east-1.pooler.supabase.com' || connection.port !== 5432
      || connection.database !== 'postgres' || connection.admin_username !== 'postgres.' + REF) throw new Error('HOST');
  const { Client } = require(modulePath);
  const client = new Client({ host: connection.host, port: 5432, database: 'postgres', user: connection.admin_username,
    password: secret(path.join(directory, REF + '-admin.password')),
    ssl: { ca: fs.readFileSync(path.join(ROOT, 'infra/certs/supabase-root-2021.crt'), 'utf8'), rejectUnauthorized: true },
    connectionTimeoutMillis: 10000, query_timeout: 30000, statement_timeout: 30000,
    application_name: 'hablas-evo-staging-credential-rotation' });
  let locked = false;
  try {
    await client.connect();
    locked = (await client.query("SELECT pg_try_advisory_lock(hashtextextended('hablas-evo-infra/staging/database',0)) AS locked")).rows[0].locked;
    if (!locked) throw new Error('LOCK_BUSY');
    const baseline = (await client.query(`SELECT
      (SELECT count(*)::int FROM pg_tables WHERE schemaname='public') AS public_tables,
      (SELECT shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname=$1) AS owner`, [ROLE])).rows[0];
    const expectedTables = mainStatus === 'BOOTSTRAPPED_RUNTIME_VERIFIED' ? 110 : 0;
    if (baseline.public_tables !== expectedTables || baseline.owner !== OWNER) throw new Error('BASELINE');
    await client.query(`ALTER ROLE ${ROLE} PASSWORD ${literal(scram(nextPassword))}`);
    fs.renameSync(passwordTemporary, destination);
    fs.renameSync(appTemporary, appFile);
    fs.renameSync(dataTemporary, dataFile);
    console.log('PASS: exposed predeployment DB migrator, data-service and application values rotated; values suppressed');
  } finally {
    if (locked) await client.query("SELECT pg_advisory_unlock(hashtextextended('hablas-evo-infra/staging/database',0))").catch(() => {});
    await client.end().catch(() => {});
  }
}
main().catch(error => {
  console.error('BLOCKED: predeployment rotation failed (' + (/^[A-Z0-9_]+$/.test(error.message) ? error.message : 'ROTATION_FAILED') + '); values suppressed');
  process.exitCode = 2;
});
