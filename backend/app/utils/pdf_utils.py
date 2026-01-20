# Utilidades para manipulación de PDFs
import os
import tempfile
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
from loguru import logger

try:
    from PyPDF2 import PdfReader, PdfWriter
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyPDF2 no está instalado. Algunas funciones estarán limitadas.")


class PDFUtils:
    """
    Utilidades para manipulación y validación de PDFs
    """
    
    @staticmethod
    def validate_pdf_size(pdf_path: Path) -> Tuple[bool, List[str], List[str]]:
        """
        Validar que el PDF tenga tamaño México Oficio (21.59cm x 34.01cm)
        
        Returns:
            (es_valido, errores, advertencias)
        """
        errors = []
        warnings = []
        
        if not PDF_AVAILABLE:
            warnings.append("PyPDF2 no disponible, validación de tamaño limitada")
            return True, errors, warnings
        
        try:
            reader = PdfReader(pdf_path)
            
            if not reader.pages:
                errors.append("PDF no tiene páginas")
                return False, errors, warnings
            
            # Obtener tamaño de la primera página
            page = reader.pages[0]
            mediabox = page.mediabox
            
            # Convertir de puntos a cm (1 punto = 1/72 inch, 1 inch = 2.54 cm)
            width_pt = mediabox.width
            height_pt = mediabox.height
            
            width_cm = (width_pt / 72) * 2.54
            height_cm = (height_pt / 72) * 2.54
            
            # Tolerancia de 0.1 cm
            expected_width = 21.59
            expected_height = 34.01
            tolerance = 0.1
            
            is_width_valid = abs(width_cm - expected_width) <= tolerance
            is_height_valid = abs(height_cm - expected_height) <= tolerance
            
            if not is_width_valid:
                errors.append(f"Ancho inválido: {width_cm:.2f}cm (esperado: {expected_width}cm)")
            
            if not is_height_valid:
                errors.append(f"Alto inválido: {height_cm:.2f}cm (esperado: {expected_height}cm)")
            
            # Verificar todas las páginas
            if len(reader.pages) > 1:
                for i, page in enumerate(reader.pages[1:], 1):
                    mediabox = page.mediabox
                    if mediabox.width != width_pt or mediabox.height != height_pt:
                        warnings.append(f"Página {i+1} tiene tamaño diferente a la primera página")
            
            is_valid = len(errors) == 0
            
            logger.info(f"Tamaño de PDF validado: {width_cm:.2f}cm x {height_cm:.2f}cm - Válido: {is_valid}")
            
            return is_valid, errors, warnings
            
        except Exception as e:
            logger.error(f"Error validando tamaño de PDF: {str(e)}")
            errors.append(f"Error validando PDF: {str(e)}")
            return False, errors, warnings
    
    @staticmethod
    def merge_pdfs(pdf_paths: List[Path], output_path: Path) -> bool:
        """
        Fusionar múltiples PDFs en uno solo
        """
        if not PDF_AVAILABLE:
            logger.error("PyPDF2 no disponible, no se puede fusionar PDFs")
            return False
        
        try:
            writer = PdfWriter()
            
            for pdf_path in pdf_paths:
                if pdf_path.exists():
                    reader = PdfReader(pdf_path)
                    for page in reader.pages:
                        writer.add_page(page)
                else:
                    logger.warning(f"PDF no encontrado: {pdf_path}")
            
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            logger.info(f"PDFs fusionados exitosamente en: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error fusionando PDFs: {str(e)}")
            return False
    
    @staticmethod
    def extract_text(pdf_path: Path, page_num: int = 0) -> Optional[str]:
        """
        Extraer texto de una página del PDF
        """
        if not PDF_AVAILABLE:
            return None
        
        try:
            reader = PdfReader(pdf_path)
            
            if page_num < 0 or page_num >= len(reader.pages):
                return None
            
            page = reader.pages[page_num]
            text = page.extract_text()
            
            return text
            
        except Exception as e:
            logger.error(f"Error extrayendo texto del PDF: {str(e)}")
            return None
    
    @staticmethod
    def get_pdf_info(pdf_path: Path) -> Dict[str, Any]:
        """
        Obtener información del PDF
        """
        info = {
            "path": str(pdf_path),
            "exists": pdf_path.exists(),
            "size_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
            "error": None
        }
        
        if not info["exists"]:
            info["error"] = "Archivo no encontrado"
            return info
        
        if not PDF_AVAILABLE:
            info["error"] = "PyPDF2 no disponible"
            return info
        
        try:
            reader = PdfReader(pdf_path)
            
            info.update({
                "num_pages": len(reader.pages),
                "encrypted": reader.is_encrypted,
                "metadata": reader.metadata,
                "page_sizes": []
            })
            
            # Obtener tamaño de cada página
            for i, page in enumerate(reader.pages):
                mediabox = page.mediabox
                width_cm = (mediabox.width / 72) * 2.54
                height_cm = (mediabox.height / 72) * 2.54
                
                info["page_sizes"].append({
                    "page": i + 1,
                    "width_cm": round(width_cm, 2),
                    "height_cm": round(height_cm, 2),
                    "width_pt": mediabox.width,
                    "height_pt": mediabox.height
                })
            
        except Exception as e:
            info["error"] = str(e)
        
        return info
    
    @staticmethod
    def create_placeholder_pdf(output_path: Path, text: str = "Documento PDF") -> bool:
        """
        Crear un PDF de placeholder
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.lib import colors
            
            c = canvas.Canvas(str(output_path), pagesize=letter)
            
            # Fondo color pastel
            c.setFillColor(colors.HexColor("#FFD6E7"))  # Rosa pastel
            c.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
            
            # Texto
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 24)
            c.drawCentredString(letter[0]/2, letter[1]/2, text)
            
            # Información adicional
            c.setFont("Helvetica", 12)
            c.drawCentredString(letter[0]/2, letter[1]/2 - 50, "PDF generado automáticamente")
            
            c.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Error creando PDF placeholder: {str(e)}")
            return False