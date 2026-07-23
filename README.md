# Interactive Story App

A collaborative storytelling platform where users write story parts one at a time, with branching narratives, voting, Bayesian/Wilson scoring, reputation-based posting limits, and anti-spam moderation.

## Quick start

```bash
docker compose up -d --build
```

Then open **http://localhost:8001** — the React UI, API, PostgreSQL, and Redis all run in Docker. No other install or config steps are required.

| Service   | Role                         | Host port |
|-----------|------------------------------|-----------|
| frontend  | React SPA + nginx reverse proxy | **8001** |
| backend   | FastAPI                      | internal  |
| postgres  | Database                     | internal  |
| redis     | Cache / rate limiting        | internal  |

Stop with `docker compose down`. Wipe data with `docker compose down -v`.

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Redis
- **Frontend**: React, TypeScript, Vite, TanStack Query, TailwindCSS, React Router
- **Package managers**: uv (Python), npm (frontend)
- **Migrations**: Alembic
- **Runtime**: Docker Compose

## Project Structure

```
istory/
├── app/                 # FastAPI backend
├── frontend/            # React SPA (served by nginx in Docker)
├── tests/               # Fast unit tests (mocked DB)
├── alembic/             # Migrations
├── scripts/             # Container entrypoints
├── docker-compose.yml   # Full stack
└── Dockerfile           # Backend image
```

## Available Endpoints

API is proxied at `http://localhost:8001/api/v1/...`. Docs: `http://localhost:8001/docs`. Health: `http://localhost:8001/health`.

### Authentication
- `POST /api/v1/auth/register` — returns user profile with reputation tier limits
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me` — current user plus tier limits (`tier_name`, length caps, `daily_part_limit`, `can_vote`, `can_create_root`, `parts_written_today`, …)

### Stories
- `GET /api/v1/stories/` — list root stories
- `GET /api/v1/stories/{id}` — get part (includes `user_vote` when logged in)
- `GET /api/v1/stories/{id}/children` — direct continuations (highest `vote_score` first)
- `GET /api/v1/stories/{id}/tree` — full subtree
- `POST /api/v1/stories/` — create root story (tier length + daily + min reputation + concurrent open-tree limits)
- `POST /api/v1/stories/{id}/continue` — add continuation (spacing + sibling-branch cooldown)
- `POST /api/v1/stories/{id}/vote` — vote (Novices can vote; same type toggles off)
- `DELETE /api/v1/stories/{id}/vote` — remove vote
- `DELETE /api/v1/stories/{id}` — author hard-deletes a leaf part (no continuations)
- `POST /api/v1/stories/{id}/report` — report a part (auto-quarantines after enough distinct reports)

### Users
- `GET /api/v1/users/{id}` — public profile (mods also see quarantine/block/vote counts)
- `GET /api/v1/users/{id}/parts` — authored parts (`sort=age|vote_score|recursive_score`); quarantined parts only when a moderator passes `include_quarantined=true`

### Moderator (requires `is_moderator=true`)
- `GET /api/v1/moderator/quarantine-queue` — open quarantine items
- `GET /api/v1/moderator/audit-log` — all quarantine log entries
- `POST /api/v1/moderator/{entity_type}/{entity_id}/allow` — lift quarantine (`USER` or `STORY_PART`)
- `POST /api/v1/moderator/{entity_type}/{entity_id}/remove` — permanently hide a story part (soft; no cascade delete)
- `POST /api/v1/moderator/users/{id}/block` — block user and quarantine their parts
- `POST /api/v1/moderator/users/{id}/unblock` — clear block + user quarantine (parts left for review)
- `POST /api/v1/moderator/users/{id}/warn` — temporary write quarantine + warning message (`WARN_DEFAULT_HOURS`, default 24h)
- `POST /api/v1/moderator/bulk` — bulk allow / remove / block on many queue items
- `GET /api/v1/moderator/voting-patterns` — heavy downvoters and vote-only accounts, sorted by severity
- `POST /api/v1/moderator/voting-patterns/dismiss` — hide a pattern flag (`duration_hours`: omit for `VOTING_PATTERN_DISMISS_DEFAULT_HOURS` / 7 days, `0` = forever)
- `GET /api/v1/moderator/users/{id}/votes` — votes cast by the user (UP/DOWN + target preview)
- `GET /api/v1/moderator/users/{id}/reputation-history` — reputation snapshots for sparklines

Promote a local moderator in Postgres:

```sql
UPDATE users SET is_moderator = true WHERE username = 'yourname';
```

## Scoring & reputation (Phase 3)

- **Story scores**: raw `vote_score` (up − down) for display; UI shows green ▲ for ≥0 and red ▼ with the absolute value when negative. Bayesian average + Wilson lower bound drive cached `recursive_score` with trust propagation (`trust = reputation / (reputation + 100)`).
- **User reputation**: Wilson aggregate of votes on authored parts, with rapid-posting penalty when consecutive parts are under 1 hour apart. Recalculated in the background after votes (and after creates). Docker sets `SKIP_DB_INIT=1` to skip `create_all` only — score refresh still runs. Unit tests use a separate `SKIP_SCORE_REFRESH=1` flag.
- **Tiers** (seeded): Novice → Apprentice → Storyteller → Master → Legend control teaser/content length, daily post quota, and spacing. Novices may vote from the start (`can_vote_threshold` 0); writing limits still grow with reputation. Starting a **root** story requires `MIN_REPUTATION_CREATE_ROOT` (default 50 / Apprentice); Novices can still continue others’ stories.
- **FAQ**: plain-language guide at `/faq` (linked from the header).

## Anti-spam & moderation (Phase 4)

- **Redis rate limits** on register/login and write routes (create, continue, vote, report); separate from tier daily quotas.
- **Auto-quarantine** when a part’s `vote_score` or a user’s reputation crosses env thresholds, when rapid posting hits `QUARANTINE_RAPID_POSTING_COUNT`, or when distinct reports reach `QUARANTINE_MIN_REPORTS`.
- **Content validation** on create/continue: reject duplicates and any URLs; auto-quarantine when blocklist spam confidence ≥ `QUARANTINE_SPAM_CONFIDENCE`.
- **Velocity anomalies**: established accounts (age ≥ `VELOCITY_MIN_ACCOUNT_AGE_HOURS`) that burst posts/votes are auto-quarantined for review; last-seen IP shifts are noted in the quarantine reason. (Forced password reset is not implemented yet.)
- **Warn user**: moderators can warn an account with a temporary write quarantine; the user sees the reason in the UI until `quarantine_until` (or an Allow).
- **Mod dashboard**: bulk allow/remove/block on the queue; Patterns tab for voting anomalies sorted by severity (heavy downvoters first; low-volume vote-only ranks lower); Allow pattern dismisses a flag for a timeout (`VOTING_PATTERN_DISMISS_DEFAULT_HOURS`, default 7 days) or forever (`duration_hours=0`); Warn/Block also remove that user from Patterns.
- **User profile** at `/users/:id` (linked from story authors and the header username): authored parts sorted by newest or highest scores; owners can hard-delete leaf parts (no branches); moderators also see votes cast and can quarantine/warn/block/unblock. Soft-removed parents no longer break child Story View — the path stops at the gap with a short note.
- **Extra anti-spam gates**: sibling-branch cooldown under the same parent (`SIBLING_BRANCH_COOLDOWN_SECONDS`); max concurrent non-quarantined root stories per user (`MAX_CONCURRENT_OPEN_TREES`); min reputation to create roots (`MIN_REPUTATION_CREATE_ROOT`).
- **Quarantined parts** are hidden from the public; moderators can still open them (banner on Story View). Quarantined users cannot post or vote.
- **Moderator UI** at `/moderator` (Header link when `is_moderator`).

## Local development (optional)

Only needed if you want to hack on code outside Docker.

### Backend
```bash
uv sync --group dev
cp .env.example .env
# Point DATABASE_URL at a local Postgres, or run only infra:
# docker compose up -d postgres redis
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Tests
Unit tests mock the database — no Postgres required:

```bash
uv sync --group dev
uv run pytest
uv run ruff check app tests
uv run ruff format app tests
uv run ty check
```

## Phase Status

- **Phase 1** — Foundation ✅
- **Phase 2** — Core story features + **Archive Parchment** UI (Wireframe C) ✅
- **Phase 3** — Scoring & reputation limits ✅
- **Phase 4** — Anti-spam & moderation ✅
- **Phase 5** — Search, polish, deployment

### UI design

The frontend uses the **Archive Parchment** theme (warm cream/amber, literary reading focus) with **Wireframe C** layout: dense Home lists and a path-on-top story view (ancestor spine → current part → branch choices). Style rules for agents: [`.cursor/rules/archive-parchment-ui.mdc`](.cursor/rules/archive-parchment-ui.mdc).

## License

MIT
