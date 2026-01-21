# Gestión de tablas dinámicas 
# Gestión de tablas dinámicas 
import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text, DDL, Table, Column, MetaData, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger
import pandas as pd
from io import StringIO

from config import settings
from database import engine


class PadronManager:
    """
    Gestiona la creación y modificación de tablas dinámicas para padrones
    """
    
    @staticmethod
    def sanitize_table_name(name: str) -> str:
        """
        Sanitiza nombre de tabla para PostgreSQL
        """
        # Solo letras, números y guiones bajos
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # No puede empezar con número
        if sanitized[0].isdigit():
            sanitized = 't_' + sanitized
        # Máximo 63 caracteres (límite PostgreSQL)
        return sanitized[:63].lower()
    
    @staticmethod
    def create_padron_table(project_uuid: str, columnas: List[Dict[str, Any]]) -> Tuple[str, str]:
        """
        Crea tabla dinámica para el padrón de un proyecto
        
        Args:
            project_uuid: UUID del proyecto
            columnas: Lista de diccionarios con 'nombre' y 'tipo'
            
        Returns:
            (nombre_tabla, nombre_final) donde nombre_final incluye prefijo
        """
        # Generar nombre de tabla
        table_uuid = str(uuid.uuid4())[:8]
        table_base_name = f"padron_completo_{table_uuid}"
        table_name = PadronManager.sanitize_table_name(table_base_name)
        
        # Crear SQL para la tabla
        columns_sql = []
        columns_sql.append("id SERIAL PRIMARY KEY")
        
        for col in columnas:
            col_name = PadronManager.sanitize_column_name(col['nombre'])
            col_type = col['tipo']
            
            # Agregar constraints según configuración
            constraint = ""
            if col.get('es_obligatorio', False):
                constraint += " NOT NULL"
            if col.get('es_unico', False):
                constraint += " UNIQUE"
                
            columns_sql.append(f"{col_name} {col_type}{constraint}")
        
        # Agregar columnas de control
        columns_sql.append("created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP")
        columns_sql.append("updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP")
        columns_sql.append("is_deleted BOOLEAN DEFAULT FALSE")
        
        # Crear tabla
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {', '.join(columns_sql)}
        );
        """
        
        # Índices para búsqueda rápida
        index_sql = f"""
        CREATE INDEX IF NOT EXISTS idx_{table_name}_cuenta 
        ON {table_name}(cuenta) WHERE is_deleted = false;
        
        CREATE INDEX IF NOT EXISTS idx_{table_name}_search 
        ON {table_name}(cuenta, nombre) WHERE is_deleted = false;
        """
        
        try:
            with engine.connect() as conn:
                # Ejecutar creación de tabla
                conn.execute(text(create_sql))
                conn.execute(text(index_sql))
                conn.commit()
                
                logger.info(f"Tabla de padrón creada: {table_name}")
                return table_name, table_base_name
                
        except SQLAlchemyError as e:
            logger.error(f"Error creando tabla de padrón: {str(e)}")
            raise
    
    @staticmethod
    def sanitize_column_name(name: str) -> str:
        """
        Sanitiza nombre de columna para PostgreSQL
        """
        # Reemplazar espacios y caracteres especiales
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # No puede empezar con número
        if sanitized[0].isdigit():
            sanitized = 'c_' + sanitized
        return sanitized.lower()
    
    @staticmethod
    def drop_padron_table(table_name: str) -> bool:
        """
        Elimina tabla de padrón
        
        Args:
            table_name: Nombre de la tabla
            
        Returns:
            True si se eliminó, False si hubo error
        """
        drop_sql = f"DROP TABLE IF EXISTS {table_name} CASCADE;"
        
        try:
            with engine.connect() as conn:
                conn.execute(text(drop_sql))
                conn.commit()
                logger.info(f"Tabla de padrón eliminada: {table_name}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error eliminando tabla de padrón: {str(e)}")
            return False
    
    @staticmethod
    def insert_padron_data(table_name: str, data: List[Dict[str, Any]], 
                          merge: bool = True) -> Dict[str, int]:
        """
        Inserta datos en la tabla de padrón
        
        Args:
            table_name: Nombre de la tabla
            data: Lista de diccionarios con los datos
            merge: True para upsert, False para insert ignorando duplicados
            
        Returns:
            Diccionario con conteo de operaciones
        """
        if not data:
            return {"inserted": 0, "updated": 0, "errors": 0}
        
        try:
            # Convertir a DataFrame para facilitar manejo
            df = pd.DataFrame(data)
            
            # Sanitizar nombres de columnas
            df.columns = [PadronManager.sanitize_column_name(col) for col in df.columns]
            
            # Separar inserts y updates si merge=True
            inserted = 0
            updated = 0
            errors = 0
            
            with engine.connect() as conn:
                for _, row in df.iterrows():
                    row_dict = row.to_dict()
                    
                    # Verificar si la cuenta ya existe
                    if merge and 'cuenta' in row_dict:
                        check_sql = f"""
                        SELECT id FROM {table_name} 
                        WHERE cuenta = :cuenta AND is_deleted = false
                        """
                        result = conn.execute(
                            text(check_sql), 
                            {"cuenta": row_dict['cuenta']}
                        ).fetchone()
                        
                        if result:
                            # UPDATE
                            set_clause = ", ".join([f"{k} = :{k}" for k in row_dict.keys()])
                            update_sql = f"""
                            UPDATE {table_name}
                            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                            WHERE cuenta = :cuenta AND is_deleted = false
                            """
                            conn.execute(text(update_sql), row_dict)
                            updated += 1
                        else:
                            # INSERT
                            columns = ", ".join(row_dict.keys())
                            values = ", ".join([f":{k}" for k in row_dict.keys()])
                            insert_sql = f"""
                            INSERT INTO {table_name} ({columns})
                            VALUES ({values})
                            """
                            conn.execute(text(insert_sql), row_dict)
                            inserted += 1
                    else:
                        # INSERT simple
                        columns = ", ".join(row_dict.keys())
                        values = ", ".join([f":{k}" for k in row_dict.keys()])
                        insert_sql = f"""
                        INSERT INTO {table_name} ({columns})
                        VALUES ({values})
                        ON CONFLICT DO NOTHING
                        """
                        result = conn.execute(text(insert_sql), row_dict)
                        if result.rowcount:
                            inserted += 1
                
                conn.commit()
                
                logger.info(f"Datos procesados en {table_name}: {inserted} inserts, {updated} updates")
                return {"inserted": inserted, "updated": updated, "errors": errors}
                
        except SQLAlchemyError as e:
            logger.error(f"Error insertando datos en padrón: {str(e)}")
            raise
    
    @staticmethod
    def get_table_structure(table_name: str) -> List[Dict[str, Any]]:
        """
        Obtiene la estructura de una tabla
        
        Args:
            table_name: Nombre de la tabla
            
        Returns:
            Lista de columnas con nombre y tipo
        """
        sql = """
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = :table_name
        AND column_name NOT IN ('id', 'created_at', 'updated_at', 'is_deleted')
        ORDER BY ordinal_position;
        """
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql), {"table_name": table_name})
                columns = []
                
                for row in result:
                    col_type = row[1]
                    if row[2]:  # Si tiene longitud máxima
                        col_type = f"{col_type}({row[2]})"
                    
                    columns.append({
                        "nombre": row[0],
                        "tipo": col_type,
                        "nulo": row[3] == 'YES',
                        "default": row[4]
                    })
                
                return columns
                
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo estructura de tabla: {str(e)}")
            raise
    
    @staticmethod
    def table_exists(table_name: str) -> bool:
        """
        Verifica si una tabla existe
        
        Args:
            table_name: Nombre de la tabla
            
        Returns:
            True si existe, False si no
        """
        sql = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = :table_name
        );
        """
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql), {"table_name": table_name}).scalar()
                return bool(result)
        except SQLAlchemyError:
            return False
    
    @staticmethod
    def get_sample_data(table_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene datos de muestra de una tabla
        
        Args:
            table_name: Nombre de la tabla
            limit: Límite de registros
            
        Returns:
            Lista de diccionarios con datos
        """
        sql = f"""
        SELECT * FROM {table_name}
        WHERE is_deleted = false
        LIMIT {limit};
        """
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                columns = result.keys()
                data = []
                
                for row in result:
                    data.append({col: val for col, val in zip(columns, row)})
                
                return data
                
        except SQLAlchemyError as e:
            logger.error(f"Error obteniendo datos de muestra: {str(e)}")
            raise
    
    @staticmethod
    def parse_csv_to_dict(csv_content: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Parsea contenido CSV a lista de diccionarios
        
        Args:
            csv_content: Contenido del CSV como string
            
        Returns:
            (datos, columnas) donde datos es lista de dicts y columnas es lista de nombres
        """
        try:
            # Leer CSV
            df = pd.read_csv(StringIO(csv_content))
            
            # Convertir a lista de diccionarios
            data = df.to_dict('records')
            columns = list(df.columns)
            
            return data, columns
            
        except Exception as e:
            logger.error(f"Error parseando CSV: {str(e)}")
            raise
    
    @staticmethod
    def validate_csv_structure(csv_columns: List[str], 
                             expected_columns: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Valida que las columnas del CSV coincidan con la estructura esperada
        
        Args:
            csv_columns: Lista de columnas del CSV
            expected_columns: Lista de columnas esperadas
            
        Returns:
            (es_valido, mensajes_error)
        """
        errors = []
        
        # Verificar columnas obligatorias
        expected_names = [col['nombre'].lower() for col in expected_columns]
        csv_names = [col.lower() for col in csv_columns]
        
        # Buscar 'cuenta' y 'nombre'
        if 'cuenta' not in csv_names:
            errors.append("El CSV debe contener la columna 'cuenta'")
        
        if 'nombre' not in csv_names:
            errors.append("El CSV debe contener la columna 'nombre'")
        
        # Verificar que todas las columnas del CSV estén en la estructura
        for csv_col in csv_names:
            if csv_col not in expected_names:
                errors.append(f"Columna '{csv_col}' no está definida en la estructura del padrón")
        
        return len(errors) == 0, errors