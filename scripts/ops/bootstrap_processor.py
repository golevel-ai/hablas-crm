"""Explicit Processor/ADK bootstrap, never imported by the application runtime."""
import asyncio
import os
from uuid import uuid4

from src.config.database import Base, engine
from src.models import models  # Register the same models the original create_all used.

if os.environ.get('EVO_BOOTSTRAP_OWNER') != 'hablas-evo-infra-staging-5fd09cad-c52d-40a9-b4af-f7a57f65bed9':
    raise RuntimeError('Explicit staging bootstrap ownership required')

# Preserve the original schema ownership: users belongs to Auth, Core tables must
# already exist. The remaining model definitions came from this locked Processor.
with engine.connect() as connection:
    from sqlalchemy import text
    if connection.execute(text('SELECT current_schema()')).scalar() != 'public':
        raise RuntimeError('Unexpected Processor schema')
    if connection.execute(text("SELECT to_regclass('public.users') IS NOT NULL AND to_regclass('public.evo_core_agents') IS NOT NULL")).scalar() is not True:
        raise RuntimeError('Auth and Core must be migrated first')
owned = [table for name, table in Base.metadata.tables.items()
         if name != 'users' and not name.startswith('evo_core_')]
Base.metadata.create_all(bind=engine, tables=owned, checkfirst=True)
engine.dispose()


async def prepare_adk():
    from google.adk.sessions import DatabaseSessionService
    from src.config.postgres_tls import async_connection_options
    dsn = os.environ['POSTGRES_CONNECTION_STRING']
    if os.environ.get('INFRA_LOCAL_SCHEMA_TEST') == 'true':
        from urllib.parse import urlsplit, urlunsplit
        parsed = urlsplit(dsn)
        if parsed.hostname != 'pg' or parsed.username != 'postgres' or parsed.query != 'sslmode=disable':
            raise RuntimeError('Local CI override cannot target a managed database')
        url = urlunsplit(('postgresql+asyncpg', parsed.netloc, parsed.path, '', ''))
        connect_args = {'ssl': False}
    else:
        url, connect_args = async_connection_options(dsn)
    service = DatabaseSessionService(db_url=url, connect_args=connect_args,
                                     pool_size=1, max_overflow=0, pool_pre_ping=True)
    session_id = str(uuid4())
    app, user = 'hablas-infra-bootstrap', 'bootstrap-probe'
    await service.create_session(app_name=app, user_id=user, session_id=session_id)
    await service.delete_session(app_name=app, user_id=user, session_id=session_id)
    # This is synthetic bootstrap metadata, not a customer identity or channel.
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    cleanup = create_async_engine(url, connect_args=connect_args, pool_size=1, max_overflow=0)
    async with cleanup.begin() as connection:
        await connection.execute(text('DELETE FROM user_states WHERE app_name=:app AND user_id=:user'), {'app': app, 'user': user})
        await connection.execute(text('DELETE FROM app_states WHERE app_name=:app'), {'app': app})
    await cleanup.dispose()


asyncio.run(prepare_adk())
print('PASS: explicit Processor models and ADK session schema bootstrap completed')
