from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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

    # Application
    APP_NAME: str = "Interactive Story App"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
