"""Shared pytest fixtures — no real database.

Sets env flags before app imports so unit tests never open Postgres for
schema init or background score refresh.
"""

import os

# Must be set before app.main is imported by any test module.
os.environ["SKIP_DB_INIT"] = "1"
# Separate from SKIP_DB_INIT: Compose uses SKIP_DB_INIT in Docker without
# disabling live score/reputation refresh after votes.
os.environ["SKIP_SCORE_REFRESH"] = "1"
# Avoid Redis walks/connects in unit tests (matches CI); individual tests can re-enable.
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:1/0")
