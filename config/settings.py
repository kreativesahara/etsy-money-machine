from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI Configuration
    openai_api_key: str = Field(default="sk-proj-mock-key", alias="OPENAI_API_KEY")
    image_model: str = Field(default="gpt-image-2", alias="IMAGE_MODEL")
    text_model: str = Field(default="gpt-4o", alias="TEXT_MODEL")

    # Printify Configuration
    printify_api_token: str = Field(default="mock-printify-token", alias="PRINTIFY_API_TOKEN")
    printify_shop_id: str = Field(default="12345678", alias="PRINTIFY_SHOP_ID")
    default_blueprint_id: int = Field(default=12, alias="DEFAULT_BLUEPRINT_ID")
    default_print_provider_id: int = Field(default=99, alias="DEFAULT_PRINT_PROVIDER_ID")

    # Etsy Open API v3 Configuration
    etsy_api_keystring: str = Field(default="mock-etsy-key", alias="ETSY_API_KEYSTRING")
    etsy_shared_secret: str = Field(default="mock-etsy-secret", alias="ETSY_SHARED_SECRET")
    etsy_shop_id: str = Field(default="87654321", alias="ETSY_SHOP_ID")
    etsy_oauth_access_token: str = Field(default="mock-etsy-oauth-token", alias="ETSY_OAUTH_ACCESS_TOKEN")

    # Pipeline Thresholds & Output
    min_render_confidence: float = Field(default=0.75, ge=0.0, le=1.0, alias="MIN_RENDER_CONFIDENCE")
    auto_publish_enabled: bool = Field(default=False, alias="AUTO_PUBLISH_ENABLED")
    output_dir: Path = Field(default=Path("artifacts/renders"), alias="OUTPUT_DIR")


def get_settings() -> Settings:
    return Settings()
