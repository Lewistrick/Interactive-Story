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
