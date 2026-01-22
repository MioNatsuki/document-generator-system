# frontend/widgets/sidebar.py
"""
Sidebar de navegación por rol
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QListWidget, QListWidgetItem, QSizePolicy,
    QSpacerItem, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QBrush, QPen

from config import config
from styles import styles


class Sidebar(QWidget):
    """Sidebar de navegación con opciones según rol"""
    
    # Señales
    project_selected = pyqtSignal(dict)  # Emitida cuando se selecciona "Todos los proyectos" o proyecto específico
    dashboard_selected = pyqtSignal()     # Emitida cuando se selecciona Dashboard (solo superadmin)
    stats_selected = pyqtSignal()         # Emitida cuando se seleccionan Estadísticas
    bitacora_selected = pyqtSignal()      # Emitida cuando se selecciona Bitácora (solo superadmin)
    logout_requested = pyqtSignal()       # Emitida cuando se solicita logout
    
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info
        
        self.setFixedWidth(250)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {config.COLORS['color4']}20;
                border-right: 2px solid {config.COLORS['color4']}40;
            }}
        """)
        
        self.init_ui()
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(15)
        
        # Logo/Header
        header_frame = self.create_header()
        layout.addWidget(header_frame)
        
        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {config.COLORS['color4']}60;")
        separator.setFixedHeight(2)
        layout.addWidget(separator)
        
        # Navegación principal
        nav_widget = self.create_navigation()
        layout.addWidget(nav_widget)
        
        # Espacio flexible
        layout.addStretch(1)
        
        # Footer con usuario
        footer_frame = self.create_footer()
        layout.addWidget(footer_frame)
        
        self.setLayout(layout)
        
    def create_header(self):
        """Crear header del sidebar"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: transparent;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Logo/icono
        icon_label = QLabel("📄")
        icon_font = QFont()
        icon_font.setPointSize(32)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Nombre de la app (abreviado)
        app_label = QLabel("PDF Generator")
        app_font = QFont()
        app_font.setPointSize(14)
        app_font.setBold(True)
        app_label.setFont(app_font)
        app_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_label.setStyleSheet(f"color: {config.COLORS['primary']};")
        
        layout.addWidget(icon_label)
        layout.addWidget(app_label)
        
        header.setLayout(layout)
        return header
        
    def create_navigation(self):
        """Crear navegación según rol"""
        nav_widget = QWidget()
        nav_layout = QVBoxLayout()
        nav_layout.setSpacing(5)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        
        # Elementos comunes a todos los roles
        common_items = [
            ("🏠", "Inicio", "home", None),
            ("📁", "Todos los proyectos", "all_projects", None),
            ("📊", "Mis estadísticas", "my_stats", None),
        ]
        
        # Elementos según rol
        role_items = {
            "SUPERADMIN": [
                ("📈", "Dashboard global", "dashboard", None),
                ("👥", "Gestión de usuarios", "users", None),
                ("📋", "Bitácora del sistema", "bitacora", None),
                ("⚙️", "Configuración", "settings", None),
            ],
            "ANALISTA": [
                ("📄", "Mis plantillas", "templates", None),
                ("📈", "Reportes", "reports", None),
            ],
            "AUXILIAR": [
                ("🖨️", "Generar PDFs", "generate", None),
                ("📋", "Mis tareas", "tasks", None),
            ]
        }
        
        # Agregar elementos comunes
        for icon, text, action_id, project in common_items:
            btn = self.create_nav_button(icon, text, action_id, project)
            nav_layout.addWidget(btn)
        
        # Separador
        if role_items.get(self.user_info['rol']):
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setStyleSheet(f"background-color: {config.COLORS['color4']}40;")
            separator.setFixedHeight(1)
            nav_layout.addWidget(separator)
            
            # Agregar elementos específicos del rol
            for icon, text, action_id, project in role_items[self.user_info['rol']]:
                btn = self.create_nav_button(icon, text, action_id, project)
                nav_layout.addWidget(btn)
        
        nav_widget.setLayout(nav_layout)
        return nav_widget
        
    def create_nav_button(self, icon, text, action_id, project=None):
        """Crear botón de navegación"""
        btn = QPushButton(f"{icon} {text}")
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {config.COLORS['dark']};
                border: none;
                border-radius: 8px;
                padding: 12px 15px;
                text-align: left;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {config.COLORS['color4']}40;
                color: {config.COLORS['primary']};
            }}
            QPushButton:pressed {{
                background-color: {config.COLORS['color4']}60;
            }}
        """)
        
        # Conectar señal según acción
        if action_id == "all_projects":
            btn.clicked.connect(lambda: self.project_selected.emit(None))
        elif action_id == "dashboard":
            btn.clicked.connect(self.dashboard_selected.emit)
        elif action_id == "my_stats":
            btn.clicked.connect(self.stats_selected.emit)
        elif action_id == "bitacora":
            btn.clicked.connect(self.bitacora_selected.emit)
        elif project:
            btn.clicked.connect(lambda: self.project_selected.emit(project))
        
        return btn
        
    def create_footer(self):
        """Crear footer con información del usuario"""
        footer = QFrame()
        footer.setStyleSheet(f"""
            QFrame {{
                background-color: {config.COLORS['color4']}40;
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # Información del usuario
        user_label = QLabel(f"👤 {self.user_info['nombre_completo']}")
        user_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        
        role_label = QLabel(f"🎭 {self.user_info['rol']}")
        role_label.setStyleSheet("color: #666; font-size: 11px;")
        
        # Botón de logout
        logout_btn = QPushButton("🚪 Cerrar sesión")
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {config.COLORS['danger']}20;
                color: {config.COLORS['danger']};
                border: 1px solid {config.COLORS['danger']}40;
                border-radius: 6px;
                padding: 8px;
                font-size: 11px;
                margin-top: 10px;
            }}
            QPushButton:hover {{
                background-color: {config.COLORS['danger']}40;
            }}
        """)
        logout_btn.clicked.connect(self.logout_requested.emit)
        
        layout.addWidget(user_label)
        layout.addWidget(role_label)
        layout.addWidget(logout_btn)
        
        footer.setLayout(layout)
        return footer