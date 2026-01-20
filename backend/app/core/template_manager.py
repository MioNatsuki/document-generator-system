# Gestor de plantillas y documentos
import os
import uuid
import tempfile
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
from loguru import logger

from ..config import settings
from ..utils.docx_processor import DocxProcessor
from ..utils.pdf_utils import PDFUtils


class TemplateManager:
    """
    Gestiona la manipulación de plantillas DOCX y generación de PDFs
    """
    
    @staticmethod
    def create_template(proyecto_id: int, nombre: str, descripcion: str, 
                       docx_path: Path, mapeos: List[Dict]) -> Dict[str, Any]:
        """
        Crear una nueva plantilla
        """
        try:
            # Validar tamaño de página
            is_valid, page_size = DocxProcessor.validate_page_size(docx_path)
            if not is_valid:
                return {
                    "success": False,
                    "error": f"Tamaño de página inválido. Esperado: 21.59cm x 34.01cm, Obtenido: {page_size}"
                }
            
            # Extraer placeholders
            placeholders = DocxProcessor.extract_placeholders(docx_path)
            
            # Convertir a PDF
            temp_pdf = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.pdf"
            success = DocxProcessor.convert_to_pdf(docx_path, temp_pdf)
            
            if not success:
                logger.warning("No se pudo convertir DOCX a PDF")
                temp_pdf = None
            
            # Guardar archivos permanentemente
            uploads_dir = Path(settings.UPLOAD_FOLDER) / "plantillas"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            
            unique_id = uuid.uuid4()
            docx_final = uploads_dir / f"{unique_id}.docx"
            pdf_final = uploads_dir / f"{unique_id}.pdf" if temp_pdf else None
            
            # Copiar archivos
            import shutil
            shutil.copy2(docx_path, docx_final)
            if temp_pdf and temp_pdf.exists():
                shutil.copy2(temp_pdf, pdf_final)
            
            return {
                "success": True,
                "plantilla": {
                    "proyecto_id": proyecto_id,
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "archivo_docx": str(docx_final),
                    "archivo_pdf_base": str(pdf_final) if pdf_final else None,
                    "configuracion": {
                        "mapeos": mapeos,
                        "placeholders_detectados": placeholders
                    },
                    "tamaño_pagina": page_size
                }
            }
            
        except Exception as e:
            logger.error(f"Error creando plantilla: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def generate_test_pdf(docx_path: str, mapeos: List[Dict], 
                         datos: Dict[str, Any], output_path: Path) -> bool:
        """
        Generar PDF de prueba con datos
        """
        try:
            # Usar docx-mailmerge para reemplazar placeholders
            from mailmerge import MailMerge
            
            # Crear copia temporal del DOCX
            temp_docx = Path(tempfile.gettempdir()) / f"temp_{uuid.uuid4()}.docx"
            import shutil
            shutil.copy2(docx_path, temp_docx)
            
            # Reemplazar placeholders
            with MailMerge(str(temp_docx)) as document:
                # Preparar datos para merge
                merge_data = {}
                for mapeo in mapeos:
                    campo = mapeo.get('campo_padron')
                    if campo in datos:
                        merge_data[campo] = datos[campo]
                    else:
                        merge_data[campo] = f"[{campo}]"
                
                document.merge(**merge_data)
                document.write(str(temp_docx))
            
            # Convertir a PDF
            success = DocxProcessor.convert_to_pdf(temp_docx, output_path)
            
            # Limpiar
            temp_docx.unlink(missing_ok=True)
            
            return success
            
        except Exception as e:
            logger.error(f"Error generando PDF de prueba: {str(e)}")
            return False
    
    @staticmethod
    def validate_template_completeness(plantilla_config: Dict) -> Tuple[bool, List[str]]:
        """
        Validar que la plantilla esté completamente configurada
        """
        errors = []
        
        mapeos = plantilla_config.get("mapeos", [])
        placeholders = plantilla_config.get("placeholders_detectados", [])
        
        # Verificar que todos los placeholders estén mapeados
        campos_mapeados = {m.get('campo_padron') for m in mapeos}
        
        for placeholder in placeholders:
            if placeholder not in campos_mapeados:
                errors.append(f"Placeholder '{placeholder}' no está mapeado")
        
        # Verificar que no haya mapeos sin placeholders
        for mapeo in mapeos:
            campo = mapeo.get('campo_padron')
            if campo not in placeholders:
                errors.append(f"Campo mapeado '{campo}' no existe en el documento")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def duplicate_template(plantilla_original: Dict, nuevo_nombre: str) -> Dict[str, Any]:
        """
        Duplicar una plantilla existente
        """
        try:
            # Crear copia de archivos
            original_docx = Path(plantilla_original.get('archivo_docx', ''))
            original_pdf = Path(plantilla_original.get('archivo_pdf_base', ''))
            
            if not original_docx.exists():
                return {
                    "success": False,
                    "error": "Archivo DOCX original no encontrado"
                }
            
            # Directorio de uploads
            uploads_dir = Path(settings.UPLOAD_FOLDER) / "plantillas"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            
            unique_id = uuid.uuid4()
            nuevo_docx = uploads_dir / f"{unique_id}.docx"
            nuevo_pdf = uploads_dir / f"{unique_id}.pdf" if original_pdf.exists() else None
            
            # Copiar archivos
            import shutil
            shutil.copy2(original_docx, nuevo_docx)
            if nuevo_pdf and original_pdf.exists():
                shutil.copy2(original_pdf, nuevo_pdf)
            
            return {
                "success": True,
                "plantilla": {
                    "nombre": nuevo_nombre,
                    "descripcion": f"Copia de {plantilla_original.get('nombre', '')}",
                    "archivo_docx": str(nuevo_docx),
                    "archivo_pdf_base": str(nuevo_pdf) if nuevo_pdf else None,
                    "configuracion": plantilla_original.get('configuracion', {}),
                    "tamaño_pagina": plantilla_original.get('tamaño_pagina', {})
                }
            }
            
        except Exception as e:
            logger.error(f"Error duplicando plantilla: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }