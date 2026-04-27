from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me"

    database_url: str = "postgresql://fundlens:fundlens_dev@localhost:5432/fundlens"
    redis_url: str = "redis://localhost:6379/0"

    enable_timescale: bool = False


settings = Settings()
