# Configuración de base de datos 
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from typing import Generator

from .config import settings

# Motor sincrónico para SQLAlchemy (usamos sync para compatibilidad)
engine = create_engine(
    settings.SYNC_DATABASE_URL,
    poolclass=NullPool,  # Para evitar problemas con tablas dinámicas
    echo=settings.DEBUG,
    future=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    """
    Dependencia para obtener sesión de base de datos
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()