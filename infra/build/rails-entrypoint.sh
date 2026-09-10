#!/bin/sh
set -eu

# Production dependencies are part of the image. Schema changes have a separate executor.
if [ "${RUN_MIGRATIONS:-}" != "false" ]; then
  printf '%s\n' 'RUN_MIGRATIONS must be false for application processes' >&2
  exit 2
fi
if [ "${PGSSLMODE:-}" != "verify-full" ]; then
  printf '%s\n' 'PGSSLMODE must be verify-full' >&2
  exit 2
fi
if [ -n "${COOKIE_DOMAIN:-}" ]; then
  printf '%s\n' 'COOKIE_DOMAIN must be unset for host-only staging sessions' >&2
  exit 2
fi
if [ "$#" -eq 0 ]; then
  printf '%s\n' 'An explicit runtime command is required' >&2
  exit 2
fi
mkdir -p tmp/pids
rm -f tmp/pids/server.pid
exec "$@"
