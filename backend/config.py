from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path, override=False)


class Settings(BaseSettings):
    e2b_api_key: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-3-flash"
    openrouter_api_key: str = ""
    openrouter_model: str = "moonshotai/kimi-k2.5"
    database_url: str = "sqlite+aiosqlite:///./vibehub.db"
    frontend_url: str = "http://localhost:5173"
    debug: bool = True
    langchain_tracing_v2: str = "false"
    langchain_api_key: str = ""
    langchain_project: str = "vibehub"

    model_config = {
        "env_file": str(_env_path),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
