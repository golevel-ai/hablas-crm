"""Run Processor Alembic migrations with explicit asyncpg TLS options."""
import asyncio
import os
from urllib.parse import urlsplit, urlunsplit

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

from src.config.postgres_tls import async_connection_options


if os.environ.get('EVO_BOOTSTRAP_OWNER') != 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9':
    raise RuntimeError('Explicit staging bootstrap ownership required')


def upgrade(connection):
    config = Config('/app/alembic.ini')
    config.attributes['connection'] = connection
    command.upgrade(config, 'head')


async def main():
    dsn = os.environ['POSTGRES_CONNECTION_STRING']
    if os.environ.get('INFRA_LOCAL_SCHEMA_TEST') == 'true':
        parsed = urlsplit(dsn)
        if parsed.hostname != 'pg' or parsed.username != 'postgres' or parsed.query != 'sslmode=disable':
            raise RuntimeError('Local CI override cannot target a managed database')
        url = urlunsplit(('postgresql+asyncpg', parsed.netloc, parsed.path, '', ''))
        connect_args = {'ssl': False}
    else:
        url, connect_args = async_connection_options(dsn)
    engine = create_async_engine(url, connect_args=connect_args, pool_size=1, max_overflow=0)
    async with engine.begin() as connection:
        await connection.run_sync(upgrade)
    await engine.dispose()


asyncio.run(main())
print('PASS: Processor Alembic migrations completed with explicit connection options')
