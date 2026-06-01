from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str = ""
    database_path: str = "./data/traces.db"
    policy_file_path: str = "./policy_terms.json"
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    groq_text_model: str = "llama-3.1-8b-instant"
    groq_reasoning_model: str = "openai/gpt-oss-20b"
    groq_service_tier: str = "on_demand"
    max_retries: int = 3
    request_timeout: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
