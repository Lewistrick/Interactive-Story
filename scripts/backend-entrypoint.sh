#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
until uv run python -c "
import asyncio, sys
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def check():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__('sqlalchemy').text('SELECT 1'))
    finally:
        await engine.dispose()

asyncio.run(check())
" 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Running migrations..."
uv run alembic upgrade head

echo "Starting API..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
