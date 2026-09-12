'use strict';

const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const tls = require('node:tls');
const { execFileSync } = require('node:child_process');
const { postgresOptions } = require('../../infra/build/evoflow-postgres.cjs');

const input = {
  POSTGRES_DB_HOST: 'localhost', POSTGRES_DB_USERNAME: 'synthetic',
  POSTGRES_DB_PASSWORD: 'synthetic-test-only', POSTGRES_DB_DATABASE: 'synthetic',
  POSTGRES_SSLMODE: 'verify-full',
  POSTGRES_DB_SCHEMA: 'hablas_evoflow_production',
};
let directory, certificate, server, port;

before(async () => {
  const parent = path.resolve('.ops-private');
  fs.mkdirSync(parent, { recursive: true, mode: 0o700 });
  directory = fs.mkdtempSync(path.join(parent, 'tls-test-'));
  certificate = path.join(directory, 'ca.pem');
  const key = path.join(directory, 'key.pem');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
    '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost',
    '-keyout', key, '-out', certificate], { stdio: 'ignore', timeout: 10000 });
  fs.chmodSync(key, 0o600);
  server = tls.createServer({ key: fs.readFileSync(key), cert: fs.readFileSync(certificate) }, socket => socket.end());
  server.on('tlsClientError', () => {});
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  port = server.address().port;
});

after(async () => {
  if (server) await new Promise(resolve => server.close(resolve));
  if (directory) fs.rmSync(directory, { recursive: true, force: true });
});

function connect(options, servername = 'localhost') {
  return new Promise((resolve, reject) => {
    const socket = tls.connect({ host: '127.0.0.1', port, servername, ...options.ssl });
    socket.setTimeout(5000, () => { socket.destroy(); reject(new Error('TLS test timeout')); });
    socket.once('secureConnect', () => { socket.end(); resolve(socket.authorized); });
    socket.once('error', reject);
  });
}

test('rejects untrusted server instead of disabling verification', async () => {
  await assert.rejects(connect(postgresOptions(input)), /self.signed|certificate/i);
});
test('accepts the configured CA and matching hostname', async () => {
  assert.equal(await connect(postgresOptions({ ...input, PGSSLROOTCERT: certificate })), true);
});
test('rejects wrong hostname even with trusted CA', async () => {
  await assert.rejects(connect(postgresOptions({ ...input, PGSSLROOTCERT: certificate }), 'other.invalid'),
    /hostname|altnames/i);
});
test('rejects insecure or mistyped TLS modes', () => {
  for (const POSTGRES_SSLMODE of ['', 'disable', 'prefer', 'require', 'verify-ca', 'VERIFY-FULL']) {
    assert.throws(() => postgresOptions({ ...input, POSTGRES_SSLMODE }), /verify-full/);
  }
});
test('pool, port and migration configuration fail closed', () => {
  assert.throws(() => postgresOptions({ ...input, POSTGRES_POOL_MAX: '100' }), /POSTGRES_POOL_MAX/);
  assert.throws(() => postgresOptions({ ...input, POSTGRES_DB_PORT: '5432junk' }), /POSTGRES_DB_PORT/);
  const options = postgresOptions(input);
  assert.equal(options.extra.max, 5);
  assert.equal(options.synchronize, false);
  assert.equal(options.migrationsRun, false);
  assert.equal(options.installExtensions, false);
  assert.equal(options.schema, 'hablas_evoflow_production');
  assert.throws(() => postgresOptions({ ...input, POSTGRES_DB_SCHEMA: 'public' }), /POSTGRES_DB_SCHEMA/);
});
