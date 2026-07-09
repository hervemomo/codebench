from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = None
    database_url: str = "postgresql+psycopg://cb:cb@db:5432/cb"
    redis_url: str = "redis://redis:6379/0"
    app_version: str = "0.1.0"

    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "codebench"
    s3_region: str = "us-east-1"

    def require_openai_api_key(self) -> str:
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to your .env file before making LLM calls."
            )
        return self.openai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
