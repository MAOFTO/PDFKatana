from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MAX_UPLOAD_SIZE_MB: int = Field(default=100, validation_alias="MAX_UPLOAD_SIZE_MB")
    MAX_PAGES: int = Field(default=100, validation_alias="MAX_PAGES")
    TEMP_RETENTION_MIN: int = Field(default=60, validation_alias="TEMP_RETENTION_MIN")
    MAX_WORKERS: int = Field(default=2, validation_alias="MAX_WORKERS")
    API_KEYS: Optional[str] = Field(default=None, validation_alias="API_KEYS")
    LOG_LEVEL: str = Field(default="info", validation_alias="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
