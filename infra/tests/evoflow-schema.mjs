// Disposable native PostgreSQL 17.6 on loopback only. No Supabase credentials read.
import EmbeddedPostgres from 'embedded-postgres';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const contextArg = process.argv[2];
if (!contextArg) throw new Error('Usage: node infra/tests/evoflow-schema.mjs GENERATED_EVOFLOW_CONTEXT');
const context = fs.realpathSync(contextArg);
assert.ok(context.startsWith(path.join(root, '.ops-private/build/')) && context.endsWith('/evoflow'));
const require = createRequire(path.join(context, 'package.json'));
const { DataSource } = require('typeorm');
const { postgresOptions } = require('./deployment-postgres.cjs');
const parent = path.join(root, '.ops-private');
fs.mkdirSync(parent, { recursive: true, mode: 0o700 });
const directory = fs.mkdtempSync(path.join(parent, 'pg-schema-test-'));
process.umask(0o077);
process.env.TMPDIR = directory;
const reservation = net.createServer();
await new Promise(resolve => reservation.listen(0, '127.0.0.1', resolve));
const port = reservation.address().port;
await new Promise(resolve => reservation.close(resolve));
let logs = '';
const database = new EmbeddedPostgres({
  databaseDir: path.join(directory, 'data'), user: 'test_owner', password: 'local-test-only',
  port, persistent: true, createPostgresUser: false,
  postgresFlags: ['-h', '127.0.0.1', '-c', 'shared_buffers=32MB', '-c', 'max_connections=20',
    '-c', 'unix_socket_directories=' + directory],
  onLog: text => { logs = (logs + text).slice(-4000); },
  onError: text => { logs = (logs + text).slice(-4000); },
});
let admin, migrations, runtime;
let success = false;
try {
  await database.initialise();
  await database.start();
  admin = database.getPgClient('postgres', '127.0.0.1');
  await admin.connect();
  const version = await admin.query('SHOW server_version');
  assert.match(version.rows[0].server_version, /^17\.6/);
  await admin.query(`
    CREATE SCHEMA extensions;
    CREATE EXTENSION pgcrypto SCHEMA extensions;
    CREATE EXTENSION pg_trgm SCHEMA extensions;
    CREATE EXTENSION "uuid-ossp" SCHEMA extensions;
    CREATE ROLE flow_migrator LOGIN PASSWORD 'local-flow-test';
    CREATE ROLE flow_runtime LOGIN PASSWORD 'local-flow-runtime-test';
    CREATE SCHEMA hablas_evoflow_production AUTHORIZATION flow_migrator;
    GRANT USAGE ON SCHEMA extensions TO flow_migrator, flow_runtime;
    CREATE TABLE public.contacts (id integer PRIMARY KEY, marker text);
    INSERT INTO public.contacts VALUES (1, 'preserved');
    CREATE TYPE public.journey_sessions_status_enum AS ENUM ('sentinel');
    CREATE TABLE public.journey_sessions (waiting_for text, variables text);
  `);
  const input = {
    POSTGRES_DB_HOST: '127.0.0.1', POSTGRES_DB_PORT: String(port), POSTGRES_DB_DATABASE: 'postgres',
    POSTGRES_DB_USERNAME: 'flow_migrator', POSTGRES_DB_PASSWORD: 'local-flow-test',
    POSTGRES_SSLMODE: 'verify-full', POSTGRES_DB_SCHEMA: 'hablas_evoflow_production', POSTGRES_POOL_MAX: '2',
  };
  const options = {
    ...postgresOptions(input),
    // Schema/ACL integration test is local-only. Real TLS is covered separately by test_tls.cjs.
    ssl: false,
    entities: [path.join(context, 'dist/**/*.entity.js')],
    migrations: [path.join(context, 'dist/database/migrations/*.js')],
    migrationsTransactionMode: 'each',
  };
  migrations = new DataSource(options);
  await migrations.initialize();
  assert.equal((await migrations.query('SELECT current_schema() AS schema'))[0].schema, 'hablas_evoflow_production');
  const applied = await migrations.runMigrations({ transaction: 'each' });
  assert.equal(applied.length, 17);
  assert.equal((await migrations.runMigrations({ transaction: 'each' })).length, 0);
  assert.deepEqual((await admin.query('SELECT * FROM public.contacts')).rows, [{ id: 1, marker: 'preserved' }]);
  assert.deepEqual((await admin.query("SELECT enum_range(NULL::public.journey_sessions_status_enum)::text AS values")).rows,
    [{ values: '{sentinel}' }]);
  assert.equal((await migrations.query("SELECT count(*)::int AS n FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='journey_sessions' AND column_name='waiting_for'"))[0].n, 1);
  await admin.query(`
    GRANT USAGE ON SCHEMA hablas_evoflow_production TO flow_runtime;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA hablas_evoflow_production TO flow_runtime;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA hablas_evoflow_production TO flow_runtime;
  `);
  runtime = new DataSource({ ...options, username: 'flow_runtime', password: 'local-flow-runtime-test', migrations: [] });
  await runtime.initialize();
  await runtime.query("INSERT INTO contacts (name) VALUES ('synthetic-flow-contact')");
  assert.equal((await runtime.query('SELECT count(*)::int AS n FROM contacts'))[0].n, 1);
  await assert.rejects(runtime.query('SELECT * FROM public.contacts'), error => error.code === '42501');
  await assert.rejects(runtime.query('CREATE TABLE forbidden_runtime_ddl(id integer)'), error => error.code === '42501');
  const source = JSON.parse(fs.readFileSync(path.join(context, 'hablas-build.json'), 'utf8'));
  const digest = crypto.createHash('sha256');
  for (const file of fs.readdirSync(path.join(context, 'dist/database/migrations')).filter(x => x.endsWith('.js')).sort()) {
    digest.update(file + '\0').update(fs.readFileSync(path.join(context, 'dist/database/migrations', file)));
  }
  const evidence = { status: 'PASS', scope: 'disposable local PostgreSQL schema isolation',
    postgres: version.rows[0].server_version, migrations: applied.length, rerun_applied: 0,
    public_sentinels_preserved: true, runtime_cross_schema_denied: true, runtime_ddl_denied: true,
    source_commit: source.source_commit, recipe_sha256: source.recipe_sha256,
    migrations_sha256: digest.digest('hex') };
  fs.writeFileSync(path.join(context, 'hablas-schema-test.json'), JSON.stringify(evidence, null, 2) + '\n', { mode: 0o600 });
  success = true;
  console.log(JSON.stringify(evidence));
} catch (error) {
  console.error('LOCAL SCHEMA TEST FAILED:', error);
  console.error('Local PostgreSQL diagnostics:', logs);
  process.exitCode = 1;
} finally {
  if (runtime?.isInitialized) await runtime.destroy();
  if (migrations?.isInitialized) await migrations.destroy();
  if (admin) await admin.end().catch(() => {});
  if (database.process) await database.stop();
  if (success) fs.rmSync(directory, { recursive: true });
  else console.error('Preserved local test evidence directory:', directory);
}
