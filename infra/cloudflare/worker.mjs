const BACKEND_PATHS = [
  '/.well-known',
  '/api',
  '/cable',
  '/health',
  '/healthz',
  '/link',
  '/metrics',
  '/oauth',
  '/platform/api',
  '/public/api',
  '/rails',
  '/ready',
  '/readyz',
  '/up',
  '/webhooks',
  '/setup/activate',
  '/setup/bootstrap',
  '/setup/register',
  '/setup/status',
  '/setup/survey',
];

function isBackendPath(pathname) {
  return BACKEND_PATHS.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

function contentSecurityPolicy(widget) {
  return [
    "default-src 'self'",
    "script-src 'self' 'wasm-unsafe-eval' 'unsafe-inline' blob: https://connect.facebook.net https://www.googletagmanager.com https://www.google.com https://www.gstatic.com https://www.clarity.ms",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https:",
    "media-src 'self' blob: https:",
    "font-src 'self' data:",
    "worker-src 'self' blob:",
    "connect-src 'self' blob: https: wss:",
    "frame-src 'self' https:",
    `frame-ancestors ${widget ? '*' : "'self'"}`,
    "base-uri 'self'",
    "object-src 'none'",
  ].join('; ');
}

function jsonError(status, error) {
  return Response.json(
    { error },
    {
      status,
      headers: {
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
      },
    },
  );
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);

    if (isBackendPath(pathname)) {
      return jsonError(404, 'Backend routes are only available on the API hostname');
    }
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return jsonError(405, 'Method not allowed');
    }

    try {
      const response = await env.ASSETS.fetch(request);
      const headers = new Headers(response.headers);
      const widget = pathname === '/widget' || pathname.startsWith('/widget/');

      headers.set('Content-Security-Policy', contentSecurityPolicy(widget));
      headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
      headers.set('X-Content-Type-Options', 'nosniff');
      headers.set('X-Robots-Tag', 'noindex, nofollow');
      if (widget) {
        headers.delete('X-Frame-Options');
      } else {
        headers.set('X-Frame-Options', 'SAMEORIGIN');
      }

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    } catch (error) {
      console.error(JSON.stringify({
        message: 'static asset fetch failed',
        error: error instanceof Error ? error.message : String(error),
      }));
      return jsonError(500, 'Static asset unavailable');
    }
  },
};

export { isBackendPath };
