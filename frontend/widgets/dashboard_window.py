# Ventana de dashboard 
# Ventana de dashboard 
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame,
    QMenuBar, QMenu, QStatusBar, QMessageBox, QGridLayout,
    QScrollArea, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QToolBar, QSizePolicy,
    QTabWidget, QDialog, QDialogButtonBox, QLineEdit,
    QTextEdit, QFileDialog, QProgressDialog, QApplication,
    QCheckBox, QComboBox, QSpinBox, QDateEdit, QDateTimeEdit,
    QListWidget, QListWidgetItem, QSplitter, QToolButton,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QDate, QDateTime
from PyQt6.QtGui import QAction, QFont, QIcon, QPixmap, QColor, QPalette
import sys
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from ..config import config
from ..styles import styles
from ..utils.api_client import api_client, APIError
from ..utils.file_dialogs import FileDialog
from .project_window import ProjectWindow
from ..views.projects_view import NewProjectWizard


class DashboardWindow(QMainWindow):
    """Ventana principal del dashboard"""
    
    def __init__(self, user_info: dict):
        super().__init__()
        self.user_info = user_info
        self.current_project = None
        self.projects = []
        
        self.setWindowTitle(f"{config.APP_NAME} - Dashboard")
        self.setGeometry(100, 100, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.setStyleSheet(styles.get_main_style())
        
        # Timer para refrescar datos periódicamente
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # Refrescar cada 30 segundos
        
        self.init_ui()
        self.load_projects()
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        # Crear widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        self.sidebar = self.create_sidebar()
        main_layout.addWidget(self.sidebar)
        
        # Área principal
        self.main_area = QStackedWidget()
        main_layout.addWidget(self.main_area, 1)
        
        # Páginas
        self.projects_page = self.create_projects_page()
        self.empty_page = self.create_empty_page()
        
        self.main_area.addWidget(self.projects_page)
        self.main_area.addWidget(self.empty_page)
        
        central_widget.setLayout(main_layout)
        
        # Barra de menú
        self.create_menu_bar()
        
        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status_bar()
        
        # Barra de herramientas
        self.create_toolbar()
        
    def create_menu_bar(self):
        """Crear barra de menú"""
        menubar = self.menuBar()
        
        # Menú Archivo
        file_menu = menubar.addMenu("&Archivo")
        
        new_project_action = QAction("&Nuevo Proyecto", self)
        new_project_action.triggered.connect(self.show_new_project_dialog)
        new_project_action.setShortcut("Ctrl+N")
        file_menu.addAction(new_project_action)
        
        file_menu.addSeparator()
        
        refresh_action = QAction("&Refrescar", self)
        refresh_action.triggered.connect(self.refresh_data)
        refresh_action.setShortcut("F5")
        file_menu.addAction(refresh_action)
        
        file_menu.addSeparator()
        
        logout_action = QAction("&Cerrar Sesión", self)
        logout_action.triggered.connect(self.logout)
        logout_action.setShortcut("Ctrl+Q")
        file_menu.addAction(logout_action)
        
        exit_action = QAction("&Salir", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut("Alt+F4")
        file_menu.addAction(exit_action)
        
        # Menú Editar (placeholder)
        edit_menu = menubar.addMenu("&Editar")
        
        # Menú Ver
        view_menu = menubar.addMenu("&Ver")
        
        toggle_sidebar_action = QAction("&Mostrar/Ocultar Sidebar", self)
        toggle_sidebar_action.triggered.connect(self.toggle_sidebar)
        toggle_sidebar_action.setShortcut("Ctrl+B")
        view_menu.addAction(toggle_sidebar_action)
        
        # Menú Ayuda
        help_menu = menubar.addMenu("&Ayuda")
        
        docs_action = QAction("&Documentación", self)
        docs_action.triggered.connect(self.show_documentation)
        help_menu.addAction(docs_action)
        
        about_action = QAction("&Acerca de", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_toolbar(self):
        """Crear barra de herramientas"""
        toolbar = QToolBar("Herramientas principales")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Botón de nuevo proyecto (solo para superadmin)
        if self.user_info['rol'] == 'SUPERADMIN':
            new_project_tool = QAction(QIcon(), "Nuevo Proyecto", self)
            new_project_tool.triggered.connect(self.show_new_project_dialog)
            toolbar.addAction(new_project_tool)
        
        # Botón de refrescar
        refresh_tool = QAction(QIcon(), "Refrescar", self)
        refresh_tool.triggered.connect(self.refresh_data)
        toolbar.addAction(refresh_tool)
        
        toolbar.addSeparator()
        
        # Selector de vista
        self.view_combo = QComboBox()
        self.view_combo.addItems(["Vista Tarjetas", "Vista Lista", "Vista Tabla"])
        self.view_combo.currentTextChanged.connect(self.change_view_mode)
        toolbar.addWidget(QLabel("Vista:"))
        toolbar.addWidget(self.view_combo)
        
    def create_sidebar(self):
        """Crear sidebar"""
        sidebar = QFrame()
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {config.COLORS['color4']};
                border-right: 3px solid {config.COLORS['color5']};
            }}
        """)
        sidebar.setFixedWidth(280)
        
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setSpacing(15)
        
        # Logo/header
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: transparent;")
        header_layout = QVBoxLayout()
        
        # Icono de la aplicación
        icon_label = QLabel("📕")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_font = QFont()
        icon_font.setPointSize(48)
        icon_label.setFont(icon_font)
        
        app_name_label = QLabel("Generador de Documentos")
        app_name_font = QFont()
        app_name_font.setPointSize(16)
        app_name_font.setBold(True)
        app_name_label.setFont(app_name_font)
        app_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_name_label.setStyleSheet(f"color: {config.COLORS['dark']};")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(app_name_label)
        header_frame.setLayout(header_layout)
        
        # Información del usuario
        user_frame = QFrame()
        user_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {config.COLORS['color3']};
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        user_layout = QVBoxLayout()
        user_layout.setSpacing(8)
        
        # Avatar/icono de usuario
        user_icon = QLabel("🙍🏻‍♂️")
        user_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_icon_font = QFont()
        user_icon_font.setPointSize(24)
        user_icon.setFont(user_icon_font)
        
        user_name = QLabel(self.user_info['nombre_completo'])
        user_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_name.setStyleSheet(f"font-weight: bold; color: {config.COLORS['dark']};")
        user_name.setWordWrap(True)
        
        user_role = QLabel(f"Rol: {self.user_info['rol']}")
        user_role.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_role.setStyleSheet(f"color: {config.COLORS['dark']};")
        
        user_layout.addWidget(user_icon)
        user_layout.addWidget(user_name)
        user_layout.addWidget(user_role)
        user_frame.setLayout(user_layout)
        
        # Navegación
        nav_group = QGroupBox("Navegación")
        nav_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {config.COLORS['primary']};
            }}
        """)
        nav_layout = QVBoxLayout()
        nav_layout.setSpacing(8)
        
        # Botones de navegación
        self.projects_btn = QPushButton("🗃️ Mis Proyectos")
        self.projects_btn.setStyleSheet(styles.get_main_style())
        self.projects_btn.clicked.connect(self.show_projects_page)
        
        # Según rol, mostrar diferentes opciones
        if self.user_info['rol'] == 'SUPERADMIN':
            admin_btn = QPushButton("👨🏻‍💻 Administración")
            admin_btn.setStyleSheet(styles.get_main_style())
            admin_btn.clicked.connect(self.show_admin_panel)
            nav_layout.addWidget(admin_btn)
            
            logs_btn = QPushButton("📋 Bitácora")
            logs_btn.setStyleSheet(styles.get_main_style())
            logs_btn.clicked.connect(self.show_logs)
            nav_layout.addWidget(logs_btn)
            
            stats_btn = QPushButton("📊 Estadísticas Globales")
            stats_btn.setStyleSheet(styles.get_main_style())
            stats_btn.clicked.connect(self.show_global_stats)
            nav_layout.addWidget(stats_btn)
            
        elif self.user_info['rol'] == 'ANALISTA':
            stats_btn = QPushButton("📈 Estadísticas")
            stats_btn.setStyleSheet(styles.get_main_style())
            stats_btn.clicked.connect(self.show_project_stats)
            nav_layout.addWidget(stats_btn)
            
        else:  # AUXILIAR
            my_stats_btn = QPushButton("📉 Mis Estadísticas")
            my_stats_btn.setStyleSheet(styles.get_main_style())
            my_stats_btn.clicked.connect(self.show_own_stats)
            nav_layout.addWidget(my_stats_btn)
        
        nav_layout.addWidget(self.projects_btn)
        nav_layout.addStretch()
        
        nav_group.setLayout(nav_layout)
        
        # Información del sistema
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {config.COLORS['color2']}40;
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        info_layout = QVBoxLayout()
        
        version_label = QLabel(f"Versión: {config.APP_VERSION}")
        version_label.setStyleSheet("color: #666; font-size: 10px;")
        
        status_label = QLabel("Conectado")
        status_label.setStyleSheet("color: #28a745; font-size: 10px; font-weight: bold;")
        
        info_layout.addWidget(version_label)
        info_layout.addWidget(status_label)
        info_frame.setLayout(info_layout)
        
        # Botón de logout
        logout_btn = QPushButton("🏃🚪 Cerrar Sesión")
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {config.COLORS['danger']};
                color: white;
                border: 2px solid {config.COLORS['danger']};
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: #c53030;
                border-color: #c53030;
            }}
        """)
        logout_btn.clicked.connect(self.logout)
        
        # Agregar al sidebar
        sidebar_layout.addWidget(header_frame)
        sidebar_layout.addWidget(user_frame)
        sidebar_layout.addWidget(nav_group, 1)  # Stretch factor 1
        sidebar_layout.addWidget(info_frame)
        sidebar_layout.addWidget(logout_btn)
        
        sidebar.setLayout(sidebar_layout)
        return sidebar
        
    def create_projects_page(self):
        """Crear página de listado de proyectos"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_frame = QFrame()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("Mis Proyectos")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Controles de búsqueda/filtro
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar proyectos...")
        self.search_input.setFixedWidth(250)
        self.search_input.textChanged.connect(self.filter_projects)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Todos", "Activos", "Recientes", "Con emisiones"])
        self.filter_combo.currentTextChanged.connect(self.filter_projects)
        
        search_layout.addWidget(QLabel("Filtrar:"))
        search_layout.addWidget(self.filter_combo)
        search_layout.addStretch()
        search_layout.addWidget(QLabel("Buscar:"))
        search_layout.addWidget(self.search_input)
        
        header_layout.addLayout(search_layout)
        header_frame.setLayout(header_layout)
        
        # Área de proyectos
        projects_area = QScrollArea()
        projects_area.setWidgetResizable(True)
        projects_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        self.projects_container = QWidget()
        self.projects_container_layout = QVBoxLayout()
        self.projects_container_layout.setSpacing(15)
        
        # Vista inicial: mensaje de carga
        self.loading_label = QLabel("Cargando proyectos...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("color: #666; font-style: italic; font-size: 14px;")
        
        self.projects_container_layout.addWidget(self.loading_label)
        self.projects_container_layout.addStretch()
        
        self.projects_container.setLayout(self.projects_container_layout)
        projects_area.setWidget(self.projects_container)
        
        # Agregar al layout principal
        layout.addWidget(header_frame)
        layout.addWidget(projects_area)
        
        page.setLayout(layout)
        return page
        
    def create_empty_page(self):
        """Crear página vacía"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Mensaje centrado
        message_label = QLabel("Selecciona una opción del menú")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("color: #666; font-size: 16px; margin-top: 100px;")
        
        layout.addWidget(message_label)
        layout.addStretch()
        
        page.setLayout(layout)
        return page
        
    def show_projects_page(self):
        """Mostrar página de proyectos"""
        self.main_area.setCurrentWidget(self.projects_page)
        self.load_projects()
        
    def load_projects(self):
        """Cargar proyectos desde la API"""
        try:
            response = api_client.listar_proyectos()
            self.projects = response.get("items", [])
            
            # Limpiar contenedor
            for i in reversed(range(self.projects_container_layout.count())):
                widget = self.projects_container_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
            
            if not self.projects:
                # Mostrar mensaje de no proyectos
                no_projects_label = QLabel("No tienes proyectos asignados")
                no_projects_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                no_projects_label.setStyleSheet("color: #666; font-size: 14px; margin-top: 50px;")
                self.projects_container_layout.addWidget(no_projects_label)
            else:
                # Mostrar proyectos como tarjetas
                for project in self.projects:
                    project_card = self.create_project_card(project)
                    self.projects_container_layout.addWidget(project_card)
            
            self.projects_container_layout.addStretch()
            
            # Actualizar status bar
            self.update_status_bar(f"{len(self.projects)} proyectos cargados")
            
        except APIError as e:
            QMessageBox.critical(self, "Error", f"No se pudieron cargar los proyectos: {str(e)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error inesperado: {str(e)}")
            
    def create_project_card(self, project: Dict[str, Any]) -> QFrame:
        """Crear tarjeta de proyecto"""
        card = QFrame()
        card.setObjectName("project_card")
        card.setStyleSheet(styles.get_card_style())
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.setSpacing(10)
        
        # Header de la tarjeta
        header_layout = QHBoxLayout()
        
        # Icono del proyecto
        icon_label = QLabel("🗂️")
        icon_font = QFont()
        icon_font.setPointSize(24)
        icon_label.setFont(icon_font)
        
        # Información del proyecto
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        name_label = QLabel(project['nombre'])
        name_font = QFont()
        name_font.setPointSize(14)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: {config.COLORS['primary']};")
        
        if project.get('descripcion'):
            desc_label = QLabel(project['descripcion'])
            desc_label.setStyleSheet("color: #666;")
            desc_label.setWordWrap(True)
            info_layout.addWidget(desc_label)
        
        info_layout.addWidget(name_label)
        
        # Fecha de creación
        created_at = project.get('created_at', '')
        if created_at:
            date_label = QLabel(f"Creado: {created_at[:10]}")
            date_label.setStyleSheet("color: #999; font-size: 10px;")
            info_layout.addWidget(date_label)
        
        header_layout.addWidget(icon_label)
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        # Badge de estado
        status_badge = QLabel("Activo")
        status_badge.setStyleSheet(styles.get_badge_style("success"))
        header_layout.addWidget(status_badge)
        
        # Botones de acción
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(5)
        
        open_btn = QPushButton("Abrir")
        open_btn.setStyleSheet(styles.get_main_style())
        open_btn.setFixedSize(80, 30)
        open_btn.clicked.connect(lambda: self.open_project(project))
        
        # Solo superadmin puede eliminar
        if self.user_info['rol'] == 'SUPERADMIN':
            delete_btn = QPushButton("Eliminar")
            delete_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {config.COLORS['danger']};
                    color: white;
                    border: 1px solid {config.COLORS['danger']};
                    border-radius: 4px;
                    padding: 2px 8px;
                }}
                
                QPushButton:hover {{
                    background-color: #c53030;
                }}
            """)
            delete_btn.setFixedSize(80, 30)
            delete_btn.clicked.connect(lambda: self.delete_project(project))
            actions_layout.addWidget(delete_btn)
        
        actions_layout.addWidget(open_btn)
        
        # Agregar al layout de la tarjeta
        card_layout.addLayout(header_layout)
        card_layout.addLayout(actions_layout)
        
        card.setLayout(card_layout)
        
        # Hacer toda la tarjeta clickeable (excepto los botones)
        card.mousePressEvent = lambda e: self.open_project(project) if e.button() == Qt.MouseButton.LeftButton else None
        
        return card
        
    def open_project(self, project):
        """Abrir ventana de proyecto"""
        try:
            # Obtener proyecto actualizado
            project_data = api_client.obtener_proyecto(project['id'])
            
            # Crear y mostrar ventana de proyecto
            self.project_window = ProjectWindow(project_data, self.user_info)
            self.project_window.show()
            
            # Actualizar status bar
            self.update_status_bar(f"Proyecto abierto: {project['nombre']}")
            
        except APIError as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el proyecto: {str(e)}")
            
    def delete_project(self, project):
        """Eliminar proyecto"""
        # Diálogo de confirmación
        confirm_dialog = QMessageBox()
        confirm_dialog.setIcon(QMessageBox.Icon.Warning)
        confirm_dialog.setWindowTitle("Confirmar eliminación")
        confirm_dialog.setText(f"¿Estás seguro de eliminar el proyecto '{project['nombre']}'?")
        confirm_dialog.setInformativeText(
            "Esta acción eliminará el proyecto, su padrón y TODAS las plantillas asociadas.\n\n"
            "Esta acción es irreversible."
        )
        confirm_dialog.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm_dialog.setDefaultButton(QMessageBox.StandardButton.No)
        
        # Agregar checkbox de confirmación adicional
        check_box = QCheckBox("Entiendo que esta acción es irreversible")
        confirm_dialog.setCheckBox(check_box)
        
        # Mostrar diálogo y verificar
        reply = confirm_dialog.exec()
        
        if reply == QMessageBox.StandardButton.Yes and check_box.isChecked():
            try:
                # Eliminar proyecto
                response = api_client.eliminar_proyecto(project['id'])
                
                QMessageBox.information(
                    self,
                    "Proyecto eliminado",
                    f"El proyecto '{project['nombre']}' ha sido eliminado exitosamente.\n\n"
                    f"Emisiones históricas: {response.get('emisiones_historicas', 0)}"
                )
                
                # Recargar lista de proyectos
                self.load_projects()
                
            except APIError as e:
                QMessageBox.critical(self, "Error", f"No se pudo eliminar el proyecto: {str(e)}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error inesperado: {str(e)}")
                
        elif reply == QMessageBox.StandardButton.Yes and not check_box.isChecked():
            QMessageBox.warning(
                self,
                "Confirmación requerida",
                "Debes marcar la casilla de confirmación para eliminar el proyecto."
            )
            
    def filter_projects(self):
        """Filtrar proyectos según criterios"""
        search_text = self.search_input.text().lower()
        filter_text = self.filter_combo.currentText()
        
        # Por implementar: lógica de filtrado
        
    def show_new_project_dialog(self):
        """Mostrar diálogo para crear nuevo proyecto"""
        if self.user_info['rol'] != 'SUPERADMIN':
            QMessageBox.warning(
                self,
                "Permisos insuficientes",
                "Solo los usuarios SUPERADMIN pueden crear nuevos proyectos."
            )
            return
            
        wizard = NewProjectWizard(self)
        if wizard.exec():
            self.load_projects()
            
    def change_view_mode(self, mode: str):
        """Cambiar modo de vista de proyectos"""
        # Por implementar: cambiar entre vista tarjetas, lista y tabla
        
    def toggle_sidebar(self):
        """Mostrar/ocultar sidebar"""
        if self.sidebar.isVisible():
            self.sidebar.hide()
        else:
            self.sidebar.show()
            
    def refresh_data(self):
        """Refrescar datos del dashboard"""
        self.load_projects()
        
    def update_status_bar(self, message: str = ""):
        """Actualizar barra de estado"""
        if not message:
            message = f"Usuario: {self.user_info['nombre_completo']} | Rol: {self.user_info['rol']} | Proyectos: {len(self.projects)}"
        
        self.status_bar.showMessage(message)
        
    def show_admin_panel(self):
        """Mostrar panel de administración (placeholder)"""
        QMessageBox.information(
            self,
            "Próximamente",
            "El panel de administración estará disponible en futuras versiones."
        )
        
    def show_logs(self):
        """Mostrar bitácora (placeholder)"""
        QMessageBox.information(
            self,
            "Próximamente",
            "La bitácora del sistema estará disponible en la parte 5."
        )
        
    def show_global_stats(self):
        """Mostrar estadísticas globales (placeholder)"""
        QMessageBox.information(
            self,
            "Próximamente",
            "Las estadísticas globales estarán disponibles en la parte 5."
        )
        
    def show_project_stats(self):
        """Mostrar estadísticas de proyecto (placeholder)"""
        QMessageBox.information(
            self,
            "Próximamente",
            "Las estadísticas de proyecto estarán disponibles en la parte 5."
        )
        
    def show_own_stats(self):
        """Mostrar estadísticas personales (placeholder)"""
        QMessageBox.information(
            self,
            "Próximamente",
            "Las estadísticas personales estarán disponibles en la parte 5."
        )
        
    def show_documentation(self):
        """Mostrar documentación (placeholder)"""
        QMessageBox.information(
            self,
            "Documentación",
            "La documentación del sistema estará disponible en la versión final."
        )
        
    def show_about(self):
        """Mostrar información acerca de la aplicación"""
        about_text = f"""
        <h2>{config.APP_NAME}</h2>
        <p>Versión: {config.APP_VERSION}</p>
        <p>Sistema de Generación Automatizada de Documentos PDF</p>
        
        <h3>Características:</h3>
        <ul>
            <li>✔ Gestión de proyectos con tablas dinámicas</li>
            <li>✔ Carga y validación de CSVs</li>
            <li>✔ Sistema de plantillas configurables</li>
            <li>✔ Generación masiva de PDFs</li>
            <li>✔ Códigos de barras automáticos</li>
            <li>✔ Sistema de roles y permisos</li>
        </ul>
        
        <p><strong>Usuario actual:</strong> {self.user_info['nombre_completo']}</p>
        <p><strong>Rol:</strong> {self.user_info['rol']}</p>
        
        <p style="color: #666; font-size: 10px;">
        Desarrollado con Python, FastAPI y PyQt6
        </p>
        """
        
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Acerca de")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(about_text)
        msg_box.setIconPixmap(QPixmap())
        msg_box.exec()
        
    def logout(self):
        """Cerrar sesión"""
        try:
            api_client.logout()
        except:
            pass  # Ignorar errores en logout
        
        self.close()
        
    def closeEvent(self, event):
        """Manejar cierre de ventana"""
        # Detener timers
        self.refresh_timer.stop()
        
        # Preguntar si realmente quiere salir
        reply = QMessageBox.question(
            self,
            "Confirmar salida",
            "¿Estás seguro de que quieres salir de la aplicación?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()