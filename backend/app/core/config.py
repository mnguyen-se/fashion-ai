from typing import Optional

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL:      str = "sqlite:///./fashion_ai.db"
    OLLAMA_BASE_URL:   str = "http://localhost:11434"
    OLLAMA_MODEL:      str = "llama3.1"
    EMBEDDING_MODEL:   str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    CHROMA_PATH:       str = "./chroma_db"
    APP_ENV:           str = "development"
    SECRET_KEY:        str = "your-secret-key-here"
    CLIPDROP_API_KEY:  str = ""
    photoroom_api_key: Optional[str] = None
    GEMINI_API_KEY: str = ""

    @property
    def gemini_key_list(self) -> list[str]:
        return [k.strip() for k in self.GEMINI_API_KEYS.split(",") if k.strip()]

    google_application_credentials: str | None = None
    google_cloud_location: str = "us-central1"
    google_cloud_project: str = ""          # ← THÊM DÒNG NÀY
    internal_api_key: str = ""

    class Config:
        env_file = ".env"

settings = Settings()