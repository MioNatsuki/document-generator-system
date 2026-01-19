# Configuración frontend 
import os
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuración de la aplicación frontend"""
    
    # Directorios
    BASE_DIR = Path(__file__).parent.parent
    APP_DIR = BASE_DIR / "frontend"
    BACKEND_DIR = BASE_DIR / "backend"
    
    # API
    API_BASE_URL = "http://localhost:8000"
    API_TIMEOUT = 30
    
    # Aplicación
    APP_NAME = "Combinación de Correspondencia Automatizada"
    APP_VERSION = "1.0.0"
    
    # UI
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    
    # Colores (paleta Madolche/Yummies)
    COLORS: Dict[str, str] = {
        # Colores principales de la paleta
        "color1": "#ffabab",  # Rosa pastel
        "color2": "#ffdaab",  # Melocotón pastel
        "color3": "#ddffab",  # Verde menta pastel
        "color4": "#abe4ff",  # Azul cielo pastel
        "color5": "#d9abff",  # Lila pastel
        
        # Colores utilitarios
        "primary": "#4a6fa5",   # Azul principal
        "secondary": "#6b5b95", # Morado secundario
        "success": "#88b04b",   # Verde éxito
        "warning": "#ff6b35",   # Naranja advertencia
        "danger": "#c44569",    # Rojo peligro
        "info": "#17a2b8",      # Azul info
        "light": "#f8f9fa",     # Gris claro
        "dark": "#343a40",      # Gris oscuro
        
        # Variantes pastel
        "pastel_pink": "#ffc9d6",
        "pastel_peach": "#ffdfc4",
        "pastel_mint": "#d4f1c5",
        "pastel_sky": "#c4e8ff",
        "pastel_lavender": "#e6d4ff",
        
        # Fondo y texto
        "bg_light": "#fff9f9",
        "bg_dark": "#2d3748",
        "text_light": "#f8f9fa",
        "text_dark": "#212529",
    }
    
    # Fuentes
    FONTS = {
        "main": "Segoe UI",
        "fallback": ["Arial", "Helvetica", "sans-serif"],
        "monospace": "Consolas, Monaco, monospace"
    }
    
    # Tamaños de fuente
    FONT_SIZES = {
        "xs": "9px",
        "sm": "11px",
        "base": "13px",
        "lg": "15px",
        "xl": "18px",
        "2xl": "22px",
        "3xl": "28px"
    }
    
    @classmethod
    def ensure_directories(cls):
        """Crear directorios necesarios"""
        directories = [
            cls.BASE_DIR / "output",
            cls.BASE_DIR / "uploads",
            cls.BASE_DIR / "temp",
            cls.BASE_DIR / "logs"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# Instancia global de configuración
config = Config()