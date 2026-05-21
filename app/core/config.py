from pathlib import Path
from typing import List
from urllib.parse import quote

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE, override=True)


class Settings(BaseSettings):
    PROJECT_NAME: str = "EventRank"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Database
    DATABASE_URL: str = ""
    MYSQL_DRIVER: str = "mysql+aiomysql"
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "eventrank"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    CREATE_DATABASE_TABLES_ON_STARTUP: bool = False

    # Storage backend: "memory" | "s3"
    STORAGE_BACKEND: str = "memory"

    # AWS S3 (optional)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_REGION: str = "us-east-1"

    # Redis (optional, for caching rankings)
    REDIS_URL: str = "redis://localhost:6379"

    # Scoring weights
    EVENT_SIMILARITY_WEIGHT: float = 0.25
    AFFINITY_WEIGHT: float = 0.25
    TICKET_WEIGHT: float = 0.15
    AGE_WEIGHT: float = 0.10
    PURCHASE_TIMING_WEIGHT: float = 0.10
    VIBE_WEIGHT: float = 0.08
    FREQUENCY_WEIGHT: float = 0.07

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def build_database_url(self):
        if self.DATABASE_URL:
            return self

        user = quote(self.MYSQL_USER, safe="")
        password = quote(self.MYSQL_PASSWORD, safe="")
        auth = user if not password else f"{user}:{password}"

        self.DATABASE_URL = (
            f"{self.MYSQL_DRIVER}://{auth}@"
            f"{self.MYSQL_HOST}:{self.MYSQL_PORT}/"
            f"{self.MYSQL_DATABASE}?charset=utf8mb4"
        )
        return self


settings = Settings()
