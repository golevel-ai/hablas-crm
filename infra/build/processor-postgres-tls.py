"""Translate the shared libpq DSN into strict asyncpg connection options."""
import ssl
from urllib.parse import parse_qsl, urlsplit, urlunsplit


def async_connection_options(dsn):
    parsed = urlsplit(dsn or '')
    if parsed.scheme != 'postgresql' or not parsed.hostname or not parsed.username:
        raise ValueError('POSTGRES_CONNECTION_STRING must be a PostgreSQL URL')
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    options = dict(pairs)
    if len(pairs) != len(options) or set(options) != {'sslmode', 'sslrootcert'}:
        raise ValueError('Expected only explicit sslmode and sslrootcert connection options')
    if options['sslmode'] != 'verify-full' or not options['sslrootcert']:
        raise ValueError('PostgreSQL TLS must verify the certificate and hostname')
    context = ssl.create_default_context(cafile=options['sslrootcert'])
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    url = urlunsplit(('postgresql+asyncpg', parsed.netloc, parsed.path, '', ''))
    return url, {'ssl': context, 'timeout': 10, 'command_timeout': 15}
