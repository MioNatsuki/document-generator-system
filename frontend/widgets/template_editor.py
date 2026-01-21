# Editor visual de plantillas
import os
import json
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QGroupBox, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QCheckBox, QFileDialog, QMessageBox, QProgressDialog,
    QApplication, QToolBar, QStatusBar, QDialog, QDialogButtonBox,
    QScrollArea, QFrame, QTabWidget, QTextEdit, QDoubleSpinBox,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsItem, QColorDialog, QFontDialog, QInputDialog,
    QRadioButton, QButtonGroup, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QSize, QTimer
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QBrush, QColor, QFont,
    QAction, QIcon, QKeySequence, QMouseEvent, QWheelEvent,
    QPainterPath
)
import sys
import uuid

from config import config
from styles import styles
from utils.api_client import api_client, APIError
from utils.file_dialogs import FileDialog


class TemplateEditor(QMainWindow):
    """Editor visual de plantillas PDF"""
    
    template_saved = pyqtSignal()
    
    def __init__(self, proyecto, plantilla=None, parent=None):
        super().__init__(parent)
        self.proyecto = proyecto
        self.plantilla = plantilla
        self.docx_path = None
        self.placeholders = []
        self.mappings = []
        self.padron_fields = []
        self.current_mapping_index = -1
        self.is_drawing = False
        self.start_point = None
        self.current_rect = None
        
        self.setWindowTitle(f"Editor de Plantillas - {proyecto['nombre']}")
        self.setGeometry(100, 100, 1400, 900)
        self.setStyleSheet(styles.get_main_style())
        
        self.init_ui()
        if plantilla:
            self.load_existing_template()
        else:
            self.load_padron_fields()
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Barra de herramientas
        self.create_toolbar()
        
        # Área principal con splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo: Configuración
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Panel central: Vista previa
        center_panel = self.create_center_panel()
        splitter.addWidget(center_panel)
        
        # Panel derecho: Propiedades
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([300, 800, 300])
        
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
        
        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("Listo")
        
    def create_toolbar(self):
        """Crear barra de herramientas"""
        toolbar = self.addToolBar("Editor")
        toolbar.setMovable(False)
        
        # Cargar DOCX
        load_action = QAction("📄 Cargar DOCX", self)
        load_action.triggered.connect(self.load_docx_file)
        load_action.setShortcut(QKeySequence.StandardKey.Open)
        toolbar.addAction(load_action)
        
        toolbar.addSeparator()
        
        # Modos de edición
        mode_group = QButtonGroup(self)
        
        select_action = QAction("🔍 Seleccionar", self)
        select_action.setCheckable(True)
        select_action.setChecked(True)
        select_action.triggered.connect(lambda: self.set_edit_mode("select"))
        
        draw_action = QAction("📐 Dibujar área", self)
        draw_action.setCheckable(True)
        draw_action.triggered.connect(lambda: self.set_edit_mode("draw"))
        
        mode_group.addAction(select_action)
        mode_group.addAction(draw_action)
        
        toolbar.addAction(select_action)
        toolbar.addAction(draw_action)
        
        toolbar.addSeparator()
        
        # Validar
        validate_action = QAction("✅ Validar", self)
        validate_action.triggered.connect(self.validate_template)
        toolbar.addAction(validate_action)
        
        # Preview con datos
        preview_action = QAction("👁️ Vista previa con datos", self)
        preview_action.triggered.connect(self.generate_preview_with_data)
        toolbar.addAction(preview_action)
        
        toolbar.addSeparator()
        
        # Guardar
        save_action = QAction("💾 Guardar", self)
        save_action.triggered.connect(self.save_template)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        toolbar.addAction(save_action)
        
    def create_left_panel(self):
        """Crear panel izquierdo de configuración"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Información de la plantilla
        info_group = QGroupBox("📋 Información de la Plantilla")
        info_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nombre de la plantilla")
        
        self.desc_input = QTextEdit()
        self.desc_input.setMaximumHeight(80)
        self.desc_input.setPlaceholderText("Descripción (opcional)")
        
        info_layout.addRow("Nombre:*", self.name_input)
        info_layout.addRow("Descripción:", self.desc_input)
        info_group.setLayout(info_layout)
        
        # Archivo cargado
        self.file_group = QGroupBox("📄 Documento Base")
        file_layout = QVBoxLayout()
        
        self.file_label = QLabel("No hay documento cargado")
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("color: #666; padding: 5px;")
        
        load_btn = QPushButton("📁 Cargar DOCX")
        load_btn.setStyleSheet(styles.get_main_style())
        load_btn.clicked.connect(self.load_docx_file)
        
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(load_btn)
        self.file_group.setLayout(file_layout)
        
        # Lista de mapeos
        mappings_group = QGroupBox("🗺️ Mapeos Configurados")
        mappings_layout = QVBoxLayout()
        
        self.mappings_list = QListWidget()
        self.mappings_list.itemClicked.connect(self.on_mapping_selected)
        self.mappings_list.setAlternatingRowColors(True)
        
        mappings_layout.addWidget(self.mappings_list)
        
        # Botones para gestionar mapeos
        mappings_buttons_layout = QHBoxLayout()
        
        add_mapping_btn = QPushButton("➕ Agregar")
        add_mapping_btn.setStyleSheet(styles.get_main_style())
        add_mapping_btn.clicked.connect(self.add_mapping)
        
        edit_mapping_btn = QPushButton("✏️ Editar")
        edit_mapping_btn.setStyleSheet(styles.get_main_style())
        edit_mapping_btn.clicked.connect(self.edit_selected_mapping)
        
        delete_mapping_btn = QPushButton("🗑️ Eliminar")
        delete_mapping_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {config.COLORS['danger']};
                color: white;
                border: 2px solid {config.COLORS['danger']};
            }}
        """)
        delete_mapping_btn.clicked.connect(self.delete_selected_mapping)
        
        mappings_buttons_layout.addWidget(add_mapping_btn)
        mappings_buttons_layout.addWidget(edit_mapping_btn)
        mappings_buttons_layout.addWidget(delete_mapping_btn)
        
        mappings_layout.addLayout(mappings_buttons_layout)
        mappings_group.setLayout(mappings_layout)
        
        # Placeholders detectados
        placeholders_group = QGroupBox("🔍 Placeholders Detectados")
        placeholders_layout = QVBoxLayout()
        
        self.placeholders_list = QListWidget()
        self.placeholders_list.setAlternatingRowColors(True)
        
        placeholders_layout.addWidget(self.placeholders_list)
        placeholders_group.setLayout(placeholders_layout)
        
        # Agregar grupos al layout
        layout.addWidget(info_group)
        layout.addWidget(self.file_group)
        layout.addWidget(mappings_group, 1)  # Stretch
        layout.addWidget(placeholders_group)
        
        panel.setLayout(layout)
        return panel
    
    def create_center_panel(self):
        """Crear panel central con vista previa del PDF"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Barra de herramientas de vista previa
        preview_toolbar = QHBoxLayout()
        preview_toolbar.setContentsMargins(5, 5, 5, 5)
        
        zoom_label = QLabel("Zoom:")
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["25%", "50%", "75%", "100%", "150%", "200%"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.currentTextChanged.connect(self.update_zoom)
        
        self.show_mappings_check = QCheckBox("Mostrar áreas mapeadas")
        self.show_mappings_check.setChecked(True)
        self.show_mappings_check.stateChanged.connect(self.update_preview)
        
        preview_toolbar.addWidget(zoom_label)
        preview_toolbar.addWidget(self.zoom_combo)
        preview_toolbar.addStretch()
        preview_toolbar.addWidget(self.show_mappings_check)
        
        # Vista gráfica del PDF
        self.graphics_view = QGraphicsView()
        self.graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.graphics_view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.graphics_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        
        self.scene = QGraphicsScene()
        self.graphics_view.setScene(self.scene)
        
        # Instrucciones
        instructions = QLabel(
            "<b>Instrucciones:</b><br>"
            "• Click y arrastrar para dibujar áreas de texto<br>"
            "• Doble click en un área para editarla<br>"
            "• Use la rueda del mouse para hacer zoom<br>"
            "• Arrastre con el botón derecho para mover la vista"
        )
        instructions.setStyleSheet("background-color: #f8f9fa; padding: 10px; border-top: 1px solid #dee2e6;")
        instructions.setWordWrap(True)
        
        layout.addLayout(preview_toolbar)
        layout.addWidget(self.graphics_view, 1)  # Stretch
        layout.addWidget(instructions)
        
        panel.setLayout(layout)
        
        # Conectar eventos del mouse
        self.graphics_view.mousePressEvent = self.on_mouse_press
        self.graphics_view.mouseMoveEvent = self.on_mouse_move
        self.graphics_view.mouseReleaseEvent = self.on_mouse_release
        self.graphics_view.wheelEvent = self.on_wheel_event
        
        return panel
    
    def create_right_panel(self):
        """Crear panel derecho de propiedades"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Propiedades del mapeo seleccionado
        self.properties_group = QGroupBox("⚙️ Propiedades del Mapeo")
        self.properties_layout = QFormLayout()
        
        # Campo del padrón
        self.field_combo = QComboBox()
        self.properties_layout.addRow("Campo del padrón:*", self.field_combo)
        
        # Coordenadas
        coords_layout = QHBoxLayout()
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(0, 100)
        self.x_spin.setDecimals(2)
        self.x_spin.setSuffix(" cm")
        
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(0, 100)
        self.y_spin.setDecimals(2)
        self.y_spin.setSuffix(" cm")
        
        coords_layout.addWidget(QLabel("X:"))
        coords_layout.addWidget(self.x_spin)
        coords_layout.addWidget(QLabel("Y:"))
        coords_layout.addWidget(self.y_spin)
        self.properties_layout.addRow("Posición:", coords_layout)
        
        # Tamaño
        size_layout = QHBoxLayout()
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.1, 20)
        self.width_spin.setDecimals(2)
        self.width_spin.setSuffix(" cm")
        
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(0.1, 20)
        self.height_spin.setDecimals(2)
        self.height_spin.setSuffix(" cm")
        
        size_layout.addWidget(QLabel("Ancho:"))
        size_layout.addWidget(self.width_spin)
        size_layout.addWidget(QLabel("Alto:"))
        size_layout.addWidget(self.height_spin)
        self.properties_layout.addRow("Tamaño:", size_layout)
        
        # Fuente
        font_layout = QHBoxLayout()
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Calibri", "Arial", "Times New Roman", "Helvetica", "Courier"])
        self.font_combo.setCurrentText("Calibri")
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(11)
        
        font_layout.addWidget(self.font_combo)
        font_layout.addWidget(QLabel("Tamaño:"))
        font_layout.addWidget(self.font_size_spin)
        self.properties_layout.addRow("Fuente:", font_layout)
        
        # Opciones avanzadas
        self.barcode_check = QCheckBox("Es código de barras")
        self.barcode_check.stateChanged.connect(self.on_barcode_changed)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["", "Moneda ($#,##0.00)", "Fecha (DD/MM/YYYY)", "Número (#,##0)", "Texto mayúsculas"])
        
        self.properties_layout.addRow("Código de barras:", self.barcode_check)
        self.properties_layout.addRow("Formato:", self.format_combo)
        
        # Botones de acciones
        buttons_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("💾 Aplicar cambios")
        self.apply_btn.setStyleSheet(styles.get_main_style())
        self.apply_btn.clicked.connect(self.apply_mapping_changes)
        self.apply_btn.setEnabled(False)
        
        self.cancel_btn = QPushButton("❌ Cancelar")
        self.cancel_btn.setStyleSheet(styles.get_main_style())
        self.cancel_btn.clicked.connect(self.cancel_mapping_changes)
        self.cancel_btn.setEnabled(False)
        
        buttons_layout.addWidget(self.apply_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        self.properties_layout.addRow("", buttons_layout)
        
        self.properties_group.setLayout(self.properties_layout)
        
        # Validación de plantilla
        validation_group = QGroupBox("✅ Validación")
        validation_layout = QVBoxLayout()
        
        self.validation_label = QLabel("No se ha validado la plantilla")
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("padding: 10px; background-color: #f8f9fa; border-radius: 5px;")
        
        validate_btn = QPushButton("🔍 Validar plantilla")
        validate_btn.setStyleSheet(styles.get_main_style())
        validate_btn.clicked.connect(self.validate_template)
        
        validation_layout.addWidget(self.validation_label)
        validation_layout.addWidget(validate_btn)
        validation_group.setLayout(validation_layout)
        
        # Agregar al layout
        layout.addWidget(self.properties_group)
        layout.addWidget(validation_group)
        layout.addStretch()
        
        panel.setLayout(layout)
        return panel
    
    def load_existing_template(self):
        """Cargar plantilla existente"""
        try:
            if not self.plantilla:
                return
            
            self.name_input.setText(self.plantilla.get('nombre', ''))
            self.desc_input.setText(self.plantilla.get('descripcion', ''))
            
            # Cargar información del archivo
            docx_path = self.plantilla.get('archivo_docx', '')
            if docx_path and os.path.exists(docx_path):
                self.docx_path = Path(docx_path)
                self.file_label.setText(f"✓ {os.path.basename(docx_path)}")
            
            # Cargar mapeos
            configuracion = self.plantilla.get('configuracion', {})
            self.mappings = configuracion.get('mapeos', [])
            self.placeholders = configuracion.get('placeholders_detectados', [])
            
            # Actualizar listas
            self.update_mappings_list()
            self.update_placeholders_list()
            
            # Cargar imagen de vista previa
            self.load_preview_image()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando plantilla: {str(e)}")
    
    def load_padron_fields(self):
        """Cargar campos del padrón desde la API"""
        try:
            response = api_client.obtener_estructura_padron(self.proyecto['id'])
            estructura = response.get('estructura', [])
            
            self.padron_fields = [col['nombre'] for col in estructura]
            self.field_combo.clear()
            self.field_combo.addItems(self.padron_fields)
            
        except APIError as e:
            QMessageBox.warning(self, "Advertencia", f"No se pudieron cargar los campos del padrón: {str(e)}")
            self.padron_fields = []
    
    def load_docx_file(self):
        """Cargar archivo DOCX"""
        file_path = FileDialog.open_docx_file(self, "Seleccionar plantilla DOCX")
        
        if file_path:
            try:
                # Validar tamaño del archivo
                max_size_mb = 10  # 10MB máximo para DOCX
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                
                if file_size_mb > max_size_mb:
                    reply = QMessageBox.question(
                        self,
                        "Archivo grande",
                        f"El archivo es grande ({file_size_mb:.1f} MB). ¿Deseas continuar?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return
                
                self.docx_path = Path(file_path)
                self.file_label.setText(f"✓ {os.path.basename(file_path)}")
                
                # Extraer placeholders del documento
                self.extract_placeholders()
                
                # Convertir a PDF para vista previa
                self.generate_preview_image()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error cargando documento: {str(e)}")
    
    def extract_placeholders(self):
        """Extraer placeholders del documento DOCX"""
        try:
            # Usar API para extraer placeholders
            # En una implementación real, esto se haría en el backend
            # Por ahora, simulamos la extracción
            self.placeholders = [
                "nombre", "cuenta", "direccion", "monto", "fecha",
                "referencia", "observaciones", "codigo_barras"
            ]
            
            self.update_placeholders_list()
            
            # Verificar mapeos existentes
            unmatched = []
            for mapping in self.mappings:
                campo = mapping.get('campo_padron')
                if campo not in self.placeholders:
                    unmatched.append(campo)
            
            if unmatched:
                QMessageBox.warning(
                    self,
                    "Placeholders no encontrados",
                    f"Los siguientes campos mapeados no se encontraron en el documento: {', '.join(unmatched)}"
                )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error extrayendo placeholders: {str(e)}")
    
    def generate_preview_image(self):
        """Generar imagen de vista previa del PDF"""
        try:
            if not self.docx_path:
                return
            
            # Crear PDF temporal
            temp_dir = Path(tempfile.gettempdir())
            pdf_path = temp_dir / f"preview_{uuid.uuid4()}.pdf"
            
            # En producción, esto llamaría a la API para convertir DOCX a PDF
            # Por ahora, creamos un PDF placeholder
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.lib import colors
            
            c = canvas.Canvas(str(pdf_path), pagesize=letter)
            
            # Fondo color pastel
            c.setFillColor(colors.HexColor("#E8F4FD"))  # Azul pastel
            c.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
            
            # Título
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 24)
            c.drawCentredString(letter[0]/2, letter[1] - 100, "VISTA PREVIA DE DOCUMENTO")
            
            # Información del documento
            c.setFont("Helvetica", 12)
            c.drawString(100, letter[1] - 150, f"Documento: {self.docx_path.name}")
            c.drawString(100, letter[1] - 180, f"Tamaño: 21.59cm x 34.01cm (México Oficio)")
            
            # Simular áreas de texto
            c.setFillColor(colors.HexColor("#FFF9C4"))  # Amarillo pastel
            c.rect(100, 400, 200, 30, fill=1, stroke=1)
            c.setFillColor(colors.black)
            c.drawString(105, 415, "{{nombre}}")
            
            c.setFillColor(colors.HexColor("#C8E6C9"))  # Verde pastel
            c.rect(100, 350, 150, 30, fill=1, stroke=1)
            c.setFillColor(colors.black)
            c.drawString(105, 365, "{{cuenta}}")
            
            c.setFillColor(colors.HexColor("#FFCCBC"))  # Naranja pastel
            c.rect(100, 300, 200, 30, fill=1, stroke=1)
            c.setFillColor(colors.black)
            c.drawString(105, 315, "{{direccion}}")
            
            c.setFillColor(colors.HexColor("#E1BEE7"))  # Morado pastel
            c.rect(100, 250, 100, 30, fill=1, stroke=1)
            c.setFillColor(colors.black)
            c.drawString(105, 265, "{{monto}}")
            
            c.setFillColor(colors.HexColor("#BBDEFB"))  # Azul claro
            c.rect(100, 200, 120, 30, fill=1, stroke=1)
            c.setFillColor(colors.black)
            c.drawString(105, 215, "{{fecha}}")
            
            c.save()
            
            # Cargar PDF como imagen
            self.load_pdf_as_image(pdf_path)
            
            # Limpiar
            pdf_path.unlink(missing_ok=True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generando vista previa: {str(e)}")
    
    def load_pdf_as_image(self, pdf_path):
        """Cargar PDF como imagen para vista previa"""
        try:
            # En producción, usaríamos una librería como pdf2image
            # Por ahora, creamos una imagen de placeholder
            from reportlab.lib.pagesizes import letter
            
            # Crear imagen QPixmap
            width, height = letter
            scale = 1.5  # Escala para mejor visualización
            pixmap = QPixmap(int(width * scale), int(height * scale))
            pixmap.fill(QColor("#E8F4FD"))
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Dibujar fondo
            painter.fillRect(0, 0, int(width * scale), int(height * scale), QColor("#E8F4FD"))
            
            # Dibujar bordes de página
            painter.setPen(QPen(QColor("#4a6fa5"), 2))
            painter.setBrush(QBrush(QColor("white")))
            painter.drawRect(10, 10, int((width - 20) * scale), int((height - 20) * scale))
            
            # Dibujar áreas de texto simuladas
            areas = [
                (100, 400, 200, 30, "#FFF9C4", "{{nombre}}"),
                (100, 350, 150, 30, "#C8E6C9", "{{cuenta}}"),
                (100, 300, 200, 30, "#FFCCBC", "{{direccion}}"),
                (100, 250, 100, 30, "#E1BEE7", "{{monto}}"),
                (100, 200, 120, 30, "#BBDEFB", "{{fecha}}"),
            ]
            
            for x, y, w, h, color, text in areas:
                painter.setPen(QPen(QColor("#666"), 1))
                painter.setBrush(QBrush(QColor(color)))
                painter.drawRect(
                    int(x * scale),
                    int((height - y) * scale),  # Invertir Y
                    int(w * scale),
                    int(h * scale)
                )
                
                painter.setPen(QPen(QColor("black")))
                painter.setFont(QFont("Arial", 10))
                painter.drawText(
                    int((x + 5) * scale),
                    int((height - y + 20) * scale),
                    text
                )
            
            painter.end()
            
            # Mostrar en la escena
            self.scene.clear()
            self.scene.addPixmap(pixmap)
            
            # Ajustar vista
            self.graphics_view.fitInView(QRectF(0, 0, pixmap.width(), pixmap.height()), Qt.AspectRatioMode.KeepAspectRatio)
            
            # Dibujar áreas mapeadas
            self.draw_mapping_areas()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando PDF: {str(e)}")
    
    def update_mappings_list(self):
        """Actualizar lista de mapeos"""
        self.mappings_list.clear()
        
        for i, mapping in enumerate(self.mappings):
            campo = mapping.get('campo_padron', '')
            x = mapping.get('x', 0)
            y = mapping.get('y', 0)
            
            item = QListWidgetItem(f"{i+1}. {campo} ({x:.1f}, {y:.1f})")
            
            # Color según estado
            if campo in self.placeholders:
                item.setForeground(QColor("#28a745"))
            else:
                item.setForeground(QColor("#dc3545"))
            
            self.mappings_list.addItem(item)
    
    def update_placeholders_list(self):
        """Actualizar lista de placeholders"""
        self.placeholders_list.clear()
        
        for placeholder in self.placeholders:
            # Verificar si está mapeado
            is_mapped = any(m.get('campo_padron') == placeholder for m in self.mappings)
            
            item = QListWidgetItem(placeholder)
            
            if is_mapped:
                item.setForeground(QColor("#28a745"))
                item.setText(f"✓ {placeholder}")
            else:
                item.setForeground(QColor("#dc3545"))
                item.setText(f"✗ {placeholder}")
            
            self.placeholders_list.addItem(item)
    
    def draw_mapping_areas(self):
        """Dibujar áreas mapeadas en la vista previa"""
        if not self.show_mappings_check.isChecked():
            return
        
        # Escala de la vista
        view_rect = self.graphics_view.viewport().rect()
        scene_rect = self.graphics_view.mapToScene(view_rect).boundingRect()
        
        for mapping in self.mappings:
            campo = mapping.get('campo_padron', '')
            x = mapping.get('x', 0)
            y = mapping.get('y', 0)
            width = mapping.get('ancho', 0)
            height = mapping.get('alto', 0)
            
            # Convertir cm a píxeles (aproximado)
            scale = 37.8  # 1 cm ≈ 37.8 píxeles a 96 DPI
            rect = QRectF(
                x * scale,
                y * scale,
                width * scale,
                height * scale
            )
            
            # Crear rectángulo
            rect_item = QGraphicsRectItem(rect)
            rect_item.setPen(QPen(QColor("#ff6b35"), 2))  # Naranja
            rect_item.setBrush(QBrush(QColor(255, 107, 53, 50)))  # Naranja semitransparente
            
            # Texto del campo
            text_item = QGraphicsTextItem(campo)
            text_item.setDefaultTextColor(QColor("#ff6b35"))
            text_item.setFont(QFont("Arial", 8))
            text_item.setPos(rect.x(), rect.y() - 15)
            
            self.scene.addItem(rect_item)
            self.scene.addItem(text_item)
    
    def set_edit_mode(self, mode):
        """Establecer modo de edición"""
        self.edit_mode = mode
        
        if mode == "select":
            self.graphics_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        elif mode == "draw":
            self.graphics_view.setDragMode(QGraphicsView.DragMode.NoDrag)
    
    def on_mouse_press(self, event):
        """Manejar presión del mouse"""
        if self.edit_mode == "draw" and event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = True
            self.start_point = self.graphics_view.mapToScene(event.pos())
            self.current_rect = QGraphicsRectItem()
            self.current_rect.setPen(QPen(QColor("#4a6fa5"), 2))
            self.current_rect.setBrush(QBrush(QColor(74, 111, 165, 50)))
            self.scene.addItem(self.current_rect)
        else:
            QGraphicsView.mousePressEvent(self.graphics_view, event)
    
    def on_mouse_move(self, event):
        """Manejar movimiento del mouse"""
        if self.is_drawing and self.current_rect:
            current_point = self.graphics_view.mapToScene(event.pos())
            rect = QRectF(self.start_point, current_point).normalized()
            
            # Convertir píxeles a cm
            scale = 37.8
            self.current_rect.setRect(rect)
        else:
            QGraphicsView.mouseMoveEvent(self.graphics_view, event)
    
    def on_mouse_release(self, event):
        """Manejar liberación del mouse"""
        if self.is_drawing and self.current_rect and event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
            
            # Obtener rectángulo final
            end_point = self.graphics_view.mapToScene(event.pos())
            rect = QRectF(self.start_point, end_point).normalized()
            
            # Convertir píxeles a cm
            scale = 37.8
            x_cm = rect.x() / scale
            y_cm = rect.y() / scale
            width_cm = rect.width() / scale
            height_cm = rect.height() / scale
            
            # Crear nuevo mapeo
            self.create_mapping_dialog(x_cm, y_cm, width_cm, height_cm)
            
            # Limpiar rectángulo temporal
            self.scene.removeItem(self.current_rect)
            self.current_rect = None
            
        else:
            QGraphicsView.mouseReleaseEvent(self.graphics_view, event)
    
    def on_wheel_event(self, event):
        """Manejar evento de rueda del mouse para zoom"""
        factor = 1.2
        if event.angleDelta().y() > 0:
            self.graphics_view.scale(factor, factor)
        else:
            self.graphics_view.scale(1/factor, 1/factor)
        event.accept()
    
    def update_zoom(self, zoom_text):
        """Actualizar nivel de zoom"""
        try:
            zoom = float(zoom_text.strip('%')) / 100
            self.graphics_view.resetTransform()
            self.graphics_view.scale(zoom, zoom)
        except:
            pass
    
    def update_preview(self):
        """Actualizar vista previa"""
        self.scene.clear()
        self.load_preview_image()
    
    def create_mapping_dialog(self, x, y, width, height):
        """Crear diálogo para nuevo mapeo"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Nuevo Mapeo")
        dialog.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        # Campo del padrón
        field_combo = QComboBox()
        field_combo.addItems(self.padron_fields)
        
        # Coordenadas
        x_spin = QDoubleSpinBox()
        x_spin.setRange(0, 100)
        x_spin.setDecimals(2)
        x_spin.setValue(x)
        x_spin.setSuffix(" cm")
        
        y_spin = QDoubleSpinBox()
        y_spin.setRange(0, 100)
        y_spin.setDecimals(2)
        y_spin.setValue(y)
        y_spin.setSuffix(" cm")
        
        coords_layout = QHBoxLayout()
        coords_layout.addWidget(x_spin)
        coords_layout.addWidget(QLabel("X"))
        coords_layout.addWidget(y_spin)
        coords_layout.addWidget(QLabel("Y"))
        
        # Tamaño
        width_spin = QDoubleSpinBox()
        width_spin.setRange(0.1, 20)
        width_spin.setDecimals(2)
        width_spin.setValue(width)
        width_spin.setSuffix(" cm")
        
        height_spin = QDoubleSpinBox()
        height_spin.setRange(0.1, 20)
        height_spin.setDecimals(2)
        height_spin.setValue(height)
        height_spin.setSuffix(" cm")
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(width_spin)
        size_layout.addWidget(QLabel("Ancho"))
        size_layout.addWidget(height_spin)
        size_layout.addWidget(QLabel("Alto"))
        
        form_layout.addRow("Campo del padrón:*", field_combo)
        form_layout.addRow("Posición:", coords_layout)
        form_layout.addRow("Tamaño:", size_layout)
        
        # Botones
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        layout.addLayout(form_layout)
        layout.addWidget(button_box)
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            mapping = {
                "campo_padron": field_combo.currentText(),
                "x": x_spin.value(),
                "y": y_spin.value(),
                "ancho": width_spin.value(),
                "alto": height_spin.value(),
                "fuente": "Calibri",
                "tamaño": 11,
                "es_codigo_barras": False,
                "formato": ""
            }
            
            self.mappings.append(mapping)
            self.update_mappings_list()
            self.update_placeholders_list()
            self.update_preview()
    
    def add_mapping(self):
        """Agregar nuevo mapeo manualmente"""
        self.create_mapping_dialog(1, 1, 5, 1)
    
    def on_mapping_selected(self, item):
        """Manejar selección de mapeo en la lista"""
        index = self.mappings_list.row(item)
        if 0 <= index < len(self.mappings):
            self.current_mapping_index = index
            mapping = self.mappings[index]
            
            # Cargar valores en los controles
            self.field_combo.setCurrentText(mapping.get('campo_padron', ''))
            self.x_spin.setValue(mapping.get('x', 0))
            self.y_spin.setValue(mapping.get('y', 0))
            self.width_spin.setValue(mapping.get('ancho', 0))
            self.height_spin.setValue(mapping.get('alto', 0))
            self.font_combo.setCurrentText(mapping.get('fuente', 'Calibri'))
            self.font_size_spin.setValue(mapping.get('tamaño', 11))
            self.barcode_check.setChecked(mapping.get('es_codigo_barras', False))
            self.format_combo.setCurrentText(mapping.get('formato', ''))
            
            # Habilitar botones
            self.apply_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
    
    def edit_selected_mapping(self):
        """Editar mapeo seleccionado"""
        if self.current_mapping_index >= 0:
            # Los cambios ya se reflejan en los controles
            # Solo necesitamos permitir la edición
            pass
        else:
            QMessageBox.warning(self, "Advertencia", "Selecciona un mapeo para editar")
    
    def delete_selected_mapping(self):
        """Eliminar mapeo seleccionado"""
        if self.current_mapping_index >= 0:
            reply = QMessageBox.question(
                self,
                "Confirmar eliminación",
                "¿Estás seguro de eliminar este mapeo?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                del self.mappings[self.current_mapping_index]
                self.current_mapping_index = -1
                self.update_mappings_list()
                self.update_placeholders_list()
                self.update_preview()
                
                # Deshabilitar botones
                self.apply_btn.setEnabled(False)
                self.cancel_btn.setEnabled(False)
        else:
            QMessageBox.warning(self, "Advertencia", "Selecciona un mapeo para eliminar")
    
    def apply_mapping_changes(self):
        """Aplicar cambios al mapeo actual"""
        if self.current_mapping_index >= 0:
            mapping = self.mappings[self.current_mapping_index]
            
            mapping.update({
                "campo_padron": self.field_combo.currentText(),
                "x": self.x_spin.value(),
                "y": self.y_spin.value(),
                "ancho": self.width_spin.value(),
                "alto": self.height_spin.value(),
                "fuente": self.font_combo.currentText(),
                "tamaño": self.font_size_spin.value(),
                "es_codigo_barras": self.barcode_check.isChecked(),
                "formato": self.format_combo.currentText()
            })
            
            self.update_mappings_list()
            self.update_placeholders_list()
            self.update_preview()
            
            QMessageBox.information(self, "Éxito", "Cambios aplicados correctamente")
    
    def cancel_mapping_changes(self):
        """Cancelar cambios al mapeo actual"""
        self.current_mapping_index = -1
        self.apply_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        
        # Limpiar controles
        self.field_combo.setCurrentIndex(0)
        self.x_spin.setValue(0)
        self.y_spin.setValue(0)
        self.width_spin.setValue(0)
        self.height_spin.setValue(0)
        self.font_combo.setCurrentText("Calibri")
        self.font_size_spin.setValue(11)
        self.barcode_check.setChecked(False)
        self.format_combo.setCurrentText("")
    
    def on_barcode_changed(self, state):
        """Manejar cambio en checkbox de código de barras"""
        if state == Qt.CheckState.Checked.value:
            # Auto-ajustar configuración para código de barras
            self.font_combo.setCurrentText("Code 128")
            self.font_size_spin.setValue(10)
            self.format_combo.setCurrentText("")
        else:
            self.font_combo.setCurrentText("Calibri")
            self.font_size_spin.setValue(11)
    
    def validate_template(self):
        """Validar plantilla"""
        errors = []
        warnings = []
        
        # Validar nombre
        if not self.name_input.text().strip():
            errors.append("El nombre de la plantilla es requerido")
        
        # Validar documento
        if not self.docx_path:
            errors.append("No se ha cargado un documento DOCX")
        
        # Validar mapeos
        if not self.mappings:
            warnings.append("No hay mapeos configurados")
        else:
            # Verificar placeholders no mapeados
            for placeholder in self.placeholders:
                if not any(m.get('campo_padron') == placeholder for m in self.mappings):
                    warnings.append(f"Placeholder '{placeholder}' no está mapeado")
            
            # Verificar mapeos sin placeholders
            for mapping in self.mappings:
                campo = mapping.get('campo_padron')
                if campo not in self.placeholders:
                    warnings.append(f"Campo mapeado '{campo}' no existe en el documento")
        
        # Mostrar resultados
        if errors:
            self.validation_label.setText(
                f"<b style='color: #dc3545;'>❌ Plantilla no válida</b><br>"
                f"Errores: {', '.join(errors)}"
            )
        elif warnings:
            self.validation_label.setText(
                f"<b style='color: #ffc107;'>⚠️ Plantilla con advertencias</b><br>"
                f"Advertencias: {', '.join(warnings)}"
            )
        else:
            self.validation_label.setText(
                f"<b style='color: #28a745;'>✅ Plantilla válida</b><br>"
                f"Lista para guardar"
            )
        
        # Mostrar mensaje
        if errors:
            QMessageBox.critical(self, "Errores de validación", "\n".join(errors))
        elif warnings:
            QMessageBox.warning(self, "Advertencias de validación", "\n".join(warnings))
        else:
            QMessageBox.information(self, "Validación exitosa", "La plantilla pasa todas las validaciones")
    
    def generate_preview_with_data(self):
        """Generar vista previa con datos reales"""
        try:
            if not self.mappings:
                QMessageBox.warning(self, "Advertencia", "No hay mapeos configurados para generar vista previa")
                return
            
            # Obtener datos de muestra del padrón
            response = api_client.obtener_muestra_padron(self.proyecto['id'], limit=1)
            datos = response.get('muestra', [])
            
            if not datos:
                QMessageBox.warning(self, "Advertencia", "No hay datos en el padrón para generar vista previa")
                return
            
            # En producción, esto llamaría a la API para generar el PDF
            # Por ahora, mostramos un mensaje
            QMessageBox.information(
                self,
                "Vista previa con datos",
                f"Se generaría un PDF con datos reales del padrón.\n\n"
                f"Datos usados: {json.dumps(datos[0], indent=2, ensure_ascii=False)}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generando vista previa: {str(e)}")
    
    def save_template(self):
        """Guardar plantilla"""
        try:
            # Validar antes de guardar
            self.validate_template()
            
            nombre = self.name_input.text().strip()
            descripcion = self.desc_input.toPlainText().strip()
            
            if not nombre:
                QMessageBox.critical(self, "Error", "El nombre de la plantilla es requerido")
                return
            
            if not self.docx_path:
                QMessageBox.critical(self, "Error", "Debes cargar un documento DOCX")
                return
            
            # Crear plantilla nueva o actualizar existente
            if self.plantilla:
                # Actualizar plantilla existente
                response = api_client.actualizar_plantilla(
                    self.plantilla['id'],
                    nombre=nombre,
                    descripcion=descripcion,
                    mapeos=self.mappings
                )
                message = "Plantilla actualizada correctamente"
            else:
                # Crear nueva plantilla
                response = api_client.crear_plantilla(
                    proyecto_id=self.proyecto['id'],
                    nombre=nombre,
                    descripcion=descripcion,
                    archivo_docx=str(self.docx_path),
                    mapeos_json=json.dumps(self.mappings)
                )
                message = "Plantilla creada correctamente"
            
            QMessageBox.information(self, "Éxito", message)
            self.template_saved.emit()
            self.close()
            
        except APIError as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la plantilla: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error inesperado: {str(e)}")
    
    def update_status(self, message):
        """Actualizar barra de estado"""
        self.status_bar.showMessage(message)
    
    def closeEvent(self, event):
        """Manejar cierre de ventana"""
        reply = QMessageBox.question(
            self,
            "Confirmar salida",
            "¿Estás seguro de salir del editor?\n\nLos cambios no guardados se perderán.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()