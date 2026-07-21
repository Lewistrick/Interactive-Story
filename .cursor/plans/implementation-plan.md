# Interactive Story App - Comprehensive Implementation Plan

This plan outlines the complete architecture, database design, scoring systems, and implementation approach for a collaborative interactive story platform with built-in anti-spam and moderation features.

## Project Overview

Build a collaborative storytelling platform where users write story parts one at a time, with branching narratives, voting systems, and sophisticated anti-spam mechanisms to prevent malicious attacks.

## Tech Stack

**Backend**
- Python 3.12+ with uv package manager
- FastAPI (async web framework)
- PostgreSQL 16+ with asyncpg
- SQLAlchemy 2.0 (async ORM)
- Alembic (database migrations)
- Pydantic (data validation)
- Redis (caching, rate limiting)

**Frontend**
- React 18+ with TypeScript
- Vite (build tool)
- React Router (routing)
- TanStack Query (data fetching)
- TailwindCSS + shadcn/ui (styling)
- Axios (HTTP client)

**Infrastructure**
- Docker Compose (local development)
- PostgreSQL container
- Redis container
- Nginx (reverse proxy)

## Database Schema & Object Models

### Core Models

**User**
- `id`: UUID (primary key)
- `username`: String (unique, indexed)
- `password_hash`: String (bcrypt)
- `reputation_score`: Integer (default: 0)
- `is_quarantined`: Boolean (default: false)
- `quarantine_reason`: Text (nullable)
- `quarantined_at`: Timestamp (nullable)
- `is_moderator`: Boolean (default: false)
- `is_blocked`: Boolean (default: false)
- `created_at`: Timestamp
- `updated_at`: Timestamp

**StoryPart**
- `id`: UUID (primary key)
- `parent_part_id`: UUID (foreign key to StoryPart, nullable for root stories)
- `author_id`: UUID (foreign key to User)
- `teaser`: String (max length based on user reputation)
- `content`: String (max length based on user reputation)
- `vote_score`: Integer (default: 0, upvotes - downvotes)
- `recursive_score`: Integer (cached sum of subtree votes)
- `is_quarantined`: Boolean (default: false)
- `quarantine_reason`: Text (nullable)
- `quarantined_at`: Timestamp (nullable)
- `depth_level`: Integer (calculated from root)
- `created_at`: Timestamp
- `updated_at`: Timestamp

**Vote**
- `id`: UUID (primary key)
- `user_id`: UUID (foreign key to User)
- `story_part_id`: UUID (foreign key to StoryPart)
- `vote_type`: Enum (UP, DOWN)
- `created_at`: Timestamp
- Unique constraint on (user_id, story_part_id)

**QuarantineLog**
- `id`: UUID (primary key)
- `entity_type`: Enum (USER, STORY_PART)
- `entity_id`: UUID
- `reason`: String
- `triggered_by`: String (system rule or moderator_id)
- `automatic`: Boolean
- `resolved_by_moderator_id`: UUID (nullable)
- `resolution_action`: Enum (ALLOWED, REMOVED, BLOCKED)
- `resolved_at`: Timestamp (nullable)
- `created_at`: Timestamp

**UserDailyLimit**
- `id`: UUID (primary key)
- `user_id`: UUID (foreign key to User)
- `date`: Date
- `parts_written`: Integer (default: 0)
- Unique constraint on (user_id, date)

**ReputationTier**
- `id`: UUID (primary key)
- `name`: String (e.g., "Novice", "Storyteller", "Master")
- `min_score`: Integer
- `max_teaser_length`: Integer
- `max_content_length`: Integer
- `daily_part_limit`: Integer
- `min_parts_between_own`: Integer
- `can_vote_threshold`: Integer

## Scoring System: Bayesian Reputation with Trust Propagation

**Story Part Score**
- Uses Bayesian average to handle low vote counts: (votes * average + prior * weight) / (votes + weight)
- Recursive score with trust propagation: descendants' scores are weighted by the trustworthiness of their authors
- Trust score = author's reputation / (author's reputation + 100)
- Wilson score interval for confidence bounds

**User Reputation**
- Uses Wilson score interval for statistical confidence
- Base reputation = Bayesian average of all authored parts' scores
- Trust network: reputation influenced by reputation of users who vote on your content
- Anti-spam: rapid posting penalty (exponential decay if posting < 1 hour apart)
- Recovery: reputation slowly recovers over time if no new violations

**Advantages**: Highly resistant to manipulation, statistically sound, handles low vote counts gracefully

## Anti-Spam Mechanisms

### Rate Limiting
- IP-based rate limiting on write-heavy endpoints (Redis-backed) — **Phase 4 MVP**
- Per-user daily posting limits based on reputation tier — **done (Phase 3)**
- Minimum time between posts / spacing — **done (Phase 3)**

### Content Validation
- Profanity filter and spam detection using basic NLP — **deferred**
- Duplicate content detection (prevent copy-paste spam) — **deferred**
- URL/link restrictions for new users — **deferred**

### Behavioral Analysis
- Detect voting patterns (mass downvoting, coordinated voting) — **deferred**
- Flag users who only vote without contributing — **deferred**
- Detect bot-like behavior (rapid successive actions) — **Phase 4 MVP** via Redis rate limits + rapid-post quarantine count
- **Hacked Account Detection** — **deferred** (velocity anomalies, IP/device fingerprinting, forced password reset)
- Emergency quarantine / freeze accounts — **Phase 4 MVP** via moderator block + auto-quarantine

### Spacing Rules
- Require N other users' parts between same user's parts (based on reputation) — **done (Phase 3)**
- Prevent creating multiple branches from same parent in short time — **deferred** (if not already covered by spacing)
- Limit concurrent active story trees per user — **deferred**

### Reputation Gates
- Minimum reputation to vote — **done (Phase 3; Novices can vote)**
- Minimum reputation to create root stories — **deferred** (tiers already gate length/daily)
- Higher reputation = higher limits (teaser/content length, daily posts) — **done (Phase 3)**

## Moderation Workflow

### Automatic Quarantine Triggers (Configurable) — Phase 4 MVP
All triggers are configurable via environment variables for easy tuning:
- `QUARANTINE_STORY_SCORE_THRESHOLD`: Story part score threshold (default: -5) — **MVP**
- `QUARANTINE_USER_REPUTATION_THRESHOLD`: User reputation threshold (default: -20) — **MVP**
- `QUARANTINE_MIN_REPORTS`: Minimum reports from different users (default: 3) — **MVP**
- `QUARANTINE_SPAM_CONFIDENCE`: Spam detection confidence threshold (default: 0.8) — **deferred** (no NLP yet)
- `QUARANTINE_RAPID_POSTING_COUNT`: Rapid posting violation count (default: 5) — **MVP**

**Rationale for defaults**:
- -5 story score: Represents significant community disapproval (roughly 5 more downvotes than upvotes)
- -20 user reputation: Indicates pattern of negative contributions across multiple parts
- These values are intentionally conservative to avoid false positives
- Can be tightened or loosened based on community behavior

### Quarantine Process — Phase 4 MVP
1. System automatically quarantines entity
2. Creates QuarantineLog entry with reason
3. Entity becomes invisible to normal users
4. Moderators see flagged items in dashboard

### Moderator Actions
- **View**: See quarantined content with full context (parent, children, voting history) — **MVP**
- **Allow**: Remove quarantine, restore visibility, log resolution — **MVP**
- **Remove**: Delete or permanently hide story part, log resolution — **MVP** (cascade policy: orphan children by nulling parent or soft-hide subtree — pick one in implementation)
- **Block User**: Quarantine user + set `is_blocked`, prevent new content — **MVP**
- **Warn User**: Send warning message, temporary quarantine — **deferred**

### Moderator Dashboard
- Queue of quarantined items sorted by newest / severity proxy — **MVP** (simple list)
- User reputation history graphs — **deferred**
- Voting pattern analysis — **deferred**
- Bulk actions for spam cleanup — **deferred**
- Audit log of all moderator actions — **MVP** (via QuarantineLog)

## Reputation Tier System (Example)

| Tier | Min Score | Teaser | Content | Daily Posts | Min Spacing | Can Vote |
|------|-----------|--------|---------|-------------|-------------|----------|
| Novice | 0 | 128 | 512 | 2 | 3 other parts | No |
| Apprentice | 50 | 192 | 768 | 3 | 2 other parts | Yes |
| Storyteller | 150 | 256 | 1024 | 5 | 1 other part | Yes |
| Master | 300 | 384 | 1536 | 10 | 0 | Yes |
| Legend | 500 | 512 | 2048 | 20 | 0 | Yes |

## API Architecture

### Authentication Endpoints
- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/logout
- GET /api/auth/me

### Story Endpoints
- GET /api/stories (list root stories with pagination, filters)
- GET /api/stories/:id (get story part with navigation)
- POST /api/stories (create new root story)
- POST /api/stories/:id/continue (create continuation)
- GET /api/stories/:id/tree (get full subtree)
- GET /api/stories/search (search by content/teaser)

### Voting Endpoints
- POST /api/stories/:id/vote (upvote/downvote)
- DELETE /api/stories/:id/vote (remove vote)

### User Endpoints
- GET /api/users/:id (user profile)
- GET /api/users/:id/stories (user's story parts)
- GET /api/users/me (current user profile)
- PUT /api/users/me (update profile)

### Moderator Endpoints
- GET /api/moderator/quarantine-queue
- POST /api/moderator/:entity_type/:entity_id/allow
- POST /api/moderator/:entity_type/:entity_id/remove
- POST /api/moderator/users/:id/block
- GET /api/moderator/audit-log

## Frontend Architecture

### Page Structure
- **Home**: Story discovery (popular, latest, search)
- **StoryView**: Read story part with teasers for continuations
- **CreateStory**: Form to write new story part
- **UserProfile**: User stats and story history
- **ModeratorDashboard**: Quarantine queue and actions
- **Auth**: Login/register forms

### State Management
- React Query for server state caching
- Context API for auth state
- Local state for UI interactions

### Key Components
- StoryCard (display story part with teaser)
- StoryTree (visual representation of branches)
- VotingButtons (upvote/downvote with counts)
- ReputationBadge (display user tier)
- QuarantineBanner (moderator-only warning)

## Implementation Phases (Iterative Approach)

### Phase 1: Foundation ✅
- Project setup (uv, React, PostgreSQL, Docker Compose)
- Database schema and migrations (Alembic)
- Basic authentication system (JWT, bcrypt)
- User model and reputation tiers
- Core API structure (FastAPI)
- Environment configuration system

**Deliverable**: Running backend with auth, database migrations, basic user management

### Phase 2: Core Story Features ✅
- Story CRUD operations
- Tree navigation and branching
- Basic voting system
- Home page with story listing
- Story reading interface
- React frontend setup with routing (Archive Parchment / Wireframe C)

**Deliverable**: Functional story reading/writing interface

### Phase 3: Scoring & Limits ✅
- Implement Bayesian scoring algorithm
- Trust propagation system
- Reputation-based limits (length, daily posts)
- Spacing rules enforcement
- User reputation calculations (background jobs)
- Wilson score intervals
- Novice voting enabled (`can_vote_threshold=0`)

**Deliverable**: Complete scoring system with reputation-based restrictions

### Phase 4: Anti-Spam & Moderation (MVP)

**Scope decision:** Ship an MVP only. Defer NLP/profanity, hacked-account detection, warn-user messages, and rich dashboard analytics to a later phase (see Deferred below).

#### Already done (scaffolding from Phases 1–3)

- DB fields: `User` / `StoryPart` quarantine columns; `User.is_moderator`, `User.is_blocked`
- `QuarantineLog` model + `quarantine_logs` table (unused at runtime)
- Env/config knobs: `QUARANTINE_STORY_SCORE_THRESHOLD`, `QUARANTINE_USER_REPUTATION_THRESHOLD`, `QUARANTINE_MIN_REPORTS`, `QUARANTINE_SPAM_CONFIDENCE`, `QUARANTINE_RAPID_POSTING_COUNT`
- Redis Compose service + `REDIS_URL` (not used by app code yet)
- List/children/tree CRUD hide quarantined story parts by default (`include_quarantined=False`)
- Blocked users denied login / auth-dependent actions
- Phase 3 daily post quotas + spacing (Postgres) — complementary to Redis rate limits, not a substitute

#### Still to do (MVP) — shipped on `feature/phase-4-moderation`

1. **Redis rate limiting** — done (`app/core/redis.py`, `app/core/rate_limit.py`)
2. **Automatic quarantine triggers** — done (`app/services/quarantine.py`; hooked after score refresh + create)
3. **User reports** — done (`reports` migration `003_reports`, `POST /stories/{id}/report`)
4. **Quarantine enforcement gaps** — done (GET gate, quarantined users cannot write/vote; mods see quarantined)
5. **Moderator API** — done (`/api/v1/moderator/*`)
6. **Frontend** — done (Report, QuarantineBanner, `/moderator`, FAQ/README)
7. **Tests** — done

#### Deferred (post–Phase 4 MVP)

- Content validation: profanity/NLP spam (`QUARANTINE_SPAM_CONFIDENCE`), duplicate-content detection, URL restrictions for new users
- Hacked-account detection: IP/device fingerprinting, sudden velocity anomalies, forced password reset
- Warn-user messaging / temporary quarantine UX
- Rich mod dashboard: reputation graphs, voting-pattern analysis, bulk spam cleanup
- Redis caching of story trees / reputations (performance; Phase 5 adjacent)

### Phase 5: Polish & Launch
- Search functionality
- Popular/latest algorithms
- UI/UX improvements
- Performance optimization (incl. Redis caching if still deferred)
- Testing and bug fixes
- Deployment setup
- Optionally absorb deferred Phase 4 items above

**Deliverable**: Production-ready application

## Security Considerations

- Password hashing with bcrypt
- JWT tokens with short expiration
- CSRF protection
- SQL injection prevention (parameterized queries)
- XSS protection (input sanitization)
- Rate limiting on all endpoints
- Input validation with Pydantic
- Secure headers (CORS, CSP)

## Performance Optimization

- Database indexing on frequently queried fields
- Redis caching for story trees and user reputations
- Background job for recursive score calculations
- Pagination for all list endpoints
- Lazy loading for story trees
- CDN for static assets

## Deployment Strategy

- Docker Compose for local development
- Environment-based configuration
- Database migration scripts
- CI/CD pipeline setup
- Monitoring and logging (Prometheus + Grafana)
- Backup strategy for PostgreSQL

## Next Steps

1. Implement Phase 4 MVP (Redis rate limits, auto-quarantine + reports, moderator API/UI) — see Phase 4 section above
2. Keep deferred anti-spam items (NLP, hacked-account, warn-user, rich dashboard) out of scope until after MVP ships
3. Then Phase 5: search, polish, deployment (and optionally absorb deferred moderation items)
