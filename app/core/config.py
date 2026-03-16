from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Core
    app_name: str = "Tydline Core"
    environment: str = "development"

    # Database (Supabase Postgres URI, e.g. postgres:// or postgresql+asyncpg://)
    database_url: str

    # Supabase (for future auth/integration use)
    supabase_url: str | None = None
    supabase_anon_key: str | None = None

    # Postmark (email notifications)
    email_from: str | None = None
    postmark_server_token: str | None = None

    # Legacy SMTP (optional fallback)
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None

    whatsapp_api_key: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_webhook_secret: str | None = None
    whatsapp_proxy_url: str | None = None
    sms_api_key: str | None = None

    # Groq (AI alert generation + agent)
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    # Agent: Pydantic AI with Qwen 3 via Groq
    groq_model_agent: str = "qwen/qwen3-32b"

    # Mem0 (conversation/shipment memory for the agent)
    mem0_api_key: str | None = None

    # Langfuse (LLM observability and tracing)
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # API security (optional; if set, X-API-Key required on protected routes)
    api_key: str | None = None

    # CORS — comma-separated list of allowed origins, e.g. https://app.tydline.com
    # Defaults to no external origins (same-origin only). Use ["*"] only in dev.
    cors_origins: list[str] = []

    # ShipsGo container tracking API
    shipsgo_api_base_url: str = "https://api.shipsgo.com"
    shipsgo_api_key: str | None = None

    # Fallback generic tracking vars (optional; ShipsGo takes precedence)
    tracking_api_base_url: str | None = None
    tracking_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
