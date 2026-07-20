import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def main() -> None:
    """Connect to local Postgres and print OK on success."""
    engine = create_async_engine(
        "postgresql+asyncpg://istory:istory_dev_password@localhost:5432/istory"
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        print("OK")
    finally:
        await engine.dispose()

asyncio.run(main())
