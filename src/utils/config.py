from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: str = "sqlite:///instance/metrics.db"

    # Web Application Settings
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False

    # Collector Settings
    COLLECTION_INTERVAL: int = 60  # seconds
    UPLOAD_INTERVAL: int = 5  # seconds
    UPLOAD_BATCH_SIZE: int = 100
    MAX_QUEUE_SIZE: int = 1000

    # Device Settings
    DEVICE1_HOST: str = "localhost"
    DEVICE1_PORT: int = 8001
    DEVICE2_API_KEY: str = "test_key"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings() 