from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://istory:istory_dev_password@localhost:5432/istory"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Quarantine Triggers
    QUARANTINE_STORY_SCORE_THRESHOLD: int = -5
    QUARANTINE_USER_REPUTATION_THRESHOLD: int = -20
    QUARANTINE_MIN_REPORTS: int = 3
    QUARANTINE_SPAM_CONFIDENCE: float = 0.8
    QUARANTINE_RAPID_POSTING_COUNT: int = 5

    # Content validation
    CONTENT_DUPLICATE_LOOKBACK: int = 200
    CONTENT_PROFANITY_ENABLED: bool = True
    CONTENT_PROFANITY_HIT_SCORE: float = 0.5

    # Hacked-account / velocity anomaly (established accounts only)
    VELOCITY_MIN_ACCOUNT_AGE_HOURS: float = 24.0
    VELOCITY_POST_BURST_LIMIT: int = 5
    VELOCITY_POST_WINDOW_SECONDS: int = 300
    VELOCITY_VOTE_BURST_LIMIT: int = 25
    VELOCITY_VOTE_WINDOW_SECONDS: int = 60

    # Moderator voting-pattern insights
    VOTING_PATTERN_LOOKBACK_HOURS: float = 24.0
    VOTING_PATTERN_DOWNVOTE_THRESHOLD: int = 15
    VOTING_PATTERN_DISMISS_DEFAULT_HOURS: float = 168.0  # 7 days
    VOTING_RING_MIN_SHARED_TARGETS: int = 5
    VOTING_RING_MAX_VOTES_SCAN: int = 20_000

    # Extra anti-spam gates on create/continue
    SIBLING_BRANCH_COOLDOWN_SECONDS: int = 3600
    MAX_CONCURRENT_OPEN_TREES: int = 3
    MIN_REPUTATION_CREATE_ROOT: int = 50

    # Redis rate limiting (IP / user sliding windows on write-heavy routes)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_AUTH_MAX: int = 20
    RATE_LIMIT_WRITE_MAX: int = 60

    # Redis story-tree cache
    CACHE_ENABLED: bool = True
    CACHE_TREE_TTL_SECONDS: int = 60

    # Scoring (Bayesian / Wilson / trust)
    BAYESIAN_PRIOR_MEAN: float = 0.0
    BAYESIAN_PRIOR_WEIGHT: float = 10.0
    WILSON_Z: float = 1.96
    TRUST_CONSTANT: int = 100
    SCORE_SCALE: int = 100
    REPUTATION_SCALE: int = 1000
    RAPID_POSTING_MIN_HOURS: float = 1.0

    WARN_DEFAULT_HOURS: float = 24.0

    # Application
    APP_NAME: str = "Interactive Story App"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True


settings = Settings()
