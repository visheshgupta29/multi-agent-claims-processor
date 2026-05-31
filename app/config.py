from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = ""
    database_path: str = "./data/traces.db"
    policy_file_path: str = "./policy_terms.json"
    gemini_flash_model: str = "gemini-2.0-flash"
    gemini_pro_model: str = "gemini-2.5-flash"
    max_retries: int = 3
    request_timeout: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
