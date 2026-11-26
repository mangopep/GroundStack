"""Centralized configuration module for RAG Platform.

Uses Pydantic BaseSettings to load all environment variables from .env into typed Python classes.
Every other module should import from here instead of reading .env directly.
"""

from functools import lru_cache
from urllib.parse import quote

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# Individual Config Classes
# =============================================================================


class DatabaseConfig(BaseModel):
    """PostgreSQL database configuration."""

    host: str = "localhost"
    port: int = 5432
    user: str = "rag"
    password: str = ""
    db: str = "rag_platform"

    @property
    def url(self) -> str:
        """Return PostgreSQL connection URL."""
        user = quote(self.user, safe="")
        password = quote(self.password, safe="")
        return f"postgresql://{user}:{password}@{self.host}:{self.port}/{self.db}"


class OpenSearchConfig(BaseModel):
    """OpenSearch configuration."""

    host: str = "localhost"
    port: int = 9200
    index: str = "rag_chunks"

    @property
    def url(self) -> str:
        """Return OpenSearch connection URL."""
        return f"http://{self.host}:{self.port}"


class RedisConfig(BaseModel):
    """Redis configuration."""

    host: str = "localhost"
    port: int = 6379


class MinIOConfig(BaseModel):
    """MinIO (S3-compatible) configuration."""

    endpoint: str = "localhost:9000"
    access_key: str = ""
    secret_key: str = ""
    bucket: str = "rag-documents"


class OllamaConfig(BaseModel):
    """Ollama LLM configuration."""

    host: str = "http://localhost:11434"
    model: str = "llama3.2:1b"


class LangFuseConfig(BaseModel):
    """LangFuse observability configuration."""

    host: str = "http://localhost:3000"
    public_key: str | None = None
    secret_key: str | None = None


class AppConfig(BaseModel):
    """General application configuration."""

    api_key: str = ""
    log_level: str = "INFO"
    reranker_threshold: float = 0.7


# =============================================================================
# Main Settings Class (loads from environment)
# =============================================================================


class Settings(BaseSettings):
    """
    Main settings class that loads all configuration from environment variables.

    Uses .env file for local development and environment variables for production.
    Uses lru_cache on get_settings() to ensure config is loaded once.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "rag"
    postgres_password: str = ""
    postgres_db: str = "rag_platform"

    # OpenSearch
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_index: str = "rag_chunks"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "rag-documents"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"

    # LangFuse
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None

    # App
    api_key: str = ""
    log_level: str = "INFO"
    reranker_threshold: float = 0.7

    # =========================================================================
    # Computed Properties - Return Typed Config Objects
    # =========================================================================

    @property
    def database(self) -> DatabaseConfig:
        """Return DatabaseConfig instance."""
        return DatabaseConfig(
            host=self.postgres_host,
            port=self.postgres_port,
            user=self.postgres_user,
            password=self.postgres_password,
            db=self.postgres_db,
        )

    @property
    def opensearch(self) -> OpenSearchConfig:
        """Return OpenSearchConfig instance."""
        return OpenSearchConfig(
            host=self.opensearch_host, port=self.opensearch_port, index=self.opensearch_index
        )

    @property
    def redis(self) -> RedisConfig:
        """Return RedisConfig instance."""
        return RedisConfig(host=self.redis_host, port=self.redis_port)

    @property
    def minio(self) -> MinIOConfig:
        """Return MinIOConfig instance."""
        return MinIOConfig(
            endpoint=self.minio_endpoint,
            access_key=self.minio_access_key,
            secret_key=self.minio_secret_key,
            bucket=self.minio_bucket,
        )

    @property
    def ollama(self) -> OllamaConfig:
        """Return OllamaConfig instance."""
        return OllamaConfig(host=self.ollama_host, model=self.ollama_model)

    @property
    def langfuse(self) -> LangFuseConfig:
        """Return LangFuseConfig instance."""
        return LangFuseConfig(
            host=self.langfuse_host,
            public_key=self.langfuse_public_key,
            secret_key=self.langfuse_secret_key,
        )

    @property
    def app(self) -> AppConfig:
        """Return AppConfig instance."""
        return AppConfig(
            api_key=self.api_key,
            log_level=self.log_level,
            reranker_threshold=self.reranker_threshold,
        )


# =============================================================================
# Singleton Accessor
# =============================================================================


@lru_cache
def get_settings() -> Settings:
    """
    Get cached Settings instance.

    This function is decorated with @lru_cache to ensure config is loaded once
    and cached for subsequent calls. This avoids repeatedly reading from .env.

    Returns:
        Settings: Cached settings instance.

    Example:
        >>> from src.config import get_settings
        >>> settings = get_settings()
        >>> settings.database.url
        'postgresql://rag:@localhost:5432/rag_platform'
    """
    return Settings()
