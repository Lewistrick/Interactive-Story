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
- IP-based rate limiting on all endpoints (Redis-backed)
- Per-user daily posting limits based on reputation tier
- Minimum time between posts (initially 1 hour, decreases with reputation)

### Content Validation
- Profanity filter and spam detection using basic NLP
- Duplicate content detection (prevent copy-paste spam)
- URL/link restrictions for new users

### Behavioral Analysis
- Detect voting patterns (mass downvoting, coordinated voting)
- Flag users who only vote without contributing
- Detect bot-like behavior (rapid successive actions)
- **Hacked Account Detection**:
  - Sudden behavior change analysis (posting patterns, voting patterns)
  - IP/device fingerprinting for anomaly detection
  - Velocity checks: if account suddenly posts at 10x previous rate, flag for review
  - Trust decay: if trusted user suddenly acts maliciously, their trust score drops rapidly
  - Emergency quarantine: moderators can instantly freeze accounts pending investigation
  - Password change required after suspicious activity detected

### Spacing Rules
- Require N other users' parts between same user's parts (based on reputation)
- Prevent creating multiple branches from same parent in short time
- Limit concurrent active story trees per user

### Reputation Gates
- Minimum reputation to vote (prevents sockpuppet voting)
- Minimum reputation to create root stories
- Higher reputation = higher limits (teaser/content length, daily posts)

## Moderation Workflow

### Automatic Quarantine Triggers (Configurable)
All triggers are configurable via environment variables for easy tuning:
- `QUARANTINE_STORY_SCORE_THRESHOLD`: Story part score threshold (default: -5)
- `QUARANTINE_USER_REPUTATION_THRESHOLD`: User reputation threshold (default: -20)
- `QUARANTINE_MIN_REPORTS`: Minimum reports from different users (default: 3)
- `QUARANTINE_SPAM_CONFIDENCE`: Spam detection confidence threshold (default: 0.8)
- `QUARANTINE_RAPID_POSTING_COUNT`: Rapid posting violation count (default: 5)

**Rationale for defaults**:
- -5 story score: Represents significant community disapproval (roughly 5 more downvotes than upvotes)
- -20 user reputation: Indicates pattern of negative contributions across multiple parts
- These values are intentionally conservative to avoid false positives
- Can be tightened or loosened based on community behavior

### Quarantine Process
1. System automatically quarantines entity
2. Creates QuarantineLog entry with reason
3. Entity becomes invisible to normal users
4. Moderators see flagged items in dashboard

### Moderator Actions
- **View**: See quarantined content with full context (parent, children, voting history)
- **Allow**: Remove quarantine, restore visibility, log resolution
- **Remove**: Delete story part (cascade to children or orphan them), log resolution
- **Block User**: Quarantine all user content, set user.is_blocked = true, prevent new content
- **Warn User**: Send warning message, temporary quarantine

### Moderator Dashboard
- Queue of quarantined items sorted by severity
- User reputation history graphs
- Voting pattern analysis
- Bulk actions for spam cleanup
- Audit log of all moderator actions

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

### Phase 1: Foundation
- Project setup (uv, React, PostgreSQL, Docker Compose)
- Database schema and migrations (Alembic)
- Basic authentication system (JWT, bcrypt)
- User model and reputation tiers
- Core API structure (FastAPI)
- Environment configuration system

**Deliverable**: Running backend with auth, database migrations, basic user management

### Phase 2: Core Story Features
- Story CRUD operations
- Tree navigation and branching
- Basic voting system
- Home page with story listing
- Story reading interface
- React frontend setup with routing

**Deliverable**: Functional story reading/writing interface

### Phase 3: Scoring & Limits
- Implement Bayesian scoring algorithm
- Trust propagation system
- Reputation-based limits (length, daily posts)
- Spacing rules enforcement
- User reputation calculations (background jobs)
- Wilson score intervals

**Deliverable**: Complete scoring system with reputation-based restrictions

### Phase 4: Anti-Spam & Moderation
- Configurable quarantine triggers
- Rate limiting implementation (Redis)
- Content validation and spam detection
- Hacked account detection
- Moderator dashboard
- Quarantine workflow

**Deliverable**: Full moderation system with automatic and manual controls

### Phase 5: Polish & Launch
- Search functionality
- Popular/latest algorithms
- UI/UX improvements
- Performance optimization
- Testing and bug fixes
- Deployment setup

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

1. Review hacked account mitigation strategies
2. Confirm configurable quarantine trigger approach
3. Approve iterative implementation phases
4. Begin Phase 1 implementation
