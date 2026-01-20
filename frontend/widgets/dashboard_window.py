"""
Ventana principal de dashboard
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QDateEdit, QLineEdit, QProgressBar,
    QGroupBox, QGridLayout, QStackedWidget, QSplitter,
    QMessageBox, QFileDialog, QApplication, QMenu, QToolBar,
    QStatusBar, QToolButton, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QDate, QSize
from PyQt6.QtGui import QAction, QFont, QIcon, QColor, QPixmap
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib
matplotlib.use('Qt5Agg')
import numpy as np
from datetime import datetime, timedelta
import json
import csv
from io import StringIO
import logging

from ..config import config
from ..styles import styles
from ..utils.api_client import api_client, APIError
from .kpi_card import KPICard
from .charts import LineChartWidget, PieChartWidget, BarChartWidget

logger = logging.getLogger(__name__)


class DashboardWindow(QMainWindow):
    """Ventana principal del dashboard"""
    
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info
        self.proyectos = []
        self.current_proyecto_id = None
        self.current_filters = {
            "date_filter": "30d",
            "start_date": None,
            "end_date": None
        }
        
        self.init_ui()
        self.load_proyectos()
        self.refresh_dashboard()
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        self.setWindowTitle(f"Dashboard - {config.APP_NAME}")
        self.setGeometry(100, 100, 1400, 900)
        
        # Crear widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Barra de herramientas
        self.create_toolbar()
        
        # Controles de filtro
        filter_frame = self.create_filter_controls()
        main_layout.addWidget(filter_frame)
        
        # Dashboard principal
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(styles.get_main_style())
        
        # Pestañas
        self.dashboard_tab = self.create_dashboard_tab()
        self.stats_tab = self.create_stats_tab()
        self.bitacora_tab = self.create_bitacora_tab()
        
        self.tab_widget.addTab(self.dashboard_tab, "📊 Dashboard")
        self.tab_widget.addTab(self.stats_tab, "📈 Estadísticas")
        
        # Solo superadmin ve la bitácora completa
        if self.user_info['rol'] == "SUPERADMIN":
            self.tab_widget.addTab(self.bitacora_tab, "📋 Bitácora")
        
        main_layout.addWidget(self.tab_widget, 1)
        
        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Listo")
        self.status_bar.addWidget(self.status_label, 1)
        
        # Timer para actualización automática
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_dashboard)
        self.refresh_timer.start(300000)  # 5 minutos
        
        # Aplicar estilo
        self.setStyleSheet(styles.get_main_style())
        
    def create_toolbar(self):
        """Crear barra de herramientas"""
        toolbar = QToolBar("Dashboard")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Acciones
        refresh_action = QAction("🔄 Refrescar", self)
        refresh_action.triggered.connect(self.refresh_dashboard)
        refresh_action.setShortcut("F5")
        toolbar.addAction(refresh_action)
        
        toolbar.addSeparator()
        
        export_action = QAction("📤 Exportar", self)
        export_action.triggered.connect(self.export_dashboard)
        toolbar.addAction(export_action)
        
        # Menú de exportación
        export_menu = QMenu(self)
        export_pdf_action = QAction("Exportar a PDF", self)
        export_pdf_action.triggered.connect(lambda: self.export_report("pdf"))
        export_menu.addAction(export_pdf_action)
        
        export_excel_action = QAction("Exportar a Excel", self)
        export_excel_action.triggered.connect(lambda: self.export_report("excel"))
        export_menu.addAction(export_excel_action)
        
        export_action.setMenu(export_menu)
        
        toolbar.addSeparator()
        
        # Botón de ayuda
        help_action = QAction("❓ Ayuda", self)
        help_action.triggered.connect(self.show_help)
        toolbar.addAction(help_action)
        
    def create_filter_controls(self):
        """Crear controles de filtro"""
        filter_frame = QFrame()
        filter_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(10, 5, 10, 5)
        
        # Selector de proyecto
        proyecto_label = QLabel("Proyecto:")
        self.proyecto_combo = QComboBox()
        self.proyecto_combo.addItem("Todos los proyectos", None)
        self.proyecto_combo.currentIndexChanged.connect(self.on_proyecto_changed)
        
        # Selector de período
        periodo_label = QLabel("Período:")
        self.periodo_combo = QComboBox()
        self.periodo_combo.addItems(["Hoy", "Últimos 7 días", "Últimos 30 días", "Personalizado"])
        self.periodo_combo.currentIndexChanged.connect(self.on_periodo_changed)
        
        # Fechas personalizadas
        self.date_start = QDateEdit()
        self.date_start.setDate(QDate.currentDate().addDays(-30))
        self.date_start.setCalendarPopup(True)
        self.date_start.dateChanged.connect(self.on_date_changed)
        
        self.date_end = QDateEdit()
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setCalendarPopup(True)
        self.date_end.dateChanged.connect(self.on_date_changed)
        
        self.date_label = QLabel("a")
        self.date_start.hide()
        self.date_label.hide()
        self.date_end.hide()
        
        # Botón de aplicar filtros
        apply_btn = QPushButton("Aplicar filtros")
        apply_btn.setStyleSheet(styles.get_main_style())
        apply_btn.clicked.connect(self.apply_filters)
        
        # Agregar al layout
        filter_layout.addWidget(proyecto_label)
        filter_layout.addWidget(self.proyecto_combo, 1)
        filter_layout.addWidget(periodo_label)
        filter_layout.addWidget(self.periodo_combo)
        filter_layout.addWidget(self.date_start)
        filter_layout.addWidget(self.date_label)
        filter_layout.addWidget(self.date_end)
        filter_layout.addStretch()
        filter_layout.addWidget(apply_btn)
        
        return filter_frame
        
    def create_dashboard_tab(self):
        """Crear pestaña de dashboard principal"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # Sección de KPIs
        kpi_frame = QFrame()
        kpi_layout = QGridLayout(kpi_frame)
        kpi_layout.setSpacing(10)
        
        self.kpi_cards = {}
        
        # Crear cards de KPI
        kpis = [
            ("total_pdfs", "Total PDFs", "📄", "#abe4ff"),
            ("pdfs_mes_actual", "PDFs mes actual", "📅", "#ddffab"),
            ("eficiencia", "Eficiencia", "⚡", "#ffdaab"),
            ("usuarios_activos", "Usuarios activos", "👥", "#d9abff"),
            ("proyectos_activos", "Proyectos activos", "🏢", "#ffabab"),
            ("tendencia", "Tendencia", "📈", "#abe4ff")
        ]
        
        for i, (key, title, icon, color) in enumerate(kpis):
            card = KPICard(title, icon, color)
            self.kpi_cards[key] = card
            kpi_layout.addWidget(card, i // 3, i % 3)
        
        layout.addWidget(kpi_frame)
        
        # Gráficas
        charts_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Gráfica de líneas (emisiones en el tiempo)
        self.line_chart = LineChartWidget("Emisiones en el tiempo")
        charts_splitter.addWidget(self.line_chart)
        
        # Gráfica de pastel (distribución por documento)
        self.pie_chart = PieChartWidget("Distribución por documento")
        charts_splitter.addWidget(self.pie_chart)
        
        # Gráfica de barras (solo para superadmin)
        if self.user_info['rol'] == "SUPERADMIN":
            self.bar_chart = BarChartWidget("Productividad por usuario")
            charts_splitter.addWidget(self.bar_chart)
        
        charts_splitter.setSizes([400, 400, 400])
        layout.addWidget(charts_splitter, 1)
        
        return tab
        
    def create_stats_tab(self):
        """Crear pestaña de estadísticas detalladas"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Controles de agrupación
        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame)
        
        agrupar_label = QLabel("Agrupar por:")
        self.agrupar_combo = QComboBox()
        self.agrupar_combo.addItems([
            "Día", "Semana", "Mes", "Documento", "Usuario"
        ])
        self.agrupar_combo.currentIndexChanged.connect(self.load_detailed_stats)
        
        export_stats_btn = QPushButton("Exportar estadísticas")
        export_stats_btn.setStyleSheet(styles.get_main_style())
        export_stats_btn.clicked.connect(self.export_stats)
        
        controls_layout.addWidget(agrupar_label)
        controls_layout.addWidget(self.agrupar_combo, 1)
        controls_layout.addStretch()
        controls_layout.addWidget(export_stats_btn)
        
        layout.addWidget(controls_frame)
        
        # Tabla de estadísticas
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(5)
        self.stats_table.setHorizontalHeaderLabels([
            "Grupo", "Total", "Tamaño total", "Tamaño promedio", "%"
        ])
        
        header = self.stats_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setSortingEnabled(True)
        
        layout.addWidget(self.stats_table, 1)
        
        return tab
        
    def create_bitacora_tab(self):
        """Crear pestaña de bitácora"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Controles de búsqueda
        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar en bitácora...")
        self.search_input.textChanged.connect(self.on_bitacora_search)
        
        usuario_label = QLabel("Usuario:")
        self.usuario_combo = QComboBox()
        self.usuario_combo.addItem("Todos", None)
        
        accion_label = QLabel("Acción:")
        self.accion_combo = QComboBox()
        self.accion_combo.addItem("Todas", None)
        
        refresh_bitacora_btn = QPushButton("🔄")
        refresh_bitacora_btn.clicked.connect(self.load_bitacora)
        
        export_bitacora_btn = QPushButton("📤 Exportar")
        export_bitacora_btn.setStyleSheet(styles.get_main_style())
        export_bitacora_btn.clicked.connect(self.export_bitacora)
        
        search_layout.addWidget(QLabel("Buscar:"))
        search_layout.addWidget(self.search_input, 2)
        search_layout.addWidget(usuario_label)
        search_layout.addWidget(self.usuario_combo, 1)
        search_layout.addWidget(accion_label)
        search_layout.addWidget(self.accion_combo, 1)
        search_layout.addWidget(refresh_bitacora_btn)
        search_layout.addWidget(export_bitacora_btn)
        
        layout.addWidget(search_frame)
        
        # Tabla de bitácora
        self.bitacora_table = QTableWidget()
        self.bitacora_table.setColumnCount(7)
        self.bitacora_table.setHorizontalHeaderLabels([
            "Fecha", "Usuario", "Acción", "Entidad", "ID", "Detalles", "IP"
        ])
        
        header = self.bitacora_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        
        self.bitacora_table.setAlternatingRowColors(True)
        self.bitacora_table.setSortingEnabled(True)
        self.bitacora_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.bitacora_table, 1)
        
        # Paginación
        pagination_frame = QFrame()
        pagination_layout = QHBoxLayout(pagination_frame)
        
        self.page_label = QLabel("Página 1 de 1")
        self.prev_page_btn = QPushButton("◀ Anterior")
        self.prev_page_btn.clicked.connect(self.prev_bitacora_page)
        self.prev_page_btn.setEnabled(False)
        
        self.next_page_btn = QPushButton("Siguiente ▶")
        self.next_page_btn.clicked.connect(self.next_bitacora_page)
        self.next_page_btn.setEnabled(False)
        
        page_size_label = QLabel("Registros por página:")
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["10", "25", "50", "100"])
        self.page_size_combo.currentIndexChanged.connect(self.load_bitacora)
        
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.prev_page_btn)
        pagination_layout.addWidget(self.next_page_btn)
        pagination_layout.addStretch()
        pagination_layout.addWidget(page_size_label)
        pagination_layout.addWidget(self.page_size_combo)
        
        layout.addWidget(pagination_frame)
        
        # Variables de paginación
        self.current_bitacora_page = 1
        self.bitacora_total_pages = 1
        self.bitacora_page_size = 25
        
        return tab
        
    def load_proyectos(self):
        """Cargar lista de proyectos"""
        try:
            response = api_client.listar_proyectos()
            self.proyectos = response.get('items', [])
            
            self.proyecto_combo.clear()
            self.proyecto_combo.addItem("Todos los proyectos", None)
            
            for proyecto in self.proyectos:
                self.proyecto_combo.addItem(proyecto['nombre'], proyecto['id'])
                
        except APIError as e:
            QMessageBox.warning(self, "Error", f"No se pudieron cargar los proyectos: {str(e)}")
            
    def on_proyecto_changed(self, index):
        """Manejar cambio de proyecto seleccionado"""
        self.current_proyecto_id = self.proyecto_combo.itemData(index)
        
    def on_periodo_changed(self, index):
        """Manejar cambio de período"""
        periods = ["today", "7d", "30d", "custom"]
        self.current_filters["date_filter"] = periods[index]
        
        # Mostrar/ocultar controles de fecha personalizada
        show_custom = (index == 3)
        self.date_start.setVisible(show_custom)
        self.date_label.setVisible(show_custom)
        self.date_end.setVisible(show_custom)
        
    def on_date_changed(self):
        """Manejar cambio de fechas personalizadas"""
        self.current_filters["start_date"] = self.date_start.date().toPyDate()
        self.current_filters["end_date"] = self.date_end.date().toPyDate()
        
    def apply_filters(self):
        """Aplicar filtros y refrescar dashboard"""
        self.refresh_dashboard()
        
    def refresh_dashboard(self):
        """Refrescar todo el dashboard"""
        self.status_label.setText("Actualizando dashboard...")
        QApplication.processEvents()
        
        try:
            # Cargar KPIs
            self.load_kpis()
            
            # Cargar gráficas
            self.load_charts()
            
            # Cargar estadísticas detalladas si estamos en esa pestaña
            if self.tab_widget.currentIndex() == 1:
                self.load_detailed_stats()
                
            # Cargar bitácora si estamos en esa pestaña
            elif self.tab_widget.currentIndex() == 2 and self.user_info['rol'] == "SUPERADMIN":
                self.load_bitacora()
                
            self.status_label.setText(f"Dashboard actualizado - {datetime.now().strftime('%H:%M:%S')}")
            
        except APIError as e:
            self.status_label.setText(f"Error: {str(e)}")
            QMessageBox.warning(self, "Error", f"No se pudo actualizar el dashboard: {str(e)}")
            
    def load_kpis(self):
        """Cargar KPIs desde la API"""
        try:
            params = {
                "proyecto_id": self.current_proyecto_id,
                "date_filter": self.current_filters["date_filter"]
            }
            
            if self.current_filters["date_filter"] == "custom":
                if self.current_filters["start_date"] and self.current_filters["end_date"]:
                    params["start_date"] = self.current_filters["start_date"]
                    params["end_date"] = self.current_filters["end_date"]
            
            response = api_client._request("GET", "/api/v1/stats/dashboard/kpis", params=params)
            
            # Actualizar cards de KPI
            for key, card in self.kpi_cards.items():
                value = response.get(key, 0)
                
                if key == "total_pdfs":
                    card.set_value(f"{value:,}")
                elif key == "eficiencia":
                    card.set_value(f"{value:.2f} PDFs/h")
                elif key == "tendencia":
                    card.set_value(f"{value:+.1f}%")
                    # Color según tendencia
                    if value > 0:
                        card.set_value_color("#28a745")
                    elif value < 0:
                        card.set_value_color("#dc3545")
                    else:
                        card.set_value_color("#6c757d")
                else:
                    card.set_value(str(value))
                    
        except Exception as e:
            logger.error(f"Error cargando KPIs: {str(e)}")
            
    def load_charts(self):
        """Cargar datos para gráficas"""
        try:
            # Datos para gráfica de líneas
            params = {
                "proyecto_id": self.current_proyecto_id,
                "date_filter": self.current_filters["date_filter"],
                "agrupacion": "day"
            }
            
            if self.current_filters["date_filter"] == "custom":
                if self.current_filters["start_date"] and self.current_filters["end_date"]:
                    params["start_date"] = self.current_filters["start_date"]
                    params["end_date"] = self.current_filters["end_date"]
            
            line_data = api_client._request(
                "GET", 
                "/api/v1/stats/dashboard/emisiones-tiempo", 
                params=params
            )
            
            if line_data:
                self.line_chart.update_data(line_data)
            
            # Datos para gráfica de pastel
            pie_data = api_client._request(
                "GET", 
                "/api/v1/stats/dashboard/distribucion-documentos", 
                params=params
            )
            
            if pie_data:
                self.pie_chart.update_data(pie_data)
            
            # Datos para gráfica de barras (solo superadmin)
            if self.user_info['rol'] == "SUPERADMIN":
                bar_data = api_client._request(
                    "GET", 
                    "/api/v1/stats/dashboard/productividad-usuarios", 
                    params=params
                )
                
                if bar_data:
                    self.bar_chart.update_data(bar_data)
                    
        except Exception as e:
            logger.error(f"Error cargando gráficas: {str(e)}")
            
    def load_detailed_stats(self):
        """Cargar estadísticas detalladas"""
        try:
            group_by_map = {
                0: "day",  # Día
                1: "week", # Semana
                2: "month", # Mes
                3: "documento", # Documento
                4: "usuario"  # Usuario
            }
            
            group_by = group_by_map.get(self.agrupar_combo.currentIndex(), "day")
            
            params = {
                "proyecto_id": self.current_proyecto_id,
                "date_filter": self.current_filters["date_filter"],
                "group_by": group_by
            }
            
            if self.current_filters["date_filter"] == "custom":
                if self.current_filters["start_date"] and self.current_filters["end_date"]:
                    params["start_date"] = self.current_filters["start_date"]
                    params["end_date"] = self.current_filters["end_date"]
            
            response = api_client._request(
                "GET", 
                "/api/v1/stats/stats/detalladas", 
                params=params
            )
            
            grupos = response.get('grupos', [])
            
            self.stats_table.setRowCount(len(grupos))
            
            for row, grupo in enumerate(grupos):
                # Grupo
                grupo_item = QTableWidgetItem(str(grupo.get('grupo', '')))
                self.stats_table.setItem(row, 0, grupo_item)
                
                # Total
                total_item = QTableWidgetItem(str(grupo.get('total', 0)))
                total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.stats_table.setItem(row, 1, total_item)
                
                # Tamaño total
                tamaño = grupo.get('tamaño_total', 0)
                if tamaño > 1024 * 1024:  # MB
                    tamaño_text = f"{tamaño/1024/1024:.1f} MB"
                elif tamaño > 1024:  # KB
                    tamaño_text = f"{tamaño/1024:.1f} KB"
                else:
                    tamaño_text = f"{tamaño:.0f} B"
                
                tamaño_item = QTableWidgetItem(tamaño_text)
                tamaño_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.stats_table.setItem(row, 2, tamaño_item)
                
                # Tamaño promedio
                promedio = grupo.get('tamaño_promedio', 0)
                if promedio > 1024 * 1024:  # MB
                    promedio_text = f"{promedio/1024/1024:.1f} MB"
                elif promedio > 1024:  # KB
                    promedio_text = f"{promedio/1024:.1f} KB"
                else:
                    promedio_text = f"{promedio:.0f} B"
                
                promedio_item = QTableWidgetItem(promedio_text)
                promedio_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.stats_table.setItem(row, 3, promedio_item)
                
                # Porcentaje
                porcentaje_item = QTableWidgetItem(f"{grupo.get('porcentaje', 0):.1f}%")
                porcentaje_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.stats_table.setItem(row, 4, porcentaje_item)
                
        except Exception as e:
            logger.error(f"Error cargando estadísticas detalladas: {str(e)}")
            
    def load_bitacora(self):
        """Cargar registros de bitácora"""
        try:
            if self.user_info['rol'] != "SUPERADMIN":
                return
                
            self.page_size_combo.setCurrentText(str(self.bitacora_page_size))
            
            params = {
                "skip": (self.current_bitacora_page - 1) * self.bitacora_page_size,
                "limit": self.bitacora_page_size,
                "date_filter": self.current_filters["date_filter"]
            }
            
            # Aplicar filtros
            if self.search_input.text():
                params["search"] = self.search_input.text()
                
            usuario_id = self.usuario_combo.currentData()
            if usuario_id:
                params["usuario_id"] = usuario_id
                
            accion = self.accion_combo.currentText()
            if accion and accion != "Todas":
                params["accion"] = accion
                
            if self.current_filters["date_filter"] == "custom":
                if self.current_filters["start_date"] and self.current_filters["end_date"]:
                    params["start_date"] = self.current_filters["start_date"]
                    params["end_date"] = self.current_filters["end_date"]
            
            response = api_client._request("GET", "/api/v1/stats/bitacora", params=params)
            
            items = response.get('items', [])
            total = response.get('total', 0)
            pages = response.get('pages', 1)
            
            # Actualizar tabla
            self.bitacora_table.setRowCount(len(items))
            
            for row, item in enumerate(items):
                # Fecha
                fecha = datetime.fromisoformat(item['fecha'].replace('Z', '+00:00')).strftime('%d/%m/%Y %H:%M')
                fecha_item = QTableWidgetItem(fecha)
                self.bitacora_table.setItem(row, 0, fecha_item)
                
                # Usuario
                usuario = item.get('usuario', {})
                usuario_text = f"{usuario.get('username', '')} ({usuario.get('nombre_completo', '')})"
                usuario_item = QTableWidgetItem(usuario_text)
                self.bitacora_table.setItem(row, 1, usuario_item)
                
                # Acción
                accion_item = QTableWidgetItem(item.get('accion', ''))
                self.bitacora_table.setItem(row, 2, accion_item)
                
                # Entidad
                entidad_item = QTableWidgetItem(item.get('entidad', '') or '')
                self.bitacora_table.setItem(row, 3, entidad_item)
                
                # ID Entidad
                entidad_id_item = QTableWidgetItem(str(item.get('entidad_id', '') or ''))
                self.bitacora_table.setItem(row, 4, entidad_id_item)
                
                # Detalles
                detalles = item.get('detalles', {})
                detalles_text = json.dumps(detalles, ensure_ascii=False) if detalles else ''
                detalles_item = QTableWidgetItem(detalles_text[:100] + '...' if len(detalles_text) > 100 else detalles_text)
                detalles_item.setToolTip(detalles_text)
                self.bitacora_table.setItem(row, 5, detalles_item)
                
                # IP
                ip_item = QTableWidgetItem(item.get('ip', '') or '')
                self.bitacora_table.setItem(row, 6, ip_item)
            
            # Actualizar paginación
            self.bitacora_total_pages = pages
            self.page_label.setText(f"Página {self.current_bitacora_page} de {pages} ({total} registros)")
            
            self.prev_page_btn.setEnabled(self.current_bitacora_page > 1)
            self.next_page_btn.setEnabled(self.current_bitacora_page < pages)
            
        except Exception as e:
            logger.error(f"Error cargando bitácora: {str(e)}")
            
    def on_bitacora_search(self, text):
        """Manejar búsqueda en bitácora"""
        # Usar timer para no hacer demasiadas llamadas
        if hasattr(self, 'bitacora_search_timer'):
            self.bitacora_search_timer.stop()
            
        self.bitacora_search_timer = QTimer()
        self.bitacora_search_timer.setSingleShot(True)
        self.bitacora_search_timer.timeout.connect(self.load_bitacora)
        self.bitacora_search_timer.start(500)  # 500ms delay
        
    def prev_bitacora_page(self):
        """Ir a página anterior de bitácora"""
        if self.current_bitacora_page > 1:
            self.current_bitacora_page -= 1
            self.load_bitacora()
            
    def next_bitacora_page(self):
        """Ir a página siguiente de bitácora"""
        if self.current_bitacora_page < self.bitacora_total_pages:
            self.current_bitacora_page += 1
            self.load_bitacora()
            
    def export_dashboard(self):
        """Exportar dashboard completo"""
        menu = QMenu(self)
        
        export_pdf_action = menu.addAction("Exportar a PDF")
        export_excel_action = menu.addAction("Exportar a Excel")
        export_image_action = menu.addAction("Exportar gráficas como imagen")
        
        action = menu.exec(self.mapToGlobal(self.sender().pos()))
        
        if action == export_pdf_action:
            self.export_report("pdf")
        elif action == export_excel_action:
            self.export_report("excel")
        elif action == export_image_action:
            self.export_charts_as_image()
            
    def export_report(self, format_type):
        """Exportar reporte"""
        try:
            # Preparar datos
            params = {
                "proyecto_id": self.current_proyecto_id,
                "date_filter": self.current_filters["date_filter"]
            }
            
            if self.current_filters["date_filter"] == "custom":
                if self.current_filters["start_date"] and self.current_filters["end_date"]:
                    params["start_date"] = self.current_filters["start_date"]
                    params["end_date"] = self.current_filters["end_date"]
            
            # Obtener datos
            kpis = api_client._request("GET", "/api/v1/stats/dashboard/kpis", params=params)
            emisiones = api_client._request("GET", "/api/v1/stats/dashboard/emisiones-tiempo", params=params)
            distribucion = api_client._request("GET", "/api/v1/stats/dashboard/distribucion-documentos", params=params)
            
            if format_type == "pdf":
                # En una implementación real, usaría reportlab o similar
                QMessageBox.information(
                    self,
                    "Exportar PDF",
                    "La exportación a PDF se implementaría con una librería como reportlab.\n"
                    "Por ahora, los datos están listos para exportar."
                )
                
                # Mostrar datos en un diálogo
                from PyQt6.QtWidgets import QDialog, QTextEdit, QVBoxLayout
                
                dialog = QDialog(self)
                dialog.setWindowTitle("Datos para exportación PDF")
                dialog.setGeometry(100, 100, 800, 600)
                
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                
                # Formatear datos
                report_text = f"Reporte de Dashboard\n"
                report_text += f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                report_text += f"Proyecto: {self.proyecto_combo.currentText()}\n"
                report_text += f"Período: {self.periodo_combo.currentText()}\n\n"
                
                report_text += "KPIs:\n"
                for key, value in kpis.items():
                    if key not in ['periodo', 'fecha_consulta']:
                        report_text += f"  {key}: {value}\n"
                
                report_text += "\nEmisiones en el tiempo:\n"
                for item in emisiones:
                    report_text += f"  {item.get('periodo_display', '')}: {item.get('total', 0)}\n"
                
                report_text += "\nDistribución por documento:\n"
                for item in distribucion:
                    report_text += f"  {item.get('documento', '')}: {item.get('total', 0)} ({item.get('porcentaje', 0)}%)\n"
                
                text_edit.setText(report_text)
                
                layout = QVBoxLayout(dialog)
                layout.addWidget(text_edit)
                
                dialog.exec()
                
            elif format_type == "excel":
                # Crear DataFrame y exportar
                import pandas as pd
                
                # Crear múltiples DataFrames
                kpis_df = pd.DataFrame([kpis])
                emisiones_df = pd.DataFrame(emisiones)
                distribucion_df = pd.DataFrame(distribucion)
                
                # Guardar en Excel con múltiples hojas
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Guardar reporte Excel",
                    f"reporte_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    "Excel Files (*.xlsx)"
                )
                
                if file_path:
                    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                        kpis_df.to_excel(writer, sheet_name='KPIs', index=False)
                        emisiones_df.to_excel(writer, sheet_name='Emisiones', index=False)
                        distribucion_df.to_excel(writer, sheet_name='Distribucion', index=False)
                    
                    QMessageBox.information(
                        self,
                        "Exportación exitosa",
                        f"Reporte exportado a:\n{file_path}"
                    )
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar el reporte: {str(e)}")
            
    def export_stats(self):
        """Exportar estadísticas detalladas"""
        try:
            # Obtener datos actuales
            group_by_map = {
                0: "day",  # Día
                1: "week", # Semana
                2: "month", # Mes
                3: "documento", # Documento
                4: "usuario"  # Usuario
            }
            
            group_by = group_by_map.get(self.agrupar_combo.currentIndex(), "day")
            
            params = {
                "proyecto_id": self.current_proyecto_id,
                "date_filter": self.current_filters["date_filter"],
                "group_by": group_by
            }
            
            if self.current_filters["date_filter"] == "custom":
                if self.current_filters["start_date"] and self.current_filters["end_date"]:
                    params["start_date"] = self.current_filters["start_date"]
                    params["end_date"] = self.current_filters["end_date"]
            
            response = api_client._request(
                "GET", 
                "/api/v1/stats/stats/detalladas", 
                params=params
            )
            
            # Exportar a CSV
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar estadísticas",
                f"estadisticas_{group_by}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv)"
            )
            
            if file_path:
                grupos = response.get('grupos', [])
                
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['grupo', 'total', 'tamaño_total', 'tamaño_promedio', 'porcentaje'])
                    writer.writeheader()
                    
                    for grupo in grupos:
                        writer.writerow({
                            'grupo': grupo.get('grupo', ''),
                            'total': grupo.get('total', 0),
                            'tamaño_total': grupo.get('tamaño_total', 0),
                            'tamaño_promedio': grupo.get('tamaño_promedio', 0),
                            'porcentaje': grupo.get('porcentaje', 0)
                        })
                
                QMessageBox.information(
                    self,
                    "Exportación exitosa",
                    f"Estadísticas exportadas a:\n{file_path}"
                )
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron exportar las estadísticas: {str(e)}")
            
    def export_bitacora(self):
        """Exportar bitácora"""
        try:
            # Preparar filtros
            filters = {
                "date_filter": self.current_filters["date_filter"]
            }
            
            if self.current_filters["date_filter"] == "custom":
                if self.current_filters["start_date"] and self.current_filters["end_date"]:
                    filters["start_date"] = self.current_filters["start_date"]
                    filters["end_date"] = self.current_filters["end_date"]
            
            if self.search_input.text():
                filters["search"] = self.search_input.text()
                
            usuario_id = self.usuario_combo.currentData()
            if usuario_id:
                filters["usuario_id"] = usuario_id
                
            accion = self.accion_combo.currentText()
            if accion and accion != "Todas":
                filters["accion"] = accion
            
            # Llamar a API de exportación
            response = api_client._request(
                "POST",
                "/api/v1/stats/bitacora/export",
                json=filters,
                params={"format": "csv"}
            )
            
            # Guardar archivo
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar bitácora",
                response.get('filename', f"bitacora_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"),
                "CSV Files (*.csv);;JSON Files (*.json)"
            )
            
            if file_path:
                content = response.get('content', '')
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                QMessageBox.information(
                    self,
                    "Exportación exitosa",
                    f"Bitácora exportada a:\n{file_path}"
                )
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar la bitácora: {str(e)}")
            
    def export_charts_as_image(self):
        """Exportar gráficas como imágenes"""
        # En una implementación real, guardaría las figuras de matplotlib
        QMessageBox.information(
            self,
            "Exportar gráficas",
            "La funcionalidad de exportar gráficas como imagen está disponible.\n"
            "Cada gráfica tiene un botón de exportación en su esquina superior derecha."
        )
        
    def show_help(self):
        """Mostrar ayuda"""
        help_text = """
        <h3>Ayuda del Dashboard</h3>
        
        <p><b>Dashboard Principal:</b></p>
        <ul>
            <li><b>KPIs:</b> Métricas clave del sistema</li>
            <li><b>Gráfica de líneas:</b> Emisiones en el tiempo</li>
            <li><b>Gráfica de pastel:</b> Distribución por tipo de documento</li>
            <li><b>Gráfica de barras:</b> Productividad por usuario (solo Superadmin)</li>
        </ul>
        
        <p><b>Estadísticas:</b></p>
        <ul>
            <li>Estadísticas detalladas con diferentes agrupaciones</li>
            <li>Exportación a CSV</li>
        </ul>
        
        <p><b>Bitácora (solo Superadmin):</b></p>
        <ul>
            <li>Registro completo de todas las acciones</li>
            <li>Búsqueda y filtrado avanzado</li>
            <li>Exportación a CSV/JSON</li>
            <li>Paginación de resultados</li>
        </ul>
        
        <p><b>Filtros:</b></p>
        <ul>
            <li><b>Proyecto:</b> Filtrar por proyecto específico</li>
            <li><b>Período:</b> Hoy, 7 días, 30 días o personalizado</li>
            <li><b>Aplicar filtros:</b> Botón para aplicar cambios</li>
        </ul>
        
        <p><b>Atajos de teclado:</b></p>
        <ul>
            <li><b>F5:</b> Refrescar dashboard</li>
            <li><b>Ctrl+E:</b> Exportar</li>
        </ul>
        """
        
        QMessageBox.information(self, "Ayuda", help_text)