"""
Utilidades para formateo de texto
"""
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)


class TextFormatter:
    """
    Formateador de texto para valores de campos
    """
    
    def __init__(self):
        self.currency_symbol = "$"
        self.date_format = "%d/%m/%Y"
        self.decimal_separator = ","
        self.thousands_separator = "."
    
    def format_value(self, value: Any, format_spec: Optional[str] = None) -> str:
        """
        Formatear valor según especificación
        
        Args:
            value: Valor a formatear
            format_spec: Especificación de formato
            
        Returns:
            Valor formateado como string
        """
        if value is None:
            return ""
        
        # Si no hay especificación, usar formato por defecto
        if not format_spec:
            return self._auto_format(value)
        
        # Aplicar formato específico
        format_spec = format_spec.lower().strip()
        
        if 'moneda' in format_spec or '$' in format_spec:
            return self._format_currency(value)
        elif 'fecha' in format_spec or 'date' in format_spec:
            return self._format_date(value)
        elif 'número' in format_spec or 'decimal' in format_spec or 'entero' in format_spec:
            return self._format_number(value, format_spec)
        elif 'mayúsculas' in format_spec or 'uppercase' in format_spec:
            return self._format_uppercase(value)
        elif 'minúsculas' in format_spec or 'lowercase' in format_spec:
            return self._format_lowercase(value)
        elif 'capitalize' in format_spec or 'title' in format_spec:
            return self._format_title(value)
        else:
            # Formato personalizado
            return self._apply_custom_format(value, format_spec)
    
    def _auto_format(self, value: Any) -> str:
        """Formateo automático basado en tipo de dato"""
        if isinstance(value, (int, float, Decimal)):
            return self._format_number(value, 'auto')
        elif isinstance(value, datetime):
            return self._format_date(value)
        elif isinstance(value, str):
            return value
        else:
            return str(value)
    
    def _format_currency(self, value: Any) -> str:
        """Formatear como moneda"""
        try:
            # Convertir a número
            if isinstance(value, str):
                # Limpiar caracteres no numéricos
                clean_value = re.sub(r'[^\d,.-]', '', value.replace(self.thousands_separator, ''))
                clean_value = clean_value.replace(self.decimal_separator, '.')
                num_value = float(clean_value)
            else:
                num_value = float(value)
            
            # Formatear con separadores de miles y decimales
            formatted = f"{num_value:,.2f}"
            
            # Reemplazar separadores
            formatted = formatted.replace(",", "X").replace(".", self.decimal_separator).replace("X", self.thousands_separator)
            
            return f"{self.currency_symbol}{formatted}"
            
        except (ValueError, TypeError):
            return str(value)
    
    def _format_date(self, value: Any) -> str:
        """Formatear como fecha"""
        try:
            if isinstance(value, datetime):
                date_obj = value
            elif isinstance(value, str):
                # Intentar parsear la fecha
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d%m%Y"]:
                    try:
                        date_obj = datetime.strptime(value, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return value
            else:
                return str(value)
            
            return date_obj.strftime(self.date_format)
            
        except Exception:
            return str(value)
    
    def _format_number(self, value: Any, format_spec: str) -> str:
        """Formatear como número"""
        try:
            # Convertir a número
            if isinstance(value, (int, float, Decimal)):
                num_value = value
            elif isinstance(value, str):
                # Limpiar caracteres no numéricos
                clean_value = re.sub(r'[^\d,.-]', '', value.replace(self.thousands_separator, ''))
                clean_value = clean_value.replace(self.decimal_separator, '.')
                num_value = float(clean_value)
            else:
                return str(value)
            
            # Determinar formato
            if 'entero' in format_spec or 'integer' in format_spec:
                # Formato entero
                formatted = f"{int(round(num_value)):,}"
            elif 'decimal' in format_spec:
                # Extraer precisión del formato
                match = re.search(r'decimal\((\d+),(\d+)\)', format_spec, re.IGNORECASE)
                if match:
                    total, decimals = int(match.group(1)), int(match.group(2))
                    format_str = f"{{:,.{decimals}f}}"
                    formatted = format_str.format(num_value)
                else:
                    # 2 decimales por defecto
                    formatted = f"{num_value:,.2f}"
            else:
                # Auto: sin decimales si es entero, con decimales si no
                if num_value == int(num_value):
                    formatted = f"{int(num_value):,}"
                else:
                    formatted = f"{num_value:,.2f}"
            
            # Reemplazar separadores
            formatted = formatted.replace(",", "X").replace(".", self.decimal_separator).replace("X", self.thousands_separator)
            
            return formatted
            
        except (ValueError, TypeError):
            return str(value)
    
    def _format_uppercase(self, value: Any) -> str:
        """Convertir a mayúsculas"""
        return str(value).upper()
    
    def _format_lowercase(self, value: Any) -> str:
        """Convertir a minúsculas"""
        return str(value).lower()
    
    def _format_title(self, value: Any) -> str:
        """Convertir a título (primera letra de cada palabra en mayúscula)"""
        return str(value).title()
    
    def _apply_custom_format(self, value: Any, format_spec: str) -> str:
        """Aplicar formato personalizado"""
        try:
            # Ejemplo: "###-##-####" para números
            if '#' in format_spec:
                value_str = str(value).replace(" ", "").replace("-", "").replace(".", "")
                result = ""
                format_index = 0
                value_index = 0
                
                while format_index < len(format_spec) and value_index < len(value_str):
                    if format_spec[format_index] == '#':
                        result += value_str[value_index]
                        value_index += 1
                    else:
                        result += format_spec[format_index]
                    format_index += 1
                
                return result
            
            # Otros formatos personalizados
            return format_spec.replace("{value}", str(value))
            
        except Exception:
            return str(value)
    
    def truncate_text(self, text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncar texto a longitud máxima
        
        Args:
            text: Texto a truncar
            max_length: Longitud máxima
            suffix: Sufijo para indicar truncamiento
            
        Returns:
            Texto truncado
        """
        if len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
    
    def fit_text_to_width(self, text: str, font_name: str, font_size: int, 
                         max_width: float, canvas_obj=None) -> Tuple[List[str], int]:
        """
        Ajustar texto al ancho máximo, dividiendo en líneas si es necesario
        
        Args:
            text: Texto a ajustar
            font_name: Nombre de la fuente
            font_size: Tamaño de fuente inicial
            max_width: Ancho máximo en puntos
            canvas_obj: Objeto canvas de ReportLab (opcional)
            
        Returns:
            Tuple (líneas, tamaño_fuente_ajustado)
        """
        if not canvas_obj:
            # Si no hay canvas, usar estimación simple
            char_width = font_size * 0.6  # Estimación aproximada
            chars_per_line = int(max_width / char_width)
            
            words = text.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                if len(test_line) <= chars_per_line:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
            
            return lines, font_size
        
        # Usar canvas para medida precisa
        lines = []
        words = text.split()
        current_line = []
        current_size = font_size
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            test_width = canvas_obj.stringWidth(test_line, font_name, current_size)
            
            if test_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Si hay muchas líneas, reducir tamaño de fuente
        max_lines = 3  # Máximo de líneas permitidas
        if len(lines) > max_lines and current_size > 8:
            # Reducir tamaño y reintentar
            new_size = current_size - 1
            return self.fit_text_to_width(text, font_name, new_size, max_width, canvas_obj)
        
        return lines, current_size