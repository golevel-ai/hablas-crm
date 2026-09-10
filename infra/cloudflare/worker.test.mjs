import assert from 'node:assert/strict';
import test from 'node:test';

import worker, { isBackendPath } from './worker.mjs';

const env = {
  ASSETS: {
    fetch: async () => new Response('<!doctype html>', {
      headers: { 'Content-Type': 'text/html' },
    }),
  },
};

test('backend paths cannot fall through to the SPA', async () => {
  for (const path of [
    '/.well-known/oauth-authorization-server',
    '/api/v1/users',
    '/cable',
    '/health/ready',
    '/healthz',
    '/link/campaign-code',
    '/metrics',
    '/oauth/token',
    '/public/api/v1/forms',
    '/rails/active_storage/blob',
    '/readyz',
    '/setup/bootstrap',
    '/setup/status',
    '/up',
    '/webhooks/test',
  ]) {
    assert.equal(isBackendPath(path), true);
    const response = await worker.fetch(new Request(`https://evo-stg.hablas.chat${path}`), env);
    assert.equal(response.status, 404);
    assert.equal(response.headers.get('content-type'), 'application/json');
    assert.equal(response.headers.get('cache-control'), 'no-store');
  }
});

test('frontend setup pages remain SPA routes', async () => {
  for (const path of ['/setup', '/setup/onboarding']) {
    assert.equal(isBackendPath(path), false);
    const response = await worker.fetch(new Request(`https://evo-stg.hablas.chat${path}`), env);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('content-type'), 'text/html');
  }
});

test('regular SPA responses receive restrictive security headers', async () => {
  const response = await worker.fetch(new Request('https://evo-stg.hablas.chat/conversations'), env);
  const csp = response.headers.get('content-security-policy');

  assert.equal(response.status, 200);
  assert.equal(response.headers.get('x-content-type-options'), 'nosniff');
  assert.equal(response.headers.get('x-frame-options'), 'SAMEORIGIN');
  assert.match(csp, /connect-src 'self' blob: https: wss:/);
  assert.doesNotMatch(csp, /(?:^|\s)ws:/);
  assert.match(csp, /frame-ancestors 'self'/);
});

test('widget remains embeddable without dropping the remaining CSP', async () => {
  const response = await worker.fetch(new Request('https://evo-stg.hablas.chat/widget/demo'), env);
  const csp = response.headers.get('content-security-policy');

  assert.equal(response.headers.get('x-frame-options'), null);
  assert.match(csp, /frame-ancestors \*/);
  assert.match(csp, /object-src 'none'/);
});

test('non-read methods are rejected before asset lookup', async () => {
  const response = await worker.fetch(new Request('https://evo-stg.hablas.chat/', { method: 'POST' }), env);
  assert.equal(response.status, 405);
});
