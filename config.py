from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_service_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_classify_fallback: bool = True
    enable_transaction_verification: bool = False
    dashboard_password: str = ""
    allow_no_auth: bool = False
    session_secret: str = ""
    data_dir: str = "data"


settings = Settings()

RULES_VERSION = "2026.09.20-1"
