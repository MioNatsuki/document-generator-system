"""
Generador de códigos de barras
"""
import os
import tempfile
from typing import Optional, Tuple, Dict
from pathlib import Path
import logging

import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class BarcodeGenerator:
    """
    Generador de códigos de barras en formato imagen
    """
    
    def __init__(self):
        self.supported_formats = ['Code128', 'Code39', 'EAN13', 'EAN8', 'UPC-A']
        self.default_format = 'Code128'
    
    def generate(self, data: str, barcode_format: str = None, 
                output_format: str = 'PNG', 
                options: Optional[Dict] = None) -> Image.Image:
        """
        Generar código de barras como imagen PIL
        
        Args:
            data: Datos para el código de barras
            barcode_format: Formato del código de barras (Code128, Code39, etc.)
            output_format: Formato de salida (PNG, JPEG, etc.)
            options: Opciones adicionales para el escritor
            
        Returns:
            Imagen PIL del código de barras
        """
        try:
            # Validar datos
            if not data or not str(data).strip():
                raise ValueError("Datos vacíos para código de barras")
            
            # Formato por defecto
            if not barcode_format:
                barcode_format = self.default_format
            
            if barcode_format not in self.supported_formats:
                logger.warning(f"Formato {barcode_format} no soportado, usando Code128")
                barcode_format = 'Code128'
            
            # Configurar opciones
            writer_options = {
                'module_height': 15.0,  # Altura del código de barras en mm
                'module_width': 0.2,    # Ancho de cada barra en mm
                'quiet_zone': 6.5,      # Zona silenciosa en mm
                'font_size': 10,        # Tamaño de fuente para texto
                'text_distance': 5.0,   # Distancia del texto al código
                'write_text': True,     # Mostrar texto debajo del código
                'background': 'white',  # Fondo blanco
                'foreground': 'black',  # Barras negras
            }
            
            if options:
                writer_options.update(options)
            
            # Crear código de barras
            barcode_class = barcode.get_barcode_class(barcode_format)
            barcode_writer = ImageWriter()
            
            # Configurar opciones del escritor
            for key, value in writer_options.items():
                setattr(barcode_writer, key, value)
            
            # Generar código
            barcode_obj = barcode_class(data, writer=barcode_writer)
            
            # Guardar temporalmente
            temp_dir = tempfile.gettempdir()
            temp_path = Path(temp_dir) / f"barcode_{os.getpid()}.{output_format.lower()}"
            
            barcode_obj.save(str(temp_path))
            
            # Cargar como imagen PIL
            img = Image.open(temp_path)
            
            # Limpiar archivo temporal
            temp_path.unlink(missing_ok=True)
            
            logger.debug(f"Código de barras generado: {data[:20]}...")
            
            return img
            
        except Exception as e:
            logger.error(f"Error generando código de barras: {str(e)}")
            raise
    
    def generate_with_text(self, data: str, text: Optional[str] = None,
                          barcode_format: str = None, 
                          output_size: Tuple[int, int] = None) -> Image.Image:
        """
        Generar código de barras con texto personalizado
        
        Args:
            data: Datos para el código de barras
            text: Texto para mostrar (si es None, usa data)
            barcode_format: Formato del código de barras
            output_size: Tamaño de salida deseado (ancho, alto)
            
        Returns:
            Imagen PIL del código de barras con texto
        """
        try:
            # Generar código de barras base
            barcode_img = self.generate(data, barcode_format, 'PNG')
            
            # Texto a mostrar
            display_text = text if text is not None else data
            
            # Crear imagen combinada
            barcode_width, barcode_height = barcode_img.size
            
            # Espacio para texto
            text_height = 30
            total_height = barcode_height + text_height
            
            # Crear nueva imagen
            combined_img = Image.new('RGB', (barcode_width, total_height), 'white')
            combined_img.paste(barcode_img, (0, 0))
            
            # Agregar texto
            draw = ImageDraw.Draw(combined_img)
            
            try:
                # Intentar cargar fuente
                font = ImageFont.truetype("arial.ttf", 12)
            except:
                # Fuente por defecto
                font = ImageFont.load_default()
            
            # Calcular posición del texto
            text_bbox = draw.textbbox((0, 0), display_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_x = (barcode_width - text_width) // 2
            text_y = barcode_height + 5
            
            # Dibujar texto
            draw.text((text_x, text_y), display_text, fill='black', font=font)
            
            # Redimensionar si se especifica tamaño
            if output_size:
                combined_img = combined_img.resize(output_size, Image.Resampling.LANCZOS)
            
            return combined_img
            
        except Exception as e:
            logger.error(f"Error generando código de barras con texto: {str(e)}")
            raise
    
    def validate_barcode_data(self, data: str, barcode_format: str = None) -> Tuple[bool, str]:
        """
        Validar datos para código de barras
        
        Args:
            data: Datos a validar
            barcode_format: Formato del código de barras
            
        Returns:
            Tuple (es_valido, mensaje_error)
        """
        if not data:
            return False, "Datos vacíos"
        
        data_str = str(data)
        
        # Validaciones por formato
        if barcode_format == 'Code128':
            # Code128 puede contener cualquier carácter ASCII
            if len(data_str) > 255:
                return False, "Code128: máximo 255 caracteres"
                
        elif barcode_format == 'Code39':
            # Code39: A-Z, 0-9, espacio, -, ., $, /, +, %
            import re
            if not re.match(r'^[A-Z0-9\s\-\.\$\+\/\%]*$', data_str):
                return False, "Code39: solo A-Z, 0-9, espacio y -.$+/%"
            if len(data_str) > 43:
                return False, "Code39: máximo 43 caracteres"
                
        elif barcode_format == 'EAN13':
            # EAN13: 12 o 13 dígitos
            if not data_str.isdigit():
                return False, "EAN13: solo dígitos"
            if len(data_str) not in [12, 13]:
                return False, "EAN13: debe tener 12 o 13 dígitos"
                
        elif barcode_format == 'EAN8':
            # EAN8: 7 u 8 dígitos
            if not data_str.isdigit():
                return False, "EAN8: solo dígitos"
            if len(data_str) not in [7, 8]:
                return False, "EAN8: debe tener 7 u 8 dígitos"
        
        return True, "Datos válidos"