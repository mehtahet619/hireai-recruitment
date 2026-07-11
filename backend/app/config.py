import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


class Settings:
    def __init__(self) -> None:
        # Gemini settings
        self.gemini_api_key: str = (
            os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        ).strip()
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        
        # Mistral settings
        self.mistral_api_key: str = (
            os.getenv("MISTRAL_API_KEY") or ""
        ).strip()
        self.mistral_model: str = os.getenv("MISTRAL_MODEL", "mistral-large-latest").strip()
        
        # LLM selection
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
        
        env_mock = os.getenv("USE_MOCK_LLM")
        if env_mock is not None:
            self.use_mock: bool = env_mock.lower() in ("1", "true", "yes")
        else:
            self.use_mock = not bool(self.gemini_api_key or self.mistral_api_key)
            
        self.request_timeout: float = float(os.getenv("LLM_TIMEOUT", "60"))
        self.cors_origins = [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]
        self.valkey_url: str = os.getenv("VALKEY_URL", "").strip()
        self.google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        self.s3_endpoint: str = os.getenv("S3_ENDPOINT", "").strip()
        self.s3_bucket: str = os.getenv("S3_BUCKET", "").strip()
        self.s3_access_key_id: str = os.getenv("S3_ACCESS_KEY_ID", "").strip()
        self.s3_secret_access_key: str = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
        self.s3_region: str = os.getenv("S3_REGION", "auto").strip()
        self.s3_public_base: str = os.getenv("S3_PUBLIC_BASE", "").strip()

    @property
    def prompts_dir(self) -> Path:
        return Path(__file__).resolve().parent / "prompts"


@lru_cache
def get_settings() -> Settings:
    return Settings()
