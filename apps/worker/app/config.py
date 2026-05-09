from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql://fundlens:fundlens_dev@localhost:5432/fundlens"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    mfapi_base_url: str = "https://api.mfapi.in"
    amfi_nav_url: str = "https://www.amfiindia.com/spages/NAVAll.txt"
    mfapi_timeout_seconds: int = 30
    health_alert_threshold: float = 50.0


settings = WorkerSettings()
