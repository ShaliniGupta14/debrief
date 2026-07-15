from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    git_sha: str = "dev"

    database_url: str
    database_url_sync: str
    redis_url: str = "redis://localhost:6379/0"

    # Comma-separated list; the frontend (a different origin even in prod,
    # Vercel vs. Railway) needs this to call the API from the browser at all.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    anthropic_api_key: str | None = None
    judge_model: str = "claude-sonnet-5"
    judge_sample_rate: float = 0.2


@lru_cache
def get_settings() -> Settings:
    return Settings()
