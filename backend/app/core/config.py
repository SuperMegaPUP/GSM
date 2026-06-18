from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Oil Expert SaaS MVP"
    debug: bool = False

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "oiluser"
    db_password: str = "oilpass"
    db_name: str = "oil_saas"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "uploads"
    minio_use_ssl: bool = False

    # JWT
    jwt_secret: str = "super-secret-jwt-key-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h

    # LLM
    llm_base_url: str = "http://192.168.122.1:1234/v1"
    llm_model: str = "Qwen3.6-35B-A3B-Q8_0.gguf"
    llm_api_key: str = "not-needed"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.7
    llm_timeout: int = 60

    # Embeddings
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
