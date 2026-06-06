"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for all external services and app settings."""

    # LLM Providers
    dashscope_api_key: str = ""
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Map & GIS Services
    amap_api_key: str = ""
    ors_api_key: str = ""

    # Weather Service
    qweather_api_key: str = ""
    qweather_api_host: str = "devapi.qweather.com"

    # App Settings
    app_env: str = "development"
    log_level: str = "INFO"
    showcase_mode: bool = False
    # Runtime provider selection is governed by LLMProviderFactory.get_provider_order()
    # / invoke_with_fallback() (the orchestrator's only LLM entry point). This value is
    # only consulted by get_model(provider=None); in the demo env Gemini is primary and
    # DeepSeek is the fallback.
    default_llm_provider: str = "gemini"

    # Thinking Mode (DeepSeek)
    thinking_enabled: bool = True
    thinking_effort: str = "medium"  # Options: "low", "medium", "high"

    # Default home location (望京 SOHO, Beijing)
    default_home_lng: float = 116.481
    default_home_lat: float = 39.998

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
