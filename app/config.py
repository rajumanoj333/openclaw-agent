from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_port: int = 8080
    log_level: str = "INFO"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    twilio_voice_from: str = ""
    # If set, voice-call status updates go here regardless of who called.
    # Useful in dev when the WhatsApp sandbox number != the test phone number.
    whatsapp_notify_to: str = ""

    openclaw_url: str = "http://localhost:18789"
    openclaw_token: str = ""

    google_application_credentials: str = ""
    gcp_project_id: str = ""

    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"

    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-2.5-flash-image"

    composio_api_key: str = ""

    @property
    def sarvam_key(self) -> str:
        return self.sarvam_api_key.strip()

    @property
    def gemini_key(self) -> str:
        return self.gemini_api_key.strip()

    postgres_user: str = "agent"
    postgres_password: str = ""
    postgres_db: str = "agentdb"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_host: str = "localhost"
    redis_port: int = 6379

    public_base_url: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
