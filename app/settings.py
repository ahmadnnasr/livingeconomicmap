
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Living Economic Map"
    app_env: str = "development"
    app_timezone: str = "America/New_York"
    database_url: str = "sqlite:///./lemp_local.db"
    dashboard_username: str = "admin"
    dashboard_password: str = "change-me"
    secret_key: str = "development-only-change-me"
    default_report_recipient: str = "nasrahmad0620@gmail.com"
    gmail_delivery_enabled: bool = False
    fred_api_key: str | None = None
    bls_api_key: str | None = None
    bea_api_key: str | None = None
    census_api_key: str | None = None
    eia_api_key: str | None = None
    benzinga_api_key: str | None = None
    public_conditions_key: str | None = None
    anthropic_api_key: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
