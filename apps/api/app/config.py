from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me"

    database_url: str = "postgresql://fundlens:fundlens_dev@localhost:5432/fundlens"
    redis_url: str = "redis://localhost:6379/0"

    enable_timescale: bool = False

    mfapi_base_url: str = "https://api.mfapi.in"
    amfi_nav_url: str = "https://www.amfiindia.com/spages/NAVAll.txt"
    auto_sync_mf_universe: bool = True
    auto_sync_navs: bool = True
    auto_sync_metrics: bool = True
    mfapi_timeout_seconds: int = 30


settings = Settings()
