from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
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
    output_dir: Path = Field(default=PROJECT_ROOT / "artifacts" / "renders", alias="OUTPUT_DIR")

    # Storage & Container Configuration (PostgreSQL + S3/MinIO Object Storage)
    database_url: Optional[str] = Field(
        default="postgresql://etsy_admin:etsy_secret_password@localhost:5434/etsy_pod_db",
        alias="DATABASE_URL",
    )
    s3_enabled: bool = Field(default=False, alias="S3_ENABLED")
    s3_endpoint_url: Optional[str] = Field(default="http://localhost:9000", alias="S3_ENDPOINT_URL")
    s3_access_key: Optional[str] = Field(default="minioadmin", alias="S3_ACCESS_KEY")
    s3_secret_key: Optional[str] = Field(default="minioadmin123", alias="S3_SECRET_KEY")
    s3_bucket_name: str = Field(default="etsy-renders", alias="S3_BUCKET_NAME")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")


    def missing_live_credentials(self) -> list[str]:
        """Env var names whose values are still the built-in placeholder defaults.

        A live (non dry-run) pipeline run calls OpenAI, Etsy and Printify, so
        all of these must be set to real values in .env or the environment.
        """
        required = (
            "openai_api_key",
            "etsy_api_keystring",
            "etsy_shared_secret",
            "printify_api_token",
            "printify_shop_id",
        )
        fields = type(self).model_fields
        return [
            fields[name].alias or name.upper()
            for name in required
            if getattr(self, name) == fields[name].default
        ]


class MissingCredentialsError(ValueError):
    """Raised when a live pipeline run is attempted with placeholder credentials."""


def get_settings() -> Settings:
    return Settings()
