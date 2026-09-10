'use strict';

// Deployment-only PostgreSQL options, shared by the API and TypeORM migrator.
// node-postgres validates the peer hostname when rejectUnauthorized is true.
const fs = require('node:fs');

function positiveInteger(env, name, fallback, max) {
  const raw = env[name] || String(fallback);
  if (!/^[1-9][0-9]*$/.test(raw) || Number(raw) > max) {
    throw new Error(`${name} must be an integer between 1 and ${max}`);
  }
  return Number(raw);
}

function postgresOptions(env = process.env) {
  for (const name of ['POSTGRES_DB_HOST', 'POSTGRES_DB_USERNAME', 'POSTGRES_DB_PASSWORD', 'POSTGRES_DB_DATABASE']) {
    if (!env[name]?.trim()) throw new Error(`${name} is required`);
  }
  if (env.POSTGRES_SSLMODE !== 'verify-full') {
    throw new Error('POSTGRES_SSLMODE must be verify-full for this deployment');
  }
  if (env.POSTGRES_DB_SCHEMA !== 'hablas_evoflow_staging') {
    throw new Error('POSTGRES_DB_SCHEMA must be hablas_evoflow_staging');
  }
  const ssl = { rejectUnauthorized: true };
  if (env.PGSSLROOTCERT) ssl.ca = fs.readFileSync(env.PGSSLROOTCERT, 'utf8');
  return {
    type: 'postgres',
    host: env.POSTGRES_DB_HOST,
    port: positiveInteger(env, 'POSTGRES_DB_PORT', 5432, 65535),
    username: env.POSTGRES_DB_USERNAME,
    password: env.POSTGRES_DB_PASSWORD,
    database: env.POSTGRES_DB_DATABASE,
    schema: env.POSTGRES_DB_SCHEMA,
    installExtensions: false,
    synchronize: false,
    migrationsRun: false,
    logging: false,
    ssl,
    extra: {
      max: positiveInteger(env, 'POSTGRES_POOL_MAX', 5, 20),
      connectionTimeoutMillis: 10000,
      idleTimeoutMillis: 30000,
      options: '-c search_path=hablas_evoflow_staging,extensions',
    },
  };
}

module.exports = { postgresOptions };
