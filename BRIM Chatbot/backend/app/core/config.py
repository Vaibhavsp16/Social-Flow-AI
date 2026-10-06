import json
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

# Which provider produces the chunk/query vectors. "auto" prefers OpenAI when the API key is
# usable and falls back to the local deterministic projection otherwise.
EMBEDDING_PROVIDER_AUTO = "auto"


class Settings(BaseSettings):
    PROJECT_NAME: str = "BRIM AI Backend"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "brim_super_secret_jwt_key_change_in_production_2026_xyz")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ALGORITHM: str = "HS256"

    # PostgreSQL Configuration
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "brim_ai_db")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "brim_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "brim_password_2026")
    
    DATABASE_URL: Union[str, None] = None

    # Embeddings / LLM
    OPENAI_API_KEY: Union[str, None] = None
    EMBEDDING_PROVIDER: str = EMBEDDING_PROVIDER_AUTO

    # CORS. Declared as a plain string so it can be given either as a comma separated list or
    # as a JSON array in .env; use `cors_origins` to read it as a list.
    BACKEND_CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5174,http://127.0.0.1:5174"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )

    @property
    def cors_origins(self) -> List[str]:
        """Allowed browser origins, accepting either a comma separated list or a JSON array."""
        raw = (self.BACKEND_CORS_ORIGINS or "").strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                return [str(o).strip() for o in parsed if str(o).strip()]
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        # Pin the psycopg2 driver explicitly. SQLAlchemy 2.1 resolves a bare
        # "postgresql://" URL to the psycopg (v3) dialect, which is not installed
        # by requirements.txt, so the connection would silently fail.
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

settings = Settings()
