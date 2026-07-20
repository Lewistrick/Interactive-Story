"""FastAPI application entrypoint."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, stories
from app.core.config import settings
from app.db.session import engine
from app.models import Base


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create tables on startup unless skipped (unit tests / migrations-only)."""
    if os.getenv("SKIP_DB_INIT") != "1":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(stories.router, prefix="/api/v1/stories", tags=["stories"])


@app.get("/")
async def root():
    """API root metadata."""
    return {"message": "Interactive Story API", "version": settings.APP_VERSION}


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "healthy"}
