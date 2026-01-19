# Configuración de logs 
import sys
from loguru import logger, Logger
from typing import Dict, Any
import json
from datetime import datetime


def setup_logger(name: str) -> Logger:
    """
    Configura logger con formato estructurado
    """
    # Configurar formato
    format_str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Configurar handler para consola
    logger.remove()
    logger.add(
        sys.stdout,
        format=format_str,
        level="INFO",
        colorize=True
    )
    
    # Configurar handler para archivo
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # Rotar a media noche
        retention="30 days",  # Mantener 30 días
        compression="zip",
        format=format_str,
        level="DEBUG"
    )
    
    # Configurar handler para errores
    logger.add(
        "logs/error_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="90 days",
        compression="zip",
        format=format_str,
        level="ERROR",
        filter=lambda record: record["level"].name == "ERROR"
    )
    
    return logger.bind(name=name)


def log_structured(level: str, message: str, **kwargs):
    """
    Log estructurado para bitácora
    """
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        **kwargs
    }
    
    if level == "INFO":
        logger.info(json.dumps(log_data))
    elif level == "WARNING":
        logger.warning(json.dumps(log_data))
    elif level == "ERROR":
        logger.error(json.dumps(log_data))
    elif level == "CRITICAL":
        logger.critical(json.dumps(log_data))
    else:
        logger.debug(json.dumps(log_data))