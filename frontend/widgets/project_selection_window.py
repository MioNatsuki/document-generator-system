# frontend/widgets/project_selection_window.py
"""
Ventana de selección de proyectos después del login
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QMessageBox,
    QToolBar, QStatusBar, QMenu, QMenuBar, QProgressDialog,
    QApplication, QSizePolicy, QSpacerItem, QLineEdit, QComboBox,
    QStackedWidget, QGroupBox, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QAction, QFont, QIcon, QPixmap, QColor, QPainter, QPen, QBrush
import sys
from datetime import datetime
import logging

from config import config
from styles import styles
from utils.api_client import api_client, APIError
from widgets.project_window import ProjectWindow
from widgets.dashboard_window import DashboardWindow
from widgets.sidebar import Sidebar

logger = logging.getLogger(__name__)


class ProjectSelectionWindow(QMainWindow):
    """Ventana principal de selección de proyectos"""
    
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info
        self.proyectos = []
        self.proyectos_filtrados = []
        self.current_filter = "todos"
        
        self.setWindowTitle(f"{config.APP_NAME} - Selección de Proyecto")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(styles.get_main_style())
        
        self.init_ui()
        self.load_proyectos()
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar izquierda (navegación)
        self.sidebar = Sidebar(self.user_info)
        self.sidebar.project_selected.connect(self.open_project)
        self.sidebar.dashboard_selected.connect(self.open_dashboard)
        self.sidebar.logout_requested.connect(self.logout)
        
        # Área principal derecha
        main_area = QWidget()
        main_area_layout = QVBoxLayout()
        main_area_layout.setContentsMargins(20, 20, 20, 20)
        main_area_layout.setSpacing(15)
        
        # Header del área principal
        header_frame = self.create_header()
        main_area_layout.addWidget(header_frame)
        
        # Controles de filtro
        filter_frame = self.create_filter_controls()
        main_area_layout.addWidget(filter_frame)
        
        # Área de proyectos (scrollable)
        self.projects_scroll = QScrollArea()
        self.projects_scroll.setWidgetResizable(True)
        self.projects_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """)
        
        self.projects_container = QWidget()
        self.projects_layout = QGridLayout()
        self.projects_layout.setSpacing(20)
        self.projects_layout.setContentsMargins(10, 10, 10, 10)
        
        self.projects_container.setLayout(self.projects_layout)
        self.projects_scroll.setWidget(self.projects_container)
        
        main_area_layout.addWidget(self.projects_scroll, 1)
        
        # Mensaje cuando no hay proyectos
        self.no_projects_label = QLabel(
            "<h3>No hay proyectos disponibles</h3>"
            "<p>No tienes acceso a ningún proyecto o no hay proyectos creados.</p>"
            "<p>Contacta al administrador del sistema.</p>"
        )
        self.no_projects_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_projects_label.setStyleSheet("""
            color: #666;
            padding: 60px;
            background-color: #f8f9fa;
            border-radius: 15px;
            font-size: 14px;
        """)
        self.no_projects_label.hide()
        
        main_area_layout.addWidget(self.no_projects_label)
        main_area.setLayout(main_area_layout)
        
        # Agregar al layout principal
        main_layout.addWidget(self.sidebar, 0)  # No stretch
        main_layout.addWidget(main_area, 1)     # Stretch
        
        central_widget.setLayout(main_layout)
        
        # Barra de menú
        self.create_menu_bar()
        
        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status(f"Bienvenido, {self.user_info['nombre_completo']} - Rol: {self.user_info['rol']}")
        
        # Barra de herramientas
        self.create_toolbar()
        
    def create_header(self):
        """Crear header del área principal"""
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {config.COLORS['color1']}, 
                    stop:0.5 {config.COLORS['color3']}, 
                    stop:1 {config.COLORS['color5']});
                border-radius: 15px;
                padding: 20px;
            }}
        """)
        
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Título y bienvenida
        title_layout = QVBoxLayout()
        
        welcome_label = QLabel(f"👋 ¡Bienvenido, {self.user_info['nombre_completo']}!")
        welcome_font = QFont()
        welcome_font.setPointSize(16)
        welcome_font.setBold(True)
        welcome_label.setFont(welcome_font)
        welcome_label.setStyleSheet(f"color: {config.COLORS['dark']};")
        
        subtitle_label = QLabel("Selecciona un proyecto para comenzar")
        subtitle_label.setStyleSheet("color: #555; font-size: 14px;")
        
        title_layout.addWidget(welcome_label)
        title_layout.addWidget(subtitle_label)
        
        # Stats rápidos
        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.9);
                border-radius: 10px;
                padding: 15px;
                min-width: 250px;
            }}
        """)
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(5)
        
        role_label = QLabel(f"🎭 Rol: {self.user_info['rol']}")
        role_label.setStyleSheet("font-weight: bold;")
        
        self.projects_count_label = QLabel("📊 Cargando proyectos...")
        self.projects_count_label.setStyleSheet("color: #666;")
        
        last_access_label = QLabel(f"🕒 Último acceso: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        last_access_label.setStyleSheet("color: #666; font-size: 11px;")
        
        stats_layout.addWidget(role_label)
        stats_layout.addWidget(self.projects_count_label)
        stats_layout.addWidget(last_access_label)
        stats_frame.setLayout(stats_layout)
        
        # Botón para crear proyecto (solo superadmin)
        if self.user_info['rol'] == 'SUPERADMIN':
            create_btn = QPushButton("➕ Crear Nuevo Proyecto")
            create_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {config.COLORS['primary']};
                    color: white;
                    border: 2px solid {config.COLORS['primary']};
                    border-radius: 10px;
                    padding: 12px 20px;
                    font-weight: bold;
                    font-size: 14px;
                    min-width: 180px;
                }}
                QPushButton:hover {{
                    background-color: {config.COLORS['success']};
                    border-color: {config.COLORS['success']};
                }}
            """)
            create_btn.clicked.connect(self.create_new_project)
            
            header_layout.addWidget(create_btn)
        
        header_layout.addLayout(title_layout, 1)
        header_layout.addWidget(stats_frame)
        
        header_frame.setLayout(header_layout)
        return header_frame
        
    def create_filter_controls(self):
        """Crear controles de filtro"""
        filter_frame = QFrame()
        filter_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        
        # Filtro por tipo
        filter_label = QLabel("Filtrar por:")
        filter_label.setStyleSheet("font-weight: bold;")
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "Todos los proyectos",
            "Proyectos activos",
            "Proyectos recientes",
            "Mis proyectos asignados"
        ])
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)
        
        # Búsqueda
        search_label = QLabel("Buscar:")
        search_label.setStyleSheet("font-weight: bold;")
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre o descripción...")
        self.search_input.setFixedWidth(250)
        self.search_input.textChanged.connect(self.apply_filter)
        
        # Botón refrescar
        refresh_btn = QPushButton("🔄 Refrescar")
        refresh_btn.setStyleSheet(styles.get_main_style())
        refresh_btn.clicked.connect(self.load_proyectos)
        
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        filter_layout.addWidget(search_label)
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(refresh_btn)
        
        filter_frame.setLayout(filter_layout)
        return filter_frame
        
    def create_menu_bar(self):
        """Crear barra de menú"""
        menubar = self.menuBar()
        
        # Menú Archivo
        file_menu = menubar.addMenu("&Archivo")
        
        refresh_action = QAction("&Refrescar proyectos", self)
        refresh_action.triggered.connect(self.load_proyectos)
        refresh_action.setShortcut("F5")
        file_menu.addAction(refresh_action)
        
        file_menu.addSeparator()
        
        logout_action = QAction("&Cerrar sesión", self)
        logout_action.triggered.connect(self.logout)
        file_menu.addAction(logout_action)
        
        exit_action = QAction("&Salir", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut("Ctrl+Q")
        file_menu.addAction(exit_action)
        
        # Menú Proyecto (solo superadmin)
        if self.user_info['rol'] == 'SUPERADMIN':
            project_menu = menubar.addMenu("&Proyecto")
            
            new_project_action = QAction("&Nuevo proyecto", self)
            new_project_action.triggered.connect(self.create_new_project)
            new_project_action.setShortcut("Ctrl+N")
            project_menu.addAction(new_project_action)
            
            import_project_action = QAction("&Importar desde CSV", self)
            import_project_action.triggered.connect(self.import_project)
            project_menu.addAction(import_project_action)
        
        # Menú Ayuda
        help_menu = menubar.addMenu("&Ayuda")
        
        help_action = QAction("&Documentación", self)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
        
        about_action = QAction("&Acerca de", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_toolbar(self):
        """Crear barra de herramientas"""
        toolbar = self.addToolBar("Principal")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        
        # Acciones principales
        refresh_tool = QAction("🔄 Refrescar", self)
        refresh_tool.triggered.connect(self.load_proyectos)
        toolbar.addAction(refresh_tool)
        
        toolbar.addSeparator()
        
        if self.user_info['rol'] == 'SUPERADMIN':
            new_project_tool = QAction("➕ Nuevo proyecto", self)
            new_project_tool.triggered.connect(self.create_new_project)
            toolbar.addAction(new_project_tool)
            
            toolbar.addSeparator()
        
        settings_tool = QAction("⚙️ Configuración", self)
        settings_tool.triggered.connect(self.show_settings)
        toolbar.addAction(settings_tool)
        
        help_tool = QAction("❓ Ayuda", self)
        help_tool.triggered.connect(self.show_help)
        toolbar.addAction(help_tool)
        
    def load_proyectos(self):
        """Cargar proyectos desde la API"""
        try:
            response = api_client.listar_proyectos()
            self.proyectos = response.get('items', [])
            
            # Filtrar según rol
            if self.user_info['rol'] == 'SUPERADMIN':
                # Superadmin ve todos los proyectos
                self.proyectos_filtrados = self.proyectos
            else:
                # Otros roles solo ven proyectos asignados
                # Por ahora, mostramos todos (en producción filtraríamos por asignación)
                self.proyectos_filtrados = self.proyectos
            
            self.update_projects_display()
            self.update_status(f"Cargados {len(self.proyectos_filtrados)} proyectos")
            
        except APIError as e:
            QMessageBox.critical(self, "Error", f"No se pudieron cargar los proyectos: {str(e)}")
            self.proyectos = []
            self.proyectos_filtrados = []
            self.update_projects_display()
            
    def update_projects_display(self):
        """Actualizar visualización de proyectos"""
        # Limpiar layout
        while self.projects_layout.count():
            child = self.projects_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.proyectos_filtrados:
            self.projects_scroll.hide()
            self.no_projects_label.show()
            self.projects_count_label.setText("📊 0 proyectos disponibles")
            return
        
        self.projects_scroll.show()
        self.no_projects_label.hide()
        
        # Crear cards de proyectos
        columns = 3
        for i, proyecto in enumerate(self.proyectos_filtrados):
            row = i // columns
            col = i % columns
            
            card = self.create_project_card(proyecto)
            self.projects_layout.addWidget(card, row, col)
        
        # Actualizar contador
        self.projects_count_label.setText(f"📊 {len(self.proyectos_filtrados)} proyectos disponibles")
        
    def create_project_card(self, proyecto):
        """Crear card para un proyecto"""
        card = QFrame()
        card.setObjectName("project_card")
        card.setStyleSheet(f"""
            QFrame#project_card {{
                background-color: white;
                border: 2px solid {config.COLORS['color4']};
                border-radius: 15px;
                padding: 20px;
            }}
            QFrame#project_card:hover {{
                border-color: {config.COLORS['primary']};
                background-color: {config.COLORS['color4']}20;
                transform: translateY(-2px);
            }}
        """)
        
        # Efecto hover (CSS no soporta transform, pero lo dejamos para futuro)
        card.setProperty("hover", False)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Header con nombre y estado
        header_layout = QHBoxLayout()
        
        # Icono según tipo de proyecto
        icon_label = QLabel("📁")
        icon_font = QFont()
        icon_font.setPointSize(24)
        icon_label.setFont(icon_font)
        
        # Nombre del proyecto
        name_label = QLabel(proyecto['nombre'])
        name_font = QFont()
        name_font.setPointSize(16)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: {config.COLORS['primary']};")
        name_label.setWordWrap(True)
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(name_label, 1)
        
        # Badge de estado
        status_badge = QLabel("Activo" if proyecto.get('activo', True) else "Inactivo")
        status_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {'#28a745' if proyecto.get('activo', True) else '#dc3545'};
                color: white;
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        header_layout.addWidget(status_badge)
        
        layout.addLayout(header_layout)
        
        # Descripción
        desc_label = QLabel(proyecto.get('descripcion', 'Sin descripción'))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 12px;")
        desc_label.setMaximumHeight(60)
        layout.addWidget(desc_label)
        
        # Estadísticas
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(10)
        
        # Stats simuladas (en producción vendrían de la API)
        stats = [
            ("📄", "Plantillas", "3"),
            ("👥", "Usuarios", "5"),
            ("🖨️", "Emisiones", "45")
        ]
        
        for icon, label, value in stats:
            stat_widget = QWidget()
            stat_layout = QVBoxLayout()
            stat_layout.setSpacing(2)
            stat_layout.setContentsMargins(0, 0, 0, 0)
            
            value_label = QLabel(f"<b>{value}</b>")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet("font-size: 14px;")
            
            label_label = QLabel(label)
            label_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label_label.setStyleSheet("color: #666; font-size: 10px;")
            
            stat_layout.addWidget(value_label)
            stat_layout.addWidget(label_label)
            stat_widget.setLayout(stat_layout)
            stats_layout.addWidget(stat_widget)
        
        stats_frame.setLayout(stats_layout)
        layout.addWidget(stats_frame)
        
        # Botón de acceso
        access_btn = QPushButton("🔓 Abrir Proyecto")
        access_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {config.COLORS['primary']};
                color: white;
                border: 2px solid {config.COLORS['primary']};
                border-radius: 8px;
                padding: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #3a5a8c;
                border-color: #3a5a8c;
            }}
        """)
        access_btn.clicked.connect(lambda checked, p=proyecto: self.open_project(p))
        
        layout.addWidget(access_btn)
        
        # Información adicional
        info_label = QLabel(f"📅 Creado: {proyecto.get('created_at', 'N/A')[:10]}")
        info_label.setStyleSheet("color: #999; font-size: 10px;")
        layout.addWidget(info_label)
        
        card.setLayout(layout)
        
        # Hacer la card clickeable completa
        card.mousePressEvent = lambda event, p=proyecto: self.open_project(p) if event.button() == Qt.MouseButton.LeftButton else None
        
        return card
        
    def apply_filter(self):
        """Aplicar filtros a la lista de proyectos"""
        filter_text = self.filter_combo.currentText()
        search_text = self.search_input.text().lower()
        
        filtered = []
        
        for proyecto in self.proyectos:
            # Filtrar por tipo
            if filter_text == "Proyectos activos" and not proyecto.get('activo', True):
                continue
            elif filter_text == "Mis proyectos asignados":
                # Aquí iría la lógica de asignación real
                # Por ahora, mostramos todos si es superadmin, sino filtramos
                if self.user_info['rol'] != 'SUPERADMIN':
                    # Simulamos que algunos proyectos están asignados
                    if hash(proyecto['nombre']) % 3 != 0:  # Solo algunos proyectos
                        continue
            
            # Filtrar por búsqueda
            if search_text:
                name_match = search_text in proyecto['nombre'].lower()
                desc_match = search_text in proyecto.get('descripcion', '').lower()
                if not (name_match or desc_match):
                    continue
            
            filtered.append(proyecto)
        
        self.proyectos_filtrados = filtered
        self.update_projects_display()
        
    def open_project(self, proyecto):
        """Abrir ventana de proyecto específico"""
        self.project_window = ProjectWindow(proyecto, self.user_info)
        self.project_window.show()
        self.hide()
        
    def open_dashboard(self):
        """Abrir dashboard global (solo superadmin)"""
        if self.user_info['rol'] == 'SUPERADMIN':
            self.dashboard_window = DashboardWindow(self.user_info)
            self.dashboard_window.show()
            self.hide()
        else:
            QMessageBox.warning(
                self,
                "Acceso denegado",
                "Solo los Superadministradores pueden acceder al Dashboard global."
            )
        
    def create_new_project(self):
        """Crear nuevo proyecto"""
        from views.projects_view import NewProjectWizard
        wizard = NewProjectWizard(self)
        wizard.exec()
        
        # Recargar proyectos después de crear uno nuevo
        if wizard.result() == QDialog.DialogCode.Accepted:
            self.load_proyectos()
        
    def import_project(self):
        """Importar proyecto desde CSV"""
        QMessageBox.information(
            self,
            "Importar proyecto",
            "Esta funcionalidad estará disponible en futuras versiones."
        )
        
    def show_settings(self):
        """Mostrar configuración"""
        QMessageBox.information(
            self,
            "Configuración",
            "Configuración del sistema.\n\n"
            f"Usuario: {self.user_info['username']}\n"
            f"Rol: {self.user_info['rol']}\n"
            f"API: {config.API_BASE_URL}"
        )
        
    def show_help(self):
        """Mostrar ayuda"""
        help_text = f"""
        <h3>Ayuda - Selección de Proyectos</h3>
        
        <p><b>Bienvenido a {config.APP_NAME}</b></p>
        
        <p><b>Flujo de trabajo:</b></p>
        <ol>
            <li>Selecciona un proyecto de la lista</li>
            <li>Dentro del proyecto podrás:
                <ul>
                    <li>📄 Gestionar plantillas</li>
                    <li>🖨️ Generar PDFs</li>
                    <li>📊 Ver estadísticas</li>
                    <li>🗃️ Administrar el padrón (según tu rol)</li>
                </ul>
            </li>
        </ol>
        
        <p><b>Tu rol: {self.user_info['rol']}</b></p>
        <ul>
            <li><b>SUPERADMIN:</b> Acceso completo a todos los proyectos</li>
            <li><b>ANALISTA:</b> Solo proyectos asignados, puede crear plantillas</li>
            <li><b>AUXILIAR:</b> Solo proyectos asignados, solo generación de PDFs</li>
        </ul>
        
        <p><b>Atajos de teclado:</b></p>
        <ul>
            <li><b>F5:</b> Refrescar lista de proyectos</li>
            <li><b>Ctrl+N:</b> Nuevo proyecto (solo Superadmin)</li>
            <li><b>Ctrl+Q:</b> Salir de la aplicación</li>
        </ul>
        """
        
        QMessageBox.information(self, "Ayuda", help_text)
        
    def show_about(self):
        """Mostrar información acerca de"""
        about_text = f"""
        <h3>{config.APP_NAME}</h3>
        <p><b>Versión:</b> {config.APP_VERSION}</p>
        <p><b>Descripción:</b> Sistema de Generación Automatizada de Documentos PDF</p>
        <p><b>Desarrollado por:</b> Equipo de Desarrollo</p>
        <p><b>Contacto:</b> soporte@sistema-pdf.com</p>
        
        <p style="color: #666; font-size: 10px;">
        © 2024 - Todos los derechos reservados.<br>
        Este es un sistema empresarial para uso interno.
        </p>
        """
        
        QMessageBox.about(self, f"Acerca de {config.APP_NAME}", about_text)
        
    def logout(self):
        """Cerrar sesión"""
        try:
            api_client.logout()
        except:
            pass
            
        # Mostrar ventana de login
        from main import PDFGeneratorApp
        # Esta parte es compleja porque necesitamos reiniciar el flujo
        # Por ahora, cerramos esta ventana y dejamos que main.py maneje el relogin
        self.close()
        
        # En una implementación real, emitiríamos una señal para que main.py muestre login
        QMessageBox.information(
            self.parent() if self.parent() else self,
            "Sesión cerrada",
            "Tu sesión ha sido cerrada. Por favor, inicia sesión nuevamente."
        )
        
    def update_status(self, message):
        """Actualizar barra de estado"""
        self.status_bar.showMessage(message)
        
    def closeEvent(self, event):
        """Manejar cierre de ventana"""
        reply = QMessageBox.question(
            self,
            "Confirmar salida",
            "¿Estás seguro de salir de la aplicación?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Limpiar sesión
            try:
                api_client.logout()
            except:
                pass
            event.accept()
        else:
            event.ignore()