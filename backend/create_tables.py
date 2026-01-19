# Script creación de tablas 
#!/usr/bin/env python3
"""
Script para crear todas las tablas de la base de datos
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, DDL
from sqlalchemy.schema import CreateSchema

from app.database import engine, Base
from app.models import (
    Usuario, Proyecto, ProyectoUsuario, Plantilla,
    EmisionTemp, EmisionFinal, EmisionAcumulada, Bitacora
)
from app.config import settings
from app.core.padron_manager import PadronManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_tables():
    """
    Crea todas las tablas del sistema
    """
    logger.info("Iniciando creación de tablas...")
    
    try:
        # Crear esquema si no existe
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
            conn.commit()
        
        # Crear tablas base
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas base creadas exitosamente")
        
        # Crear usuario superadmin inicial
        create_initial_superadmin()
        
        # Crear índices adicionales
        create_additional_indexes()
        
        logger.info("¡Base de datos inicializada exitosamente!")
        
    except Exception as e:
        logger.error(f"Error creando tablas: {str(e)}")
        raise


def create_initial_superadmin():
    """
    Crea usuario superadmin inicial
    """
    from app.auth import get_password_hash
    from app.models import Usuario
    from sqlalchemy.orm import Session
    
    logger.info("Creando usuario superadmin inicial...")
    
    db = Session(bind=engine)
    
    try:
        # Verificar si ya existe
        existing = db.query(Usuario).filter(
            Usuario.username == 'superadmin'
        ).first()
        
        if existing:
            logger.info("Usuario superadmin ya existe")
            return
        
        # Crear usuario
        superadmin = Usuario(
            username='superadmin',
            email='superadmin@system.com',
            hashed_password=get_password_hash('Admin123!'),
            nombre_completo='Super Administrador',
            rol='SUPERADMIN',
            is_active=True
        )
        
        db.add(superadmin)
        db.commit()
        
        logger.info("Usuario superadmin creado exitosamente")
        logger.info("Credenciales: superadmin / Admin123!")
        logger.info("¡POR FAVOR CAMBIA LA CONTRASEÑA INMEDIATAMENTE!")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creando superadmin: {str(e)}")
        raise
    finally:
        db.close()


def create_additional_indexes():
    """
    Crea índices adicionales para optimización
    """
    logger.info("Creando índices adicionales...")
    
    indexes = [
        # Índices para usuarios
        "CREATE INDEX IF NOT EXISTS idx_usuarios_search ON usuarios(username, email, nombre_completo) WHERE is_deleted = false",
        "CREATE INDEX IF NOT EXISTS idx_usuarios_created ON usuarios(created_at DESC)",
        
        # Índices para proyectos
        "CREATE INDEX IF NOT EXISTS idx_proyectos_search ON proyectos(nombre, descripcion) WHERE is_deleted = false",
        "CREATE INDEX IF NOT EXISTS idx_proyectos_created ON proyectos(created_at DESC)",
        
        # Índices para emisiones
        "CREATE INDEX IF NOT EXISTS idx_emisiones_complete ON emisiones_acumuladas(proyecto_id, cuenta, fecha_emision DESC)",
        "CREATE INDEX IF NOT EXISTS idx_emisiones_stats ON emisiones_acumuladas(fecha_generacion, usuario_id, documento)",
        
        # Índices para bitácora
        "CREATE INDEX IF NOT EXISTS idx_bitacora_complete ON bitacora(usuario_id, accion, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_bitacora_date_range ON bitacora(created_at DESC) WHERE created_at >= NOW() - INTERVAL '90 days'",
    ]
    
    with engine.connect() as conn:
        for index_sql in indexes:
            try:
                conn.execute(text(index_sql))
                conn.commit()
            except Exception as e:
                logger.warning(f"Error creando índice: {str(e)}")
                conn.rollback()
    
    logger.info("Índices adicionales creados")


if __name__ == "__main__":
    print("=" * 60)
    print("INICIALIZACIÓN DE BASE DE DATOS - SISTEMA PDF")
    print("=" * 60)
    print()
    print("Este script creará:")
    print("1. Todas las tablas del sistema")
    print("2. Usuario superadmin inicial (superadmin / Admin123!)")
    print("3. Índices de optimización")
    print()
    
    confirm = input("¿Continuar? (s/n): ")
    
    if confirm.lower() == 's':
        create_tables()
    else:
        print("Operación cancelada")