# Configuración de aplicación 
import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, PostgresDsn, validator


class Settings(BaseSettings):
    # App
    APP_NAME: str = "PDF Generation System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # API
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = ["http://localhost:3000"]
    
    # Database
    DATABASE_URL: PostgresDsn
    SYNC_DATABASE_URL: Optional[str] = None
    
    @validator("SYNC_DATABASE_URL", pre=True)
    def assemble_sync_db_url(cls, v: Optional[str], values: dict) -> str:
        if isinstance(v, str):
            return v
        # Convertir async URL a sync URL para SQLAlchemy
        db_url = str(values.get("DATABASE_URL"))
        if db_url.startswith("postgresql+asyncpg://"):
            return db_url.replace("postgresql+asyncpg://", "postgresql://")
        return db_url
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 horas
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # File Uploads
    UPLOAD_FOLDER: str = "./uploads"
    OUTPUT_FOLDER: str = "./output"
    TEMP_FOLDER: str = "./temp"
    MAX_CSV_SIZE_MB: int = 50
    MAX_PDF_SIZE_MB: int = 10
    MAX_IMAGE_SIZE_MB: int = 2
    
    # Email (para futuras notificaciones)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Crear carpetas necesarias
for folder in [settings.UPLOAD_FOLDER, settings.OUTPUT_FOLDER, settings.TEMP_FOLDER]:
    os.makedirs(folder, exist_ok=True)