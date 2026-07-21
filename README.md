# Interactive Story App

A collaborative storytelling platform where users write story parts one at a time, with branching narratives, voting, Bayesian/Wilson scoring, and reputation-based posting limits.

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
- `GET /api/v1/auth/me` — current user plus tier limits (`tier_name`, length caps, `daily_part_limit`, `can_vote`, `parts_written_today`, …)

### Stories
- `GET /api/v1/stories/` — list root stories
- `GET /api/v1/stories/{id}` — get part (includes `user_vote` when logged in)
- `GET /api/v1/stories/{id}/children` — direct continuations (highest `vote_score` first)
- `GET /api/v1/stories/{id}/tree` — full subtree
- `POST /api/v1/stories/` — create root story (enforces tier length + daily limits)
- `POST /api/v1/stories/{id}/continue` — add continuation (also enforces spacing rules)
- `POST /api/v1/stories/{id}/vote` — vote (Novices can vote; same type toggles off)
- `DELETE /api/v1/stories/{id}/vote` — remove vote

## Scoring & reputation (Phase 3)

- **Story scores**: raw `vote_score` (up − down) for display; UI shows green ▲ for ≥0 and red ▼ with the absolute value when negative. Bayesian average + Wilson lower bound drive cached `recursive_score` with trust propagation (`trust = reputation / (reputation + 100)`).
- **User reputation**: Wilson aggregate of votes on authored parts, with rapid-posting penalty when consecutive parts are under 1 hour apart. Recalculated in the background after votes.
- **Tiers** (seeded): Novice → Apprentice → Storyteller → Master → Legend control teaser/content length, daily post quota, and spacing. Novices may vote from the start (`can_vote_threshold` 0); writing limits still grow with reputation.
- **FAQ**: plain-language guide at `/faq` (linked from the header).

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
- **Phase 4** — Anti-spam & moderation
- **Phase 5** — Search, polish, deployment

### UI design

The frontend uses the **Archive Parchment** theme (warm cream/amber, literary reading focus) with **Wireframe C** layout: dense Home lists and a path-on-top story view (ancestor spine → current part → branch choices). Style rules for agents: [`.cursor/rules/archive-parchment-ui.mdc`](.cursor/rules/archive-parchment-ui.mdc).

## License

MIT
