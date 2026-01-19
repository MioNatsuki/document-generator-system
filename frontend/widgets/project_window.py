# Ventana de proyecto 
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QFrame, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QProgressDialog, QApplication, QInputDialog,
    QComboBox, QLineEdit, QTextEdit, QCheckBox, QSplitter,
    QToolBar, QStatusBar, QMenu, QMenuBar, QTreeWidget,
    QTreeWidgetItem, QScrollArea, QFormLayout, QSpinBox,
    QDateEdit, QDateTimeEdit, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QRadioButton, QButtonGroup, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QDate, QDateTime
from PyQt6.QtGui import QAction, QFont, QIcon, QPixmap, QColor, QPalette
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
from pathlib import Path
import tempfile

from ..config import config
from ..styles import styles
from ..utils.api_client import api_client, APIError
from ..utils.file_dialogs import FileDialog


class ProjectWindow(QMainWindow):
    """Ventana de detalle de proyecto"""
    
    def __init__(self, project: Dict[str, Any], user_info: Dict[str, Any]):
        super().__init__()
        self.project = project
        self.user_info = user_info
        self.padron_structure = []
        self.padron_sample = []
        
        self.setWindowTitle(f"{config.APP_NAME} - {project['nombre']}")
        self.setGeometry(150, 150, 1100, 750)
        self.setStyleSheet(styles.get_main_style())
        
        # Timer para refrescar datos
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_project_data)
        self.refresh_timer.start(60000)  # Refrescar cada minuto
        
        self.init_ui()
        self.load_project_details()
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header del proyecto
        self.header = self.create_project_header()
        main_layout.addWidget(self.header)
        
        # Tabs principales
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setDocumentMode(True)
        
        # Crear pestañas según permisos
        self.create_tabs()
        
        main_layout.addWidget(self.tabs)
        
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
        """Crear barra de menú específica del proyecto"""
        menubar = self.menuBar()
        
        # Menú Proyecto
        project_menu = menubar.addMenu("&Proyecto")
        
        refresh_action = QAction("&Refrescar", self)
        refresh_action.triggered.connect(self.refresh_project_data)
        refresh_action.setShortcut("F5")
        project_menu.addAction(refresh_action)
        
        project_menu.addSeparator()
        
        # Solo superadmin puede editar proyecto
        if self.user_info['rol'] == 'SUPERADMIN':
            edit_action = QAction("&Editar proyecto", self)
            edit_action.triggered.connect(self.edit_project)
            project_menu.addAction(edit_action)
            
            delete_action = QAction("&Eliminar proyecto", self)
            delete_action.triggered.connect(self.delete_project)
            project_menu.addAction(delete_action)
        
        project_menu.addSeparator()
        
        close_action = QAction("&Cerrar", self)
        close_action.triggered.connect(self.close)
        close_action.setShortcut("Ctrl+W")
        project_menu.addAction(close_action)
        
        # Menú Padrón (solo para superadmin y analista)
        if self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
            padron_menu = menubar.addMenu("&Padrón")
            
            load_padron_action = QAction("&Cargar datos", self)
            load_padron_action.triggered.connect(self.load_padron)
            padron_menu.addAction(load_padron_action)
            
            export_padron_action = QAction("&Exportar datos", self)
            export_padron_action.triggered.connect(self.export_padron)
            padron_menu.addAction(export_padron_action)
            
            padron_menu.addSeparator()
            
            structure_action = QAction("&Ver estructura", self)
            structure_action.triggered.connect(self.show_padron_structure)
            padron_menu.addAction(structure_action)
        
        # Menú Plantillas (solo para superadmin y analista)
        if self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
            templates_menu = menubar.addMenu("&Plantillas")
            
            new_template_action = QAction("&Nueva plantilla", self)
            new_template_action.triggered.connect(self.new_template)
            templates_menu.addAction(new_template_action)
            
            templates_menu.addSeparator()
            
            list_templates_action = QAction("&Listar plantillas", self)
            list_templates_action.triggered.connect(self.list_templates)
            templates_menu.addAction(list_templates_action)
        
        # Menú Emisión
        emission_menu = menubar.addMenu("&Emisión")
        
        generate_action = QAction("&Generar PDFs", self)
        generate_action.triggered.connect(self.generate_pdfs)
        emission_menu.addAction(generate_action)
        
    def create_toolbar(self):
        """Crear barra de herramientas específica del proyecto"""
        toolbar = self.addToolBar("Proyecto")
        toolbar.setMovable(False)
        
        refresh_tool = QAction("🔄 Refrescar", self)
        refresh_tool.triggered.connect(self.refresh_project_data)
        toolbar.addAction(refresh_tool)
        
        toolbar.addSeparator()
        
        # Según pestaña activa, mostrar herramientas específicas
        self.tab_specific_tools = {}
        
        # Herramientas para padrón
        if self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
            padron_tools = QToolBar("Padrón")
            padron_tools.setVisible(False)
            
            load_padron_tool = QAction("📥 Cargar CSV", self)
            load_padron_tool.triggered.connect(self.load_padron)
            
            export_padron_tool = QAction("📤 Exportar", self)
            export_padron_tool.triggered.connect(self.export_padron)
            
            padron_tools.addAction(load_padron_tool)
            padron_tools.addAction(export_padron_tool)
            
            self.addToolBar(padron_tools)
            self.tab_specific_tools["padron"] = padron_tools
        
        # Herramientas para plantillas
        if self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
            templates_tools = QToolBar("Plantillas")
            templates_tools.setVisible(False)
            
            new_template_tool = QAction("➕ Nueva", self)
            new_template_tool.triggered.connect(self.new_template)
            
            templates_tools.addAction(new_template_tool)
            
            self.addToolBar(templates_tools)
            self.tab_specific_tools["plantillas"] = templates_tools
        
        # Conectar cambio de tab para mostrar/ocultar herramientas
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
    def on_tab_changed(self, index):
        """Manejar cambio de pestaña"""
        # Ocultar todas las herramientas específicas
        for tools in self.tab_specific_tools.values():
            tools.setVisible(False)
        
        # Mostrar herramientas de la pestaña actual
        tab_name = self.tabs.tabText(index).lower()
        if "padrón" in tab_name and "padron" in self.tab_specific_tools:
            self.tab_specific_tools["padron"].setVisible(True)
        elif "plantillas" in tab_name and "plantillas" in self.tab_specific_tools:
            self.tab_specific_tools["plantillas"].setVisible(True)
        
    def create_project_header(self):
        """Crear header del proyecto"""
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {config.COLORS['color3']}, 
                    stop:0.5 {config.COLORS['color4']}, 
                    stop:1 {config.COLORS['color5']});
                border-bottom: 3px solid {config.COLORS['color5']};
                padding: 15px 20px;
            }}
        """)
        
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Información del proyecto
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        self.project_title = QLabel(self.project['nombre'])
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.project_title.setFont(title_font)
        self.project_title.setStyleSheet(f"color: {config.COLORS['dark']};")
        
        self.project_desc = QLabel(self.project['descripcion'] or "Sin descripción")
        self.project_desc.setStyleSheet("color: #555;")
        self.project_desc.setWordWrap(True)
        
        info_layout.addWidget(self.project_title)
        info_layout.addWidget(self.project_desc)
        
        # Estadísticas rápidas
        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.8);
                border-radius: 8px;
                padding: 10px;
                min-width: 200px;
            }}
        """)
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(5)
        
        self.stats_label = QLabel("Cargando estadísticas...")
        self.stats_label.setStyleSheet("color: #666; font-size: 11px;")
        
        stats_layout.addWidget(self.stats_label)
        stats_frame.setLayout(stats_layout)
        
        # Botones de acción
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(8)
        
        # Botón para cargar padrón (solo superadmin y analista)
        if self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
            self.load_padron_btn = QPushButton("📥 Cargar Padrón")
            self.load_padron_btn.setStyleSheet(styles.get_main_style())
            self.load_padron_btn.clicked.connect(self.load_padron)
            self.load_padron_btn.setFixedWidth(150)
            actions_layout.addWidget(self.load_padron_btn)
        
        # Botón para nueva plantilla (solo superadmin y analista)
        if self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
            self.new_template_btn = QPushButton("➕ Nueva Plantilla")
            self.new_template_btn.setStyleSheet(styles.get_main_style())
            self.new_template_btn.clicked.connect(self.new_template)
            self.new_template_btn.setFixedWidth(150)
            actions_layout.addWidget(self.new_template_btn)
        
        # Botón para generar PDFs
        self.generate_btn = QPushButton("🖨️ Generar PDFs")
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {config.COLORS['primary']};
                color: white;
                border: 2px solid {config.COLORS['primary']};
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
                min-width: 150px;
            }}
            
            QPushButton:hover {{
                background-color: #3a5a8c;
                border-color: #3a5a8c;
            }}
        """)
        self.generate_btn.clicked.connect(self.generate_pdfs)
        self.generate_btn.setFixedWidth(150)
        actions_layout.addWidget(self.generate_btn)
        
        header_layout.addLayout(info_layout)
        header_layout.addWidget(stats_frame)
        header_layout.addLayout(actions_layout)
        
        header_frame.setLayout(header_layout)
        return header_frame
        
    def create_tabs(self):
        """Crear pestañas según permisos"""
        # Pestaña de Resumen (siempre visible)
        self.overview_tab = self.create_overview_tab()
        self.tabs.addTab(self.overview_tab, "📋 Resumen")
        
        # Pestaña de Padrón (solo para superadmin y analista)
        if self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
            self.padron_tab = self.create_padron_tab()
            self.tabs.addTab(self.padron_tab, "📊 Padrón")
        
        # Pestaña de Plantillas (solo para superadmin y analista)
        if self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
            self.templates_tab = self.create_templates_tab()
            self.tabs.addTab(self.templates_tab, "📄 Plantillas")
        
        # Pestaña de Emisión (todos los roles)
        self.emission_tab = self.create_emission_tab()
        self.tabs.addTab(self.emission_tab, "🖨️ Emisión")
        
        # Pestaña de Estadísticas
        self.stats_tab = self.create_stats_tab()
        self.tabs.addTab(self.stats_tab, "📈 Estadísticas")
        
    def create_overview_tab(self):
        """Crear pestaña de resumen"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Estadísticas del proyecto
        stats_group = QGroupBox("📊 Estadísticas del Proyecto")
        stats_layout = QGridLayout()
        
        self.stats_widgets = {}
        stats_config = [
            ("Total registros", "padron_count", "0", "color4"),
            ("Plantillas activas", "templates_count", "0", "color3"),
            ("Emisiones realizadas", "emissions_count", "0", "color2"),
            ("PDFs generados", "pdfs_count", "0", "color1"),
            ("Última emisión", "last_emission", "Nunca", "color5"),
            ("Espacio utilizado", "space_used", "0 MB", "primary")
        ]
        
        for i, (label, key, default, color) in enumerate(stats_config):
            row = i // 3
            col = (i % 3) * 2
            
            # Label
            stat_label = QLabel(f"{label}:")
            stat_label.setStyleSheet("font-weight: bold;")
            
            # Valor
            value_frame = QFrame()
            value_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {config.COLORS[color]}40;
                    border: 2px solid {config.COLORS[color]};
                    border-radius: 6px;
                    padding: 8px;
                }}
            """)
            value_layout = QHBoxLayout()
            value_layout.setContentsMargins(5, 5, 5, 5)
            
            value_label = QLabel(default)
            value_label.setObjectName(key)
            value_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            
            value_layout.addWidget(value_label)
            value_layout.addStretch()
            value_frame.setLayout(value_layout)
            
            stats_layout.addWidget(stat_label, row, col)
            stats_layout.addWidget(value_frame, row, col + 1)
            
            self.stats_widgets[key] = value_label
        
        stats_group.setLayout(stats_layout)
        
        # Actividad reciente
        activity_group = QGroupBox("📅 Actividad Reciente")
        activity_layout = QVBoxLayout()
        
        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(5)
        self.activity_table.setHorizontalHeaderLabels(["Fecha", "Hora", "Usuario", "Acción", "Detalles"])
        
        header = self.activity_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.activity_table.setAlternatingRowColors(True)
        
        activity_layout.addWidget(self.activity_table)
        activity_group.setLayout(activity_layout)
        
        # Información del padrón
        padron_group = QGroupBox("🗃️ Información del Padrón")
        padron_layout = QVBoxLayout()
        
        self.padron_info_label = QLabel("Cargando información del padrón...")
        self.padron_info_label.setWordWrap(True)
        self.padron_info_label.setStyleSheet("padding: 10px; background-color: #f8f9fa; border-radius: 5px;")
        
        padron_btn_layout = QHBoxLayout()
        
        view_structure_btn = QPushButton("Ver estructura")
        view_structure_btn.setStyleSheet(styles.get_main_style())
        view_structure_btn.clicked.connect(self.show_padron_structure)
        
        view_sample_btn = QPushButton("Ver muestra de datos")
        view_sample_btn.setStyleSheet(styles.get_main_style())
        view_sample_btn.clicked.connect(self.show_padron_sample)
        
        padron_btn_layout.addWidget(view_structure_btn)
        padron_btn_layout.addWidget(view_sample_btn)
        padron_btn_layout.addStretch()
        
        padron_layout.addWidget(self.padron_info_label)
        padron_layout.addLayout(padron_btn_layout)
        padron_group.setLayout(padron_layout)
        
        # Agregar al layout
        layout.addWidget(stats_group)
        layout.addWidget(activity_group, 1)  # Stretch factor 1
        layout.addWidget(padron_group)
        
        tab.setLayout(layout)
        return tab
        
    def create_padron_tab(self):
        """Crear pestaña de padrón"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Barra de herramientas del padrón
        tools_frame = QFrame()
        tools_layout = QHBoxLayout()
        tools_layout.setContentsMargins(0, 0, 0, 0)
        
        # Botones de acción
        self.load_csv_btn = QPushButton("📥 Cargar CSV")
        self.load_csv_btn.setStyleSheet(styles.get_main_style())
        self.load_csv_btn.clicked.connect(self.load_padron)
        
        self.export_btn = QPushButton("📤 Exportar CSV")
        self.export_btn.setStyleSheet(styles.get_main_style())
        self.export_btn.clicked.connect(self.export_padron)
        
        self.refresh_btn = QPushButton("🔄 Refrescar")
        self.refresh_btn.setStyleSheet(styles.get_main_style())
        self.refresh_btn.clicked.connect(self.load_padron_data)
        
        # Controles de búsqueda/filtro
        search_frame = QFrame()
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar en padrón...")
        self.search_input.setFixedWidth(250)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Todos", "Activos", "Con datos"])
        
        search_layout.addWidget(QLabel("Filtrar:"))
        search_layout.addWidget(self.filter_combo)
        search_layout.addStretch()
        search_layout.addWidget(QLabel("Buscar:"))
        search_layout.addWidget(self.search_input)
        
        search_frame.setLayout(search_layout)
        
        tools_layout.addWidget(self.load_csv_btn)
        tools_layout.addWidget(self.export_btn)
        tools_layout.addWidget(self.refresh_btn)
        tools_layout.addStretch()
        tools_layout.addWidget(search_frame)
        
        tools_frame.setLayout(tools_layout)
        
        # Tabla de datos
        self.padron_table = QTableWidget()
        self.padron_table.setAlternatingRowColors(True)
        self.padron_table.verticalHeader().setVisible(False)
        self.padron_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.padron_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.padron_table.setSortingEnabled(True)
        
        # Información de la tabla
        self.table_info_label = QLabel("Cargando datos del padrón...")
        self.table_info_label.setStyleSheet("color: #666; font-style: italic;")
        
        # Agregar al layout
        layout.addWidget(tools_frame)
        layout.addWidget(self.table_info_label)
        layout.addWidget(self.padron_table, 1)  # Stretch factor 1
        
        tab.setLayout(layout)
        return tab
        
    def create_templates_tab(self):
        """Crear pestaña de plantillas"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Barra de herramientas
        tools_layout = QHBoxLayout()
        
        self.new_template_btn = QPushButton("➕ Nueva Plantilla")
        self.new_template_btn.setStyleSheet(styles.get_main_style())
        self.new_template_btn.clicked.connect(self.new_template)
        
        self.refresh_templates_btn = QPushButton("🔄 Refrescar")
        self.refresh_templates_btn.setStyleSheet(styles.get_main_style())
        self.refresh_templates_btn.clicked.connect(self.load_templates)
        
        tools_layout.addWidget(self.new_template_btn)
        tools_layout.addWidget(self.refresh_templates_btn)
        tools_layout.addStretch()
        
        # Tabla de plantillas
        self.templates_table = QTableWidget()
        self.templates_table.setColumnCount(6)
        self.templates_table.setHorizontalHeaderLabels(["ID", "Nombre", "Descripción", "Creada", "Estado", "Acciones"])
        
        header = self.templates_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        self.templates_table.verticalHeader().setVisible(False)
        self.templates_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.templates_table.setAlternatingRowColors(True)
        
        # Mensaje cuando no hay plantillas
        self.no_templates_label = QLabel("No hay plantillas configuradas para este proyecto.")
        self.no_templates_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_templates_label.setStyleSheet("color: #666; font-size: 14px; padding: 40px;")
        
        # Stack para alternar entre tabla y mensaje
        self.templates_stack = QWidget()
        stack_layout = QVBoxLayout()
        stack_layout.addWidget(self.templates_table)
        stack_layout.addWidget(self.no_templates_label)
        self.templates_stack.setLayout(stack_layout)
        
        # Inicialmente mostrar mensaje
        self.templates_table.hide()
        
        # Agregar al layout
        layout.addLayout(tools_layout)
        layout.addWidget(self.templates_stack, 1)
        
        tab.setLayout(layout)
        return tab
        
    def create_emission_tab(self):
        """Crear pestaña de emisión"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Título
        title_label = QLabel("🖨️ Emisión de Documentos")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {config.COLORS['primary']};")
        
        # Descripción
        desc_label = QLabel(
            "En esta sección podrás generar documentos PDF de manera masiva.\n"
            "Carga un archivo CSV con las cuentas a procesar, configura los parámetros de emisión y genera los PDFs."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; padding: 10px; background-color: #f8f9fa; border-radius: 5px;")
        
        # Panel de información
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {config.COLORS['color3']}40;
                border: 2px solid {config.COLORS['color3']};
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        info_layout = QVBoxLayout()
        
        info_title = QLabel("📋 Información importante:")
        info_title.setStyleSheet("font-weight: bold;")
        
        info_content = QLabel(
            "• El CSV debe contener las columnas 'cuenta' y 'orden_impresion'<br>"
            "• Se generará un PDF por cada cuenta válida encontrada en el padrón<br>"
            "• Los PDFs se guardarán en la carpeta de salida configurada<br>"
            "• El proceso puede tomar varios minutos para grandes volúmenes"
        )
        info_content.setWordWrap(True)
        
        info_layout.addWidget(info_title)
        info_layout.addWidget(info_content)
        info_frame.setLayout(info_layout)
        
        # Panel de estado
        status_frame = QFrame()
        status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {config.COLORS['color4']}40;
                border: 2px solid {config.COLORS['color4']};
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        status_layout = QVBoxLayout()
        
        status_title = QLabel("🚧 En desarrollo")
        status_title.setStyleSheet("font-weight: bold; color: #856404;")
        
        status_content = QLabel(
            "La funcionalidad completa de emisión de PDFs estará disponible en la <b>Parte 4</b> del desarrollo.<br><br>"
            "Características que se implementarán:<br>"
            "• Selección de plantillas y configuración de parámetros<br>"
            "• Carga y validación de CSVs de emisión<br>"
            "• Cálculo automático de PMO y visitas<br>"
            "• Generación de códigos de barras<br>"
            "• Vista previa de documentos<br>"
            "• Proceso masivo optimizado"
        )
        status_content.setWordWrap(True)
        
        status_layout.addWidget(status_title)
        status_layout.addWidget(status_content)
        status_frame.setLayout(status_layout)
        
        # Botón de prueba (placeholder)
        test_btn = QPushButton("Probar emisión (demo)")
        test_btn.setStyleSheet(styles.get_main_style())
        test_btn.clicked.connect(self.test_emission)
        test_btn.setEnabled(False)  # Deshabilitado hasta la parte 4
        
        # Agregar al layout
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addWidget(info_frame)
        layout.addWidget(status_frame, 1)  # Stretch factor 1
        layout.addWidget(test_btn)
        
        tab.setLayout(layout)
        return tab
        
    def create_stats_tab(self):
        """Crear pestaña de estadísticas"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Título según rol
        if self.user_info['rol'] == 'SUPERADMIN':
            title_text = "📊 Estadísticas Completas del Proyecto"
        elif self.user_info['rol'] == 'ANALISTA':
            title_text = "📊 Estadísticas del Proyecto"
        else:  # AUXILIAR
            title_text = "📊 Mis Estadísticas de Emisión"
        
        title_label = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {config.COLORS['primary']};")
        
        # Panel de estadísticas
        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {config.COLORS['color2']}20;
                border: 2px solid {config.COLORS['color2']};
                border-radius: 10px;
                padding: 20px;
            }}
        """)
        stats_layout = QVBoxLayout()
        
        stats_content = QLabel(
            "Las estadísticas detalladas estarán disponibles en la <b>Parte 5</b> del desarrollo.<br><br>"
            "Se incluirán:<br>"
            "• Gráficos de emisiones por fecha y tipo de documento<br>"
            "• Métricas de rendimiento y uso del sistema<br>"
            "• Reportes exportables en diferentes formatos<br>"
            "• Filtros por rangos de fecha y usuarios<br>"
            "• Comparativas entre períodos"
        )
        stats_content.setWordWrap(True)
        
        stats_layout.addWidget(stats_content)
        stats_frame.setLayout(stats_layout)
        
        # Placeholder para gráficos
        charts_frame = QFrame()
        charts_frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 2px solid {config.COLORS['color3']};
                border-radius: 10px;
                padding: 20px;
            }}
        """)
        charts_layout = QVBoxLayout()
        
        charts_label = QLabel("📈 Gráficos y visualizaciones")
        charts_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        charts_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #666;")
        
        charts_content = QLabel(
            "Área reservada para gráficos interactivos de estadísticas."
        )
        charts_content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        charts_layout.addWidget(charts_label)
        charts_layout.addWidget(charts_content)
        charts_frame.setLayout(charts_layout)
        
        # Agregar al layout
        layout.addWidget(title_label)
        layout.addWidget(stats_frame)
        layout.addWidget(charts_frame, 1)  # Stretch factor 1
        
        tab.setLayout(layout)
        return tab
        
    def load_project_details(self):
        """Cargar detalles del proyecto"""
        try:
            # Obtener proyecto actualizado
            response = api_client.obtener_proyecto(self.project["id"])
            self.project = response
            
            # Actualizar UI
            self.project_title.setText(self.project['nombre'])
            self.project_desc.setText(self.project['descripcion'] or "Sin descripción")
            
            # Cargar estadísticas
            self.load_project_stats()
            
            # Cargar actividad reciente
            self.load_recent_activity()
            
            # Cargar información del padrón
            self.load_padron_info()
            
            # Si estamos en la pestaña de padrón, cargar datos
            if self.tabs.currentIndex() == 1 and self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
                self.load_padron_data()
            
            # Si estamos en la pestaña de plantillas, cargar plantillas
            if self.tabs.currentIndex() == 2 and self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
                self.load_templates()
            
            self.update_status_bar()
            
        except APIError as e:
            QMessageBox.critical(self, "Error", f"No se pudieron cargar los detalles: {str(e)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error inesperado: {str(e)}")
            
    def load_project_stats(self):
        """Cargar estadísticas del proyecto"""
        # Por ahora, valores simulados
        # En la parte 5 implementaremos estadísticas reales
        
        stats = {
            "padron_count": "1,245",
            "templates_count": "3",
            "emissions_count": "45",
            "last_emission": "2024-01-15",
            "pdfs_count": "12,450",
            "space_used": "245 MB"
        }
        
        for key, value in stats.items():
            if key in self.stats_widgets:
                self.stats_widgets[key].setText(value)
        
        # Actualizar header
        self.stats_label.setText(f"📊 {stats['padron_count']} registros | 📄 {stats['templates_count']} plantillas | 🖨️ {stats['emissions_count']} emisiones")
        
    def load_recent_activity(self):
        """Cargar actividad reciente"""
        # Por ahora, datos simulados
        # En la parte 5 implementaremos la bitácora real
        
        activities = [
            ("2024-01-15", "10:30", "admin", "Generación PDF", "1,000 documentos generados"),
            ("2024-01-14", "15:20", "analista1", "Carga de padrón", "500 registros actualizados"),
            ("2024-01-14", "09:15", "auxiliar1", "Generación PDF", "250 documentos generados"),
            ("2024-01-13", "16:45", "admin", "Creación plantilla", "Plantilla 'Notificación' creada"),
            ("2024-01-12", "11:10", "analista2", "Actualización padrón", "Merge de datos CSV")
        ]
        
        self.activity_table.setRowCount(len(activities))
        
        for row, (fecha, hora, usuario, accion, detalles) in enumerate(activities):
            self.activity_table.setItem(row, 0, QTableWidgetItem(fecha))
            self.activity_table.setItem(row, 1, QTableWidgetItem(hora))
            self.activity_table.setItem(row, 2, QTableWidgetItem(usuario))
            self.activity_table.setItem(row, 3, QTableWidgetItem(accion))
            self.activity_table.setItem(row, 4, QTableWidgetItem(detalles))
            
    def load_padron_info(self):
        """Cargar información del padrón"""
        try:
            response = api_client.obtener_estructura_padron(self.project["id"])
            
            estructura = response.get("estructura", [])
            muestra = response.get("muestra", [])
            
            self.padron_structure = estructura
            self.padron_sample = muestra
            
            info_text = f"""
            <b>Tabla de padrón:</b> {response.get('nombre_tabla', 'N/A')}<br>
            <b>Total de columnas:</b> {len(estructura)}<br>
            <b>Muestra de datos:</b> {len(muestra)} registros disponibles<br>
            <b>Estructura:</b> {', '.join([col['nombre'] for col in estructura[:5]])}{'...' if len(estructura) > 5 else ''}
            """
            
            self.padron_info_label.setText(info_text)
            
        except APIError as e:
            self.padron_info_label.setText(f"❌ Error cargando información del padrón: {str(e)}")
            
        except Exception as e:
            self.padron_info_label.setText(f"❌ Error inesperado: {str(e)}")
            
    def load_padron_data(self):
        """Cargar datos del padrón en la tabla"""
        try:
            response = api_client.obtener_muestra_padron(self.project["id"], limit=100)
            datos = response.get("muestra", [])
            
            if not datos:
                self.table_info_label.setText("El padrón no contiene datos.")
                self.padron_table.setRowCount(0)
                self.padron_table.setColumnCount(0)
                return
            
            # Configurar tabla
            if datos:
                columns = list(datos[0].keys())
                self.padron_table.setColumnCount(len(columns))
                self.padron_table.setHorizontalHeaderLabels(columns)
                
                self.padron_table.setRowCount(len(datos))
                
                for row, registro in enumerate(datos):
                    for col, key in enumerate(columns):
                        value = registro.get(key, "")
                        item = QTableWidgetItem(str(value))
                        
                        # Formatear según tipo de dato
                        if isinstance(value, (int, float)):
                            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        
                        self.padron_table.setItem(row, col, item)
                
                # Ajustar columnas
                self.padron_table.resizeColumnsToContents()
                
                self.table_info_label.setText(f"Mostrando {len(datos)} registros de muestra. Total en padrón: {response.get('total_registros', 'N/A')}")
                
        except APIError as e:
            self.table_info_label.setText(f"❌ Error cargando datos: {str(e)}")
            QMessageBox.critical(self, "Error", f"No se pudieron cargar los datos del padrón: {str(e)}")
            
        except Exception as e:
            self.table_info_label.setText(f"❌ Error inesperado: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error inesperado: {str(e)}")
            
    def load_templates(self):
        """Cargar plantillas del proyecto"""
        # Por ahora, datos simulados
        # En la parte 3 implementaremos plantillas reales
        
        templates = [
            {
                "id": 1,
                "nombre": "Notificación",
                "descripcion": "Plantilla para notificaciones estándar",
                "created_at": "2024-01-10",
                "estado": "Activa"
            },
            {
                "id": 2,
                "nombre": "Apercibimiento",
                "descripcion": "Plantilla para apercibimientos",
                "created_at": "2024-01-11",
                "estado": "Activa"
            },
            {
                "id": 3,
                "nombre": "Embargo",
                "descripcion": "Plantilla para embargos",
                "created_at": "2024-01-12",
                "estado": "Inactiva"
            }
        ]
        
        if not templates:
            self.templates_table.hide()
            self.no_templates_label.show()
            return
        
        self.templates_table.show()
        self.no_templates_label.hide()
        
        self.templates_table.setRowCount(len(templates))
        
        for row, template in enumerate(templates):
            # ID
            id_item = QTableWidgetItem(str(template["id"]))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.templates_table.setItem(row, 0, id_item)
            
            # Nombre
            self.templates_table.setItem(row, 1, QTableWidgetItem(template["nombre"]))
            
            # Descripción
            self.templates_table.setItem(row, 2, QTableWidgetItem(template["descripcion"]))
            
            # Fecha creación
            self.templates_table.setItem(row, 3, QTableWidgetItem(template["created_at"]))
            
            # Estado
            estado_item = QTableWidgetItem(template["estado"])
            if template["estado"] == "Activa":
                estado_item.setForeground(QColor("#28a745"))
            else:
                estado_item.setForeground(QColor("#dc3545"))
            estado_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.templates_table.setItem(row, 4, estado_item)
            
            # Acciones
            actions_widget = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(5, 5, 5, 5)
            actions_layout.setSpacing(5)
            
            edit_btn = QPushButton("✏️")
            edit_btn.setStyleSheet("padding: 2px 6px;")
            edit_btn.setToolTip("Editar plantilla")
            edit_btn.clicked.connect(lambda checked, t=template: self.edit_template(t))
            
            delete_btn = QPushButton("🗑️")
            delete_btn.setStyleSheet("padding: 2px 6px;")
            delete_btn.setToolTip("Eliminar plantilla")
            delete_btn.clicked.connect(lambda checked, t=template: self.delete_template(t))
            
            duplicate_btn = QPushButton("📋")
            duplicate_btn.setStyleSheet("padding: 2px 6px;")
            duplicate_btn.setToolTip("Duplicar plantilla")
            duplicate_btn.clicked.connect(lambda checked, t=template: self.duplicate_template(t))
            
            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            actions_layout.addWidget(duplicate_btn)
            actions_layout.addStretch()
            
            actions_widget.setLayout(actions_layout)
            self.templates_table.setCellWidget(row, 5, actions_widget)
        
        self.templates_table.resizeColumnsToContents()
        
    def load_padron(self):
        """Cargar padrón desde CSV"""
        try:
            file_path = FileDialog.open_csv_file(self)
            if not file_path:
                return
            
            # Diálogo de opciones de carga
            dialog = QDialog(self)
            dialog.setWindowTitle("Opciones de carga")
            dialog.setFixedSize(400, 250)
            
            layout = QVBoxLayout()
            
            # Opciones
            options_group = QGroupBox("Opciones de carga")
            options_layout = QVBoxLayout()
            
            merge_radio = QRadioButton("Fusionar con datos existentes")
            merge_radio.setChecked(True)
            merge_radio.setToolTip("Actualiza registros existentes y añade nuevos")
            
            replace_radio = QRadioButton("Reemplazar todos los datos")
            replace_radio.setToolTip("Elimina todos los datos existentes y carga nuevos")
            
            options_layout.addWidget(merge_radio)
            options_layout.addWidget(replace_radio)
            options_group.setLayout(options_layout)
            
            # Validación
            validation_check = QCheckBox("Validar estructura antes de cargar")
            validation_check.setChecked(True)
            validation_check.setToolTip("Verifica que el CSV coincida con la estructura del padrón")
            
            # Botones
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            
            layout.addWidget(options_group)
            layout.addWidget(validation_check)
            layout.addWidget(button_box)
            
            dialog.setLayout(layout)
            
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            
            # Mostrar progreso
            progress = QProgressDialog("Cargando padrón...", "Cancelar", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setValue(10)
            QApplication.processEvents()
            
            # Cargar a través de API
            merge = merge_radio.isChecked()
            response = api_client.cargar_padron(
                self.project["id"], 
                file_path, 
                merge=merge
            )
            
            progress.setValue(100)
            progress.close()
            
            QMessageBox.information(
                self,
                "Éxito",
                f"Padrón cargado exitosamente.\n\n"
                f"Registros procesados: {response.get('registros_procesados', 0)}\n"
                f"Modo: {'Fusión' if merge else 'Reemplazo'}"
            )
            
            # Refrescar datos
            self.load_padron_data()
            self.load_padron_info()
            
        except APIError as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el padrón: {str(e)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error inesperado: {str(e)}")
            
    def export_padron(self):
        """Exportar padrón a CSV"""
        try:
            # Obtener muestra más grande para exportación
            response = api_client.obtener_muestra_padron(self.project["id"], limit=1000)
            datos = response.get("muestra", [])
            
            if not datos:
                QMessageBox.warning(self, "Sin datos", "El padrón no contiene datos para exportar.")
                return
            
            # Seleccionar ubicación para guardar
            file_path = FileDialog.save_csv_file(
                self,
                default_name=f"padron_{self.project['nombre']}_{datetime.now().strftime('%Y%m%d')}.csv"
            )
            
            if not file_path:
                return
            
            # Convertir a DataFrame y guardar
            df = pd.DataFrame(datos)
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            
            QMessageBox.information(
                self,
                "Exportación exitosa",
                f"Padrón exportado exitosamente.\n\n"
                f"Archivo: {Path(file_path).name}\n"
                f"Registros: {len(datos)}\n"
                f"Ubicación: {file_path}"
            )
            
        except APIError as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar el padrón: {str(e)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error exportando: {str(e)}")
            
    def show_padron_structure(self):
        """Mostrar estructura del padrón"""
        try:
            if not self.padron_structure:
                response = api_client.obtener_estructura_padron(self.project["id"])
                self.padron_structure = response.get("estructura", [])
            
            # Crear diálogo para mostrar estructura
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Estructura del padrón - {self.project['nombre']}")
            dialog.setFixedSize(600, 400)
            
            layout = QVBoxLayout()
            
            # Tabla de estructura
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Columna", "Tipo", "Nulo", "Default"])
            table.setRowCount(len(self.padron_structure))
            
            for row, col in enumerate(self.padron_structure):
                table.setItem(row, 0, QTableWidgetItem(col['nombre']))
                table.setItem(row, 1, QTableWidgetItem(col['tipo']))
                table.setItem(row, 2, QTableWidgetItem("Sí" if col.get('nulo') else "No"))
                table.setItem(row, 3, QTableWidgetItem(str(col.get('default', ''))))
            
            table.resizeColumnsToContents()
            
            # Información
            info_label = QLabel(f"Total de columnas: {len(self.padron_structure)}")
            
            # Botones
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            button_box.rejected.connect(dialog.reject)
            
            layout.addWidget(table)
            layout.addWidget(info_label)
            layout.addWidget(button_box)
            
            dialog.setLayout(layout)
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo mostrar la estructura: {str(e)}")
            
    def show_padron_sample(self):
        """Mostrar muestra de datos del padrón"""
        try:
            if not self.padron_sample:
                response = api_client.obtener_muestra_padron(self.project["id"], limit=20)
                self.padron_sample = response.get("muestra", [])
            
            if not self.padron_sample:
                QMessageBox.information(self, "Sin datos", "El padrón no contiene datos.")
                return
            
            # Crear diálogo
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Muestra de datos - {self.project['nombre']}")
            dialog.setFixedSize(800, 500)
            
            layout = QVBoxLayout()
            
            # Tabla de datos
            table = QTableWidget()
            if self.padron_sample:
                columns = list(self.padron_sample[0].keys())
                table.setColumnCount(len(columns))
                table.setHorizontalHeaderLabels(columns)
                table.setRowCount(len(self.padron_sample))
                
                for row, registro in enumerate(self.padron_sample):
                    for col, key in enumerate(columns):
                        value = registro.get(key, "")
                        table.setItem(row, col, QTableWidgetItem(str(value)))
                
                table.resizeColumnsToContents()
            
            # Información
            info_label = QLabel(f"Mostrando {len(self.padron_sample)} registros de muestra")
            
            # Botones
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            button_box.rejected.connect(dialog.reject)
            
            layout.addWidget(table)
            layout.addWidget(info_label)
            layout.addWidget(button_box)
            
            dialog.setLayout(layout)
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo mostrar la muestra: {str(e)}")
            
    def new_template(self):
        """Crear nueva plantilla"""
        QMessageBox.information(
            self,
            "Próximamente",
            "El editor de plantillas estará disponible en la <b>Parte 3</b> del desarrollo.\n\n"
            "Características incluirán:\n"
            "• Carga de documentos DOCX base\n"
            "• Mapeo visual de placeholders\n"
            "• Validación de tamaño de página\n"
            "• Vista previa con datos reales\n"
            "• Configuración de formatos y estilos"
        )
        
    def edit_template(self, template):
        """Editar plantilla existente"""
        QMessageBox.information(
            self,
            "Próximamente",
            f"Editar plantilla '{template['nombre']}' estará disponible en la <b>Parte 3</b>."
        )
        
    def delete_template(self, template):
        """Eliminar plantilla"""
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Estás seguro de eliminar la plantilla '{template['nombre']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                self,
                "Próximamente",
                "La eliminación de plantillas estará disponible en la <b>Parte 3</b>."
            )
            
    def duplicate_template(self, template):
        """Duplicar plantilla"""
        QMessageBox.information(
            self,
            "Próximamente",
            f"Duplicar plantilla '{template['nombre']}' estará disponible en la <b>Parte 3</b>."
        )
        
    def generate_pdfs(self):
        """Generar PDFs"""
        QMessageBox.information(
            self,
            "Próximamente",
            "La generación de PDFs estará disponible en la <b>Parte 4</b> del desarrollo.\n\n"
            "Se implementará:\n"
            "• Motor completo de generación de PDFs\n"
            "• Integración con códigos de barras\n"
            "• Cálculo automático de PMO y visitas\n"
            "• Procesamiento masivo optimizado\n"
            "• Validación de resultados"
        )
        
    def test_emission(self):
        """Probar emisión (demo)"""
        QMessageBox.information(
            self,
            "Demo de emisión",
            "Esta funcionalidad estará disponible en la Parte 4."
        )
        
    def edit_project(self):
        """Editar proyecto"""
        QMessageBox.information(
            self,
            "Próximamente",
            "La edición de proyectos estará disponible en futuras versiones."
        )
        
    def delete_project(self):
        """Eliminar proyecto"""
        # Reutilizar lógica del dashboard
        from ..widgets.dashboard_window import DashboardWindow
        DashboardWindow.delete_project(self, self.project)
        
    def refresh_project_data(self):
        """Refrescar datos del proyecto"""
        self.load_project_details()
        
    def update_status_bar(self, message: str = ""):
        """Actualizar barra de estado"""
        if not message:
            message = (
                f"Proyecto: {self.project['nombre']} | "
                f"Usuario: {self.user_info['nombre_completo']} | "
                f"Rol: {self.user_info['rol']}"
            )
        
        self.status_bar.showMessage(message)
        
    def closeEvent(self, event):
        """Manejar cierre de ventana"""
        self.refresh_timer.stop()
        event.accept()