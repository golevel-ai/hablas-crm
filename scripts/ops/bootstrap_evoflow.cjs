'use strict';

// First installation only, into an absent schema of the explicitly approved project.
// A partial failure is retained for inspection; no DROP/reset/automatic retry.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const ROOT = path.resolve(__dirname, '../..');
const SCHEMA = 'hablas_evoflow_staging';
const MIGRATOR = 'hablas_evo_stg_flow_migrator';
const RUNTIME = 'hablas_evo_stg_flow';
const literal = value => "'" + value.replaceAll("'", "''") + "'";
const read = filename => JSON.parse(fs.readFileSync(filename, 'utf8'));

function saveManifest(manifest) {
  const destination = path.join(ROOT, 'infra/deployment-manifest.yml');
  const temporary = destination + '.tmp';
  fs.writeFileSync(temporary, JSON.stringify(manifest, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
  fs.renameSync(temporary, destination);
}

function readSecret(filename) {
  const info = fs.lstatSync(filename);
  if (!info.isFile() || info.isSymbolicLink() || (info.mode & 0o077)) throw new Error('SECRET_PERMISSIONS');
  return fs.readFileSync(filename, 'utf8');
}

function scram(password) {
  const salt = crypto.randomBytes(16);
  const salted = crypto.pbkdf2Sync(password, salt, 4096, 32, 'sha256');
  const clientKey = crypto.createHmac('sha256', salted).update('Client Key').digest();
  const stored = crypto.createHash('sha256').update(clientKey).digest('base64');
  const server = crypto.createHmac('sha256', salted).update('Server Key').digest('base64');
  return `SCRAM-SHA-256$4096:${salt.toString('base64')}$${stored}:${server}`;
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--help')) {
    console.log('Usage: node bootstrap_evoflow.cjs --target PATH --context GENERATED_EVOFLOW_CONTEXT --dry-run|--apply');
    return;
  }
  const arg = key => { const i = argv.indexOf(key); return i < 0 ? null : argv[i + 1]; };
  if (!arg('--target') || !arg('--context') || argv.includes('--apply') === argv.includes('--dry-run')) throw new Error('INPUT');
  execFileSync('python3', [path.join(ROOT, 'scripts/ops/ops.py'), 'validate', '--target', arg('--target')],
    { cwd: ROOT, stdio: 'pipe', timeout: 60000 });
  const target = read(arg('--target'));
  const manifest = read(path.join(ROOT, 'infra/deployment-manifest.yml'));
  const ref = target.supabase.project_ref_owner_provided;
  const owner = manifest.ownership_marker;
  if (ref !== 'znxlfqctnezrropcbftw' || target.supabase.isolation_decision !== 'OWNER_APPROVED_DEDICATED_STAGING_PROJECT'
      || owner !== 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9') throw new Error('OWNERSHIP');
  const context = fs.realpathSync(arg('--context'));
  if (!context.startsWith(path.join(ROOT, '.ops-private/build/')) || !context.endsWith('/evoflow')) throw new Error('CONTEXT');
  const source = read(path.join(context, 'hablas-build.json'));
  const proof = read(path.join(context, 'hablas-schema-test.json'));
  const version = read(path.join(ROOT, 'infra/versions.lock.yml'));
  const digest = crypto.createHash('sha256');
  for (const file of fs.readdirSync(path.join(context, 'dist/database/migrations')).filter(x => x.endsWith('.js')).sort()) {
    digest.update(file + '\0').update(fs.readFileSync(path.join(context, 'dist/database/migrations', file)));
  }
  if (proof.status !== 'PASS' || proof.migrations !== 17 || !proof.public_sentinels_preserved
      || !proof.runtime_cross_schema_denied || !proof.runtime_ddl_denied
      || proof.recipe_sha256 !== source.recipe_sha256 || proof.migrations_sha256 !== digest.digest('hex')
      || proof.source_commit !== version.submodules['evo-flow-community']) throw new Error('LOCAL_TEST_PROOF');
  for (const [relative, expected] of Object.entries(source.files_sha256)) {
    const file = path.resolve(context, relative);
    if (!file.startsWith(context + path.sep) || crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex') !== expected) {
      throw new Error('CONTEXT_CHANGED');
    }
  }
  const plan = { project_ref: ref, schema: SCHEMA, roles: [MIGRATOR, RUNTIME],
    extension_if_absent: 'pg_trgm in extensions', migrations: 17, source_commit: proof.source_commit,
    public_schema_action: 'none', cost: 'second included Free Plan project; no paid addon' };
  if (argv.includes('--dry-run')) {
    console.log(JSON.stringify({ status: 'NOT_EXECUTED', plan }, null, 2));
    return;
  }
  const { Client } = require(path.join(context, 'node_modules/pg'));
  const { DataSource } = require(path.join(context, 'node_modules/typeorm'));
  const { postgresOptions } = require(path.join(context, 'deployment-postgres.cjs'));
  const connection = target.supabase.main_connection;
  if (connection.host !== 'aws-0-us-east-1.pooler.supabase.com' || connection.port !== 5432
      || connection.database !== 'postgres' || connection.admin_username !== 'postgres.' + ref) throw new Error('CONNECTION_TARGET');
  const secretDir = path.join(ROOT, '.ops-private/secrets');
  const admin = new Client({
    host: connection.host, port: connection.port, database: connection.database, user: connection.admin_username,
    password: readSecret(path.join(secretDir, ref + '-admin.password')),
    ssl: { ca: fs.readFileSync(path.join(ROOT, 'infra/certs/supabase-root-2021.crt'), 'utf8'), rejectUnauthorized: true },
    application_name: 'hablas-evo-staging-bootstrap', connectionTimeoutMillis: 10000,
    query_timeout: 30000, statement_timeout: 30000,
  });
  let dataSource, locked = false, resourcesCreated = false;
  try {
    await admin.connect();
    if (!admin.connection.stream.authorized) throw new Error('TLS');
    locked = (await admin.query("SELECT pg_try_advisory_lock(hashtextextended('hablas-evo-infra/staging/database', 0)) AS locked")).rows[0].locked;
    if (!locked) throw new Error('MIGRATION_LOCK_BUSY');
    const before = await admin.query(`SELECT
      (SELECT count(*)::int FROM pg_namespace WHERE nspname=$1) AS schemas,
      (SELECT count(*)::int FROM pg_roles WHERE rolname=ANY($2)) AS roles,
      (SELECT count(*)::int FROM pg_tables WHERE schemaname='public') AS public_tables`, [SCHEMA, [MIGRATOR, RUNTIME]]);
    if (before.rows[0].schemas || before.rows[0].roles) {
      throw new Error('EXISTING_RESOURCES_REQUIRE_MANIFEST_RECONCILIATION');
    }
    if (before.rows[0].public_tables !== 0) throw new Error('PRIMARY_BASELINE_CHANGED');
    const secrets = {};
    for (const [kind, role] of [['migrator', MIGRATOR], ['runtime', RUNTIME]]) {
      const filename = path.join(secretDir, ref + '-flow-' + kind + '.password');
      if (fs.existsSync(filename)) throw new Error('EXISTING_SECRET_REQUIRES_REVIEW');
      secrets[kind] = crypto.randomBytes(32).toString('hex');
      fs.writeFileSync(filename, secrets[kind], { mode: 0o600, flag: 'wx' });
    }
    await admin.query('BEGIN');
    try {
      await admin.query(`CREATE ROLE ${MIGRATOR} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 2 PASSWORD ${literal(scram(secrets.migrator))}`);
      await admin.query(`CREATE ROLE ${RUNTIME} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 5 PASSWORD ${literal(scram(secrets.runtime))}`);
      await admin.query(`COMMENT ON ROLE ${MIGRATOR} IS ${literal(owner)}`);
      await admin.query(`COMMENT ON ROLE ${RUNTIME} IS ${literal(owner)}`);
      await admin.query(`CREATE SCHEMA ${SCHEMA}`);
      await admin.query(`COMMENT ON SCHEMA ${SCHEMA} IS ${literal(owner)}`);
      await admin.query(`GRANT USAGE, CREATE ON SCHEMA ${SCHEMA} TO ${MIGRATOR}`);
      await admin.query(`GRANT USAGE ON SCHEMA ${SCHEMA} TO ${RUNTIME}`);
      await admin.query(`GRANT USAGE ON SCHEMA extensions TO ${MIGRATOR}, ${RUNTIME}`);
      await admin.query('CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions');
      await admin.query('COMMIT');
      resourcesCreated = true;
    } catch (error) {
      await admin.query('ROLLBACK');
      throw error;
    }
    const schema = (await admin.query("SELECT oid, obj_description(oid, 'pg_namespace') AS owner FROM pg_namespace WHERE nspname=$1", [SCHEMA])).rows[0];
    const roles = (await admin.query("SELECT oid, rolname, shobj_description(oid, 'pg_authid') AS owner FROM pg_roles WHERE rolname=ANY($1)", [[MIGRATOR, RUNTIME]])).rows;
    manifest.supabase.evoflow = { status: 'SCHEMA_CREATED', schema: SCHEMA, schema_oid: schema.oid,
      roles, ownership_marker: owner, source_commit: proof.source_commit, recipe_sha256: proof.recipe_sha256 };
    manifest.secret_refs = [...new Set([...manifest.secret_refs,
      `local-file:.ops-private/secrets/${ref}-flow-migrator.password`,
      `local-file:.ops-private/secrets/${ref}-flow-runtime.password`])];
    saveManifest(manifest);
    const options = postgresOptions({ POSTGRES_DB_HOST: connection.host, POSTGRES_DB_PORT: '5432',
      POSTGRES_DB_DATABASE: 'postgres', POSTGRES_DB_USERNAME: MIGRATOR + '.' + ref,
      POSTGRES_DB_PASSWORD: secrets.migrator, POSTGRES_DB_SCHEMA: SCHEMA,
      POSTGRES_SSLMODE: 'verify-full', PGSSLROOTCERT: path.join(ROOT, 'infra/certs/supabase-root-2021.crt'),
      POSTGRES_POOL_MAX: '2' });
    dataSource = new DataSource({ ...options, entities: [path.join(context, 'dist/**/*.entity.js')],
      migrations: [path.join(context, 'dist/database/migrations/*.js')], migrationsTransactionMode: 'each' });
    await dataSource.initialize();
    if ((await dataSource.query('SELECT current_schema() AS schema'))[0].schema !== SCHEMA) throw new Error('SEARCH_PATH');
    const applied = await dataSource.runMigrations({ transaction: 'each' });
    if (applied.length !== 17 || await dataSource.showMigrations()) throw new Error('MIGRATION_RESULT');
    await dataSource.query(`GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ${SCHEMA} TO ${RUNTIME}`);
    await dataSource.query(`GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ${SCHEMA} TO ${RUNTIME}`);
    await dataSource.query(`REVOKE ALL ON ${SCHEMA}.migrations FROM ${RUNTIME}`);
    await dataSource.query(`ALTER DEFAULT PRIVILEGES IN SCHEMA ${SCHEMA} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${RUNTIME}`);
    await dataSource.query(`ALTER DEFAULT PRIVILEGES IN SCHEMA ${SCHEMA} GRANT USAGE, SELECT ON SEQUENCES TO ${RUNTIME}`);
    const after = (await admin.query("SELECT count(*)::int AS n FROM pg_tables WHERE schemaname='public'")).rows[0].n;
    if (after !== before.rows[0].public_tables) throw new Error('PRIMARY_SCHEMA_CHANGED');
    manifest.supabase.evoflow.status = 'MIGRATED_RUNTIME_LOGIN_PENDING';
    manifest.supabase.evoflow.migrations_applied = applied.length;
    saveManifest(manifest);
    console.log(JSON.stringify({ status: 'PASS', scope: 'EvoFlow schema bootstrap only', schema_oid: schema.oid,
      roles: roles.map(({ oid, rolname }) => ({ oid, rolname })), migrations_applied: applied.length,
      public_tables_before: before.rows[0].public_tables, public_tables_after: after }, null, 2));
  } catch (error) {
    if (resourcesCreated && manifest.supabase.evoflow) {
      manifest.supabase.evoflow.status = 'FAILED_REQUIRES_REVIEW';
      saveManifest(manifest);
    }
    throw error;
  } finally {
    if (dataSource?.isInitialized) await dataSource.destroy();
    if (locked) await admin.query("SELECT pg_advisory_unlock(hashtextextended('hablas-evo-infra/staging/database', 0))").catch(() => {});
    await admin.end().catch(() => {});
  }
}

main().catch(error => {
  const code = /^[A-Z0-9_]{2,80}$/.test(error.code || error.message) ? (error.code || error.message) : 'BOOTSTRAP_FAILED';
  console.error('BLOCKED: ' + code + '; no promotion, no destructive rollback, secrets suppressed');
  process.exitCode = 2;
});
