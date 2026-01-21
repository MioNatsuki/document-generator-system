"""
Widget para mostrar tarjetas de KPI
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from config import config


class KPICard(QFrame):
    """Tarjeta para mostrar un KPI"""
    
    def __init__(self, title, icon, color):
        super().__init__()
        self.title = title
        self.icon = icon
        self.color = color
        
        self.init_ui()
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self.color}20;
                border: 2px solid {self.color};
                border-radius: 12px;
                padding: 15px;
            }}
            QFrame:hover {{
                background-color: {self.color}30;
                border-width: 3px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header con icono y título
        header_layout = QHBoxLayout()
        
        icon_label = QLabel(self.icon)
        icon_font = QFont()
        icon_font.setPointSize(24)
        icon_label.setFont(icon_font)
        
        title_label = QLabel(self.title)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {config.COLORS['dark']};")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Valor del KPI
        self.value_label = QLabel("0")
        value_font = QFont()
        value_font.setPointSize(28)
        value_font.setBold(True)
        self.value_label.setFont(value_font)
        self.value_label.setStyleSheet(f"color: {self.color};")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.value_label)
        
        # Footer para información adicional
        self.footer_label = QLabel("")
        self.footer_label.setStyleSheet("color: #666; font-size: 10px;")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.footer_label)
        
    def set_value(self, value):
        """Establecer valor del KPI"""
        self.value_label.setText(value)
        
    def set_value_color(self, color):
        """Cambiar color del valor"""
        self.value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")
        
    def set_footer(self, text):
        """Establecer texto del footer"""
        self.footer_label.setText(text)