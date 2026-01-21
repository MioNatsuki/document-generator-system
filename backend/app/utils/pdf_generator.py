"""
Generador de PDFs usando ReportLab y Pillow
"""
import os
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import tempfile
import logging

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.lib.units import cm, inch, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.lib.colors import Color, black, white

from PIL import Image, ImageDraw, ImageFont
import io

from text_formatter import TextFormatter
from barcode_generator import BarcodeGenerator

logger = logging.getLogger(__name__)


class PDFGenerator:
    """
    Generador de PDFs con inserción precisa de texto e imágenes
    """
    
    def __init__(self):
        self.text_formatter = TextFormatter()
        self.barcode_generator = BarcodeGenerator()
        
        # Registrar fuentes comunes
        self._register_fonts()
    
    def _register_fonts(self):
        """Registrar fuentes TrueType para ReportLab"""
        try:
            # Intentar registrar fuentes comunes
            font_paths = [
                '/usr/share/fonts/truetype/msttcorefonts/arial.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                'C:/Windows/Fonts/arial.ttf',
                '/System/Library/Fonts/Arial.ttf'
            ]
            
            for path in font_paths:
                if os.path.exists(path):
                    try:
                        pdfmetrics.registerFont(TTFont('Arial', path))
                        addMapping('Arial', 0, 0, 'Arial')  # normal
                        addMapping('Arial', 0, 1, 'Arial')  # italic
                        addMapping('Arial', 1, 0, 'Arial')  # bold
                        addMapping('Arial', 1, 1, 'Arial')  # bold-italic
                        logger.info(f"Fuente registrada: {path}")
                        break
                    except:
                        continue
            
            # Fuente por defecto
            self.default_font = 'Helvetica'
            
        except Exception as e:
            logger.warning(f"No se pudieron registrar fuentes: {str(e)}")
            self.default_font = 'Helvetica'
    
    def generate_from_template(self, template_path: Path, template_config: Dict, 
                              output_path: Path, data: Dict, 
                              barcode_image: Optional[Image.Image] = None,
                              page_size: Optional[Dict] = None):
        """
        Generar PDF desde configuración de plantilla
        
        Args:
            template_path: Ruta al archivo DOCX (no se usa directamente, pero se mantiene para referencia)
            template_config: Configuración de la plantilla
            output_path: Ruta de salida para el PDF
            data: Datos a insertar
            barcode_image: Imagen de código de barras (opcional)
            page_size: Tamaño de página personalizado
        """
        try:
            # Configurar tamaño de página
            if page_size and 'ancho' in page_size and 'alto' in page_size:
                width = page_size['ancho'] * cm
                height = page_size['alto'] * cm
                pagesize = (width, height)
            else:
                # Tamaño México Oficio por defecto: 21.59cm x 34.01cm
                width = 21.59 * cm
                height = 34.01 * cm
                pagesize = (width, height)
            
            # Crear canvas PDF
            c = canvas.Canvas(str(output_path), pagesize=pagesize)
            
            # Obtener mapeos de la plantilla
            mapeos = template_config.get('mapeos', [])
            
            # Procesar cada mapeo
            for mapeo in mapeos:
                self._process_mapeo(c, mapeo, data, barcode_image, pagesize)
            
            # Guardar PDF
            c.save()
            
            logger.debug(f"PDF generado: {output_path}")
            
        except Exception as e:
            logger.error(f"Error generando PDF: {str(e)}")
            raise
    
    def _process_mapeo(self, canvas_obj, mapeo: Dict, data: Dict, 
                      barcode_image: Optional[Image.Image], pagesize: Tuple[float, float]):
        """
        Procesar un mapeo individual
        """
        try:
            campo = mapeo.get('campo_padron')
            x = mapeo.get('x', 0) * cm
            y = mapeo.get('y', 0) * cm
            ancho = mapeo.get('ancho', 5) * cm
            alto = mapeo.get('alto', 1) * cm
            fuente = mapeo.get('fuente', 'Helvetica')
            tamaño = mapeo.get('tamaño', 11)
            es_codigo_barras = mapeo.get('es_codigo_barras', False)
            
            # Obtener valor de datos
            valor = data.get(campo, f"[{campo}]")
            
            if es_codigo_barras and barcode_image:
                # Insertar código de barras
                self._insert_barcode(canvas_obj, barcode_image, x, y, ancho, alto, pagesize)
            else:
                # Insertar texto
                self._insert_text(canvas_obj, valor, x, y, ancho, alto, fuente, tamaño)
                
        except Exception as e:
            logger.warning(f"Error procesando mapeo {mapeo.get('campo_padron')}: {str(e)}")
    
    def _insert_text(self, canvas_obj, text: str, x: float, y: float, 
                    width: float, height: float, font_name: str, font_size: int):
        """
        Insertar texto con ajuste automático
        """
        try:
            # Ajustar coordenada Y (ReportLab usa coordenadas desde abajo)
            page_height = canvas_obj._pagesize[1]
            y_adjusted = page_height - y - height
            
            # Formatear texto según sea necesario
            text = str(text) if text is not None else ""
            
            # Verificar si el texto cabe en una línea
            canvas_obj.setFont(font_name, font_size)
            text_width = canvas_obj.stringWidth(text, font_name, font_size)
            
            if text_width <= width:
                # Texto cabe en una línea
                canvas_obj.drawString(x, y_adjusted + (height - font_size) / 2, text)
            else:
                # Texto demasiado largo, necesitamos ajustar
                lines = self._wrap_text(canvas_obj, text, font_name, font_size, width)
                
                # Calcular altura total del texto
                line_height = font_size * 1.2
                total_height = len(lines) * line_height
                
                # Verificar si cabe en la altura disponible
                if total_height <= height:
                    # Dibujar cada línea
                    for i, line in enumerate(lines):
                        line_y = y_adjusted + height - ((i + 1) * line_height)
                        canvas_obj.drawString(x, line_y, line)
                else:
                    # Reducir tamaño de fuente hasta que quepa
                    new_size = font_size
                    while new_size >= 8 and total_height > height:
                        new_size -= 1
                        line_height = new_size * 1.2
                        lines = self._wrap_text(canvas_obj, text, font_name, new_size, width)
                        total_height = len(lines) * line_height
                    
                    if new_size >= 8:
                        # Dibujar con tamaño reducido
                        canvas_obj.setFont(font_name, new_size)
                        for i, line in enumerate(lines):
                            line_y = y_adjusted + height - ((i + 1) * line_height)
                            canvas_obj.drawString(x, line_y, line)
                    else:
                        # Tamaño mínimo alcanzado, truncar
                        truncated = text[:30] + "..."
                        canvas_obj.drawString(x, y_adjusted + (height - font_size) / 2, truncated)
            
        except Exception as e:
            logger.warning(f"Error insertando texto: {str(e)}")
    
    def _wrap_text(self, canvas_obj, text: str, font_name: str, font_size: int, max_width: float) -> List[str]:
        """
        Dividir texto en múltiples líneas
        """
        lines = []
        words = text.split()
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            test_width = canvas_obj.stringWidth(test_line, font_name, font_size)
            
            if test_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _insert_barcode(self, canvas_obj, barcode_image: Image.Image, x: float, y: float,
                       width: float, height: float, pagesize: Tuple[float, float]):
        """
        Insertar imagen de código de barras
        """
        try:
            # Ajustar coordenada Y
            page_height = pagesize[1]
            y_adjusted = page_height - y - height
            
            # Redimensionar imagen si es necesario
            img_width, img_height = barcode_image.size
            scale = min(width / img_width, height / img_height)
            
            new_width = img_width * scale
            new_height = img_height * scale
            
            # Centrar la imagen en el área
            x_centered = x + (width - new_width) / 2
            y_centered = y_adjusted + (height - new_height) / 2
            
            # Convertir PIL Image a formato que ReportLab pueda usar
            img_buffer = io.BytesIO()
            barcode_image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # Dibujar imagen
            canvas_obj.drawImage(ImageReader(img_buffer), x_centered, y_centered,
                               width=new_width, height=new_height, mask='auto')
            
        except Exception as e:
            logger.warning(f"Error insertando código de barras: {str(e)}")
    
    def generate_test_pdf(self, output_path: Path, data: Dict, 
                         template_config: Dict = None) -> bool:
        """
        Generar PDF de prueba
        """
        try:
            # Configuración de prueba si no se proporciona
            if not template_config:
                template_config = {
                    'mapeos': [
                        {
                            'campo_padron': 'nombre',
                            'x': 2.0,
                            'y': 5.0,
                            'ancho': 10.0,
                            'alto': 1.0,
                            'fuente': 'Helvetica',
                            'tamaño': 12
                        },
                        {
                            'campo_padron': 'cuenta',
                            'x': 2.0,
                            'y': 4.0,
                            'ancho': 5.0,
                            'alto': 1.0,
                            'fuente': 'Helvetica',
                            'tamaño': 11
                        }
                    ]
                }
            
            # Generar PDF
            self.generate_from_template(
                template_path=Path('test.docx'),
                template_config=template_config,
                output_path=output_path,
                data=data
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error generando PDF de prueba: {str(e)}")
            return False