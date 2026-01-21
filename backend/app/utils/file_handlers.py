# Manejo de archivos 
import os
import hashlib
from typing import Tuple, Optional, Dict, Any
from fastapi import UploadFile, HTTPException
from pathlib import Path
import magic

from app.config import settings


class FileHandler:
    """
    Manejo seguro de archivos
    """
    
    @staticmethod
    def validate_file_size(file: UploadFile, max_size_mb: int) -> bool:
        """
        Valida tamaño máximo de archivo
        """
        # Obtener tamaño actual
        current_position = file.file.tell()
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(current_position)  # Volver a posición original
        
        max_size_bytes = max_size_mb * 1024 * 1024
        
        return file_size <= max_size_bytes
    
    @staticmethod
    def validate_file_type(file: UploadFile, allowed_types: list) -> bool:
        """
        Valida tipo de archivo usando magic bytes
        """
        # Leer primeros 2048 bytes para detección
        current_position = file.file.tell()
        file_content = file.file.read(2048)
        file.file.seek(current_position)  # Volver a posición original
        
        mime = magic.Magic(mime=True)
        file_type = mime.from_buffer(file_content)
        
        return file_type in allowed_types
    
    @staticmethod
    async def save_upload_file(
        upload_file: UploadFile, 
        destination: Path,
        validate_size: bool = True,
        validate_type: bool = True
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Guarda archivo subido de forma segura
        """
        try:
            # Validar tamaño
            if validate_size:
                if not FileHandler.validate_file_size(upload_file, settings.MAX_CSV_SIZE_MB):
                    return False, f"El archivo excede el tamaño máximo de {settings.MAX_CSV_SIZE_MB}MB", None
            
            # Validar tipo
            if validate_type:
                allowed_mime_types = {
                    'csv': ['text/csv', 'text/plain'],
                    'pdf': ['application/pdf'],
                    'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
                    'image': ['image/jpeg', 'image/png', 'image/gif']
                }
                
                # Determinar tipo según extensión
                file_extension = Path(upload_file.filename).suffix.lower()
                if file_extension == '.csv':
                    if not FileHandler.validate_file_type(upload_file, allowed_mime_types['csv']):
                        return False, "El archivo no es un CSV válido", None
                elif file_extension == '.pdf':
                    if not FileHandler.validate_file_type(upload_file, allowed_mime_types['pdf']):
                        return False, "El archivo no es un PDF válido", None
                elif file_extension == '.docx':
                    if not FileHandler.validate_file_type(upload_file, allowed_mime_types['docx']):
                        return False, "El archivo no es un DOCX válido", None
                elif file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
                    if not FileHandler.validate_file_type(upload_file, allowed_mime_types['image']):
                        return False, "El archivo no es una imagen válida", None
            
            # Crear directorio si no existe
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Generar nombre único
            file_hash = hashlib.sha256()
            chunk_size = 8192
            
            # Leer y calcular hash mientras guardamos
            with open(destination, "wb") as buffer:
                while chunk := await upload_file.read(chunk_size):
                    file_hash.update(chunk)
                    buffer.write(chunk)
            
            file_info = {
                "original_filename": upload_file.filename,
                "saved_path": str(destination),
                "file_size": destination.stat().st_size,
                "file_hash": file_hash.hexdigest(),
                "mime_type": upload_file.content_type
            }
            
            return True, "Archivo guardado exitosamente", file_info
            
        except Exception as e:
            return False, f"Error guardando archivo: {str(e)}", None
    
    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """
        Calcula hash SHA256 de un archivo
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    @staticmethod
    def safe_delete(file_path: Path) -> bool:
        """
        Elimina archivo de forma segura
        """
        try:
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False