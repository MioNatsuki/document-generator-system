# Diálogos de archivos 
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtCore import QDir
from pathlib import Path
import mimetypes
import os


class FileDialog:
    """Clase para manejar diálogos de archivos"""
    
    @staticmethod
    def open_csv_file(parent=None, title="Seleccionar archivo CSV"):
        """Abrir diálogo para seleccionar archivo CSV"""
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            title,
            str(Path.home()),
            "Archivos CSV (*.csv);;Todos los archivos (*)"
        )
        
        if file_path:
            # Validaciones básicas
            if not file_path.lower().endswith('.csv'):
                QMessageBox.warning(
                    parent, 
                    "Archivo inválido", 
                    "El archivo seleccionado no es un CSV.\n"
                    "Por favor, selecciona un archivo con extensión .csv"
                )
                return None
            
            # Verificar que el archivo no esté vacío
            try:
                if os.path.getsize(file_path) == 0:
                    QMessageBox.warning(
                        parent,
                        "Archivo vacío",
                        "El archivo CSV seleccionado está vacío."
                    )
                    return None
            except:
                pass
        
        return file_path if file_path else None
    
    @staticmethod
    def open_docx_file(parent=None, title="Seleccionar plantilla DOCX"):
        """Abrir diálogo para seleccionar archivo DOCX"""
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            title,
            str(Path.home()),
            "Documentos Word (*.docx);;Todos los archivos (*)"
        )
        
        if file_path and not file_path.lower().endswith('.docx'):
            QMessageBox.warning(
                parent,
                "Archivo inválido",
                "El archivo seleccionado no es un documento DOCX.\n"
                "Por favor, selecciona un archivo con extensión .docx"
            )
            return None
        
        return file_path if file_path else None
    
    @staticmethod
    def open_pdf_file(parent=None, title="Seleccionar archivo PDF"):
        """Abrir diálogo para seleccionar archivo PDF"""
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            title,
            str(Path.home()),
            "Documentos PDF (*.pdf);;Todos los archivos (*)"
        )
        
        if file_path and not file_path.lower().endswith('.pdf'):
            QMessageBox.warning(
                parent,
                "Archivo inválido",
                "El archivo seleccionado no es un PDF.\n"
                "Por favor, selecciona un archivo con extensión .pdf"
            )
            return None
        
        return file_path if file_path else None
    
    @staticmethod
    def open_image_file(parent=None, title="Seleccionar imagen"):
        """Abrir diálogo para seleccionar archivo de imagen"""
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            title,
            str(Path.home()),
            "Imágenes (*.png *.jpg *.jpeg *.gif *.bmp);;Todos los archivos (*)"
        )
        
        return file_path if file_path else None
    
    @staticmethod
    def select_directory(parent=None, title="Seleccionar carpeta", default_path=None):
        """Seleccionar directorio"""
        if default_path is None:
            default_path = str(Path.home())
        
        dir_path = QFileDialog.getExistingDirectory(
            parent,
            title,
            default_path,
            QFileDialog.Option.ShowDirsOnly
        )
        
        return dir_path if dir_path else None
    
    @staticmethod
    def save_file(parent=None, title="Guardar archivo", default_name="", 
                 file_filter="Todos los archivos (*)"):
        """Diálogo para guardar archivo"""
        if default_name:
            default_path = str(Path.home() / default_name)
        else:
            default_path = str(Path.home())
        
        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            title,
            default_path,
            file_filter
        )
        
        return file_path if file_path else None
    
    @staticmethod
    def save_csv_file(parent=None, default_name="datos.csv"):
        """Diálogo para guardar archivo CSV"""
        return FileDialog.save_file(
            parent,
            "Guardar CSV",
            default_name,
            "Archivos CSV (*.csv);;Todos los archivos (*)"
        )
    
    @staticmethod
    def save_pdf_file(parent=None, default_name="documento.pdf"):
        """Diálogo para guardar archivo PDF"""
        return FileDialog.save_file(
            parent,
            "Guardar PDF",
            default_name,
            "Documentos PDF (*.pdf);;Todos los archivos (*)"
        )
    
    @staticmethod
    def get_file_size(file_path: str) -> str:
        """Obtener tamaño de archivo en formato legible"""
        try:
            size_bytes = os.path.getsize(file_path)
            
            # Convertir a unidades legibles
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            
            return f"{size_bytes:.1f} TB"
        except:
            return "Desconocido"
    
    @staticmethod
    def validate_file_size(file_path: str, max_size_mb: int) -> tuple[bool, str]:
        """
        Validar tamaño máximo de archivo
        
        Returns:
            (es_valido, mensaje_error)
        """
        try:
            size_bytes = os.path.getsize(file_path)
            max_bytes = max_size_mb * 1024 * 1024
            
            if size_bytes > max_bytes:
                file_size_mb = size_bytes / (1024 * 1024)
                return False, (
                    f"El archivo es demasiado grande ({file_size_mb:.1f} MB).\n"
                    f"Tamaño máximo permitido: {max_size_mb} MB"
                )
            
            return True, ""
        except:
            return False, "No se pudo verificar el tamaño del archivo"