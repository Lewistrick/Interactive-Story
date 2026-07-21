"""FastAPI application entrypoint."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.v1 import auth, moderator, stories
from app.core.config import settings
from app.core.redis import close_redis
from app.db.session import engine
from app.models import Base


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create tables on startup unless skipped (unit tests / migrations-only)."""
    if os.getenv("SKIP_DB_INIT") != "1":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_redis()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Trust X-Forwarded-* from nginx so redirects keep the public host/port.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(stories.router, prefix="/api/v1/stories", tags=["stories"])
app.include_router(moderator.router, prefix="/api/v1/moderator", tags=["moderator"])


@app.get("/")
async def root():
    """API root metadata."""
    return {"message": "Interactive Story API", "version": settings.APP_VERSION}


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "healthy"}
