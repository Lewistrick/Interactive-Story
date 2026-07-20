"""Shared pytest fixtures — no real database.

Sets SKIP_DB_INIT so the FastAPI app never opens a Postgres connection
during unit tests.
"""

import os

# Must be set before app.main is imported by any test module.
os.environ["SKIP_DB_INIT"] = "1"
