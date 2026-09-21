from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "campus"
    postgres_user: str = "campus"
    postgres_password: SecretStr = SecretStr("local-coursework-change-me")
    database_url: SecretStr | None = None
    db_pool_size: int = Field(10, ge=1, le=50)
    db_max_overflow: int = Field(5, ge=0, le=20)
    db_pool_timeout: float = Field(2, gt=0, le=10)
    db_statement_timeout_ms: int = Field(3000, ge=100, le=15000)
    request_timeout_seconds: float = Field(10, gt=0, le=60)
    log_file: str = "logs/app.jsonl"
    log_queue_size: int = Field(4096, ge=1, le=100000)
    fault_delay_enabled: bool = False
    fault_delay_ms: int = Field(500, ge=0, le=2000)
    fault_every_n_requests: int = Field(5, ge=1, le=1000)
    environment: str = "local"

    @model_validator(mode="after")
    def local_fault_only(self):
        if self.fault_delay_enabled and self.environment != "local":
            raise ValueError("Fault injection is allowed only in the local environment")
        return self

    def db_url(self) -> str | URL:
        if self.database_url:
            return self.database_url.get_secret_value()
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
