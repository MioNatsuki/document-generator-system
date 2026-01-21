 # Vista de gestión de plantillas
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressDialog, QApplication, QInputDialog, QMenu, QToolBar,
    QStatusBar, QMainWindow, QSplitter, QFrame, QGroupBox,
    QTextEdit, QLineEdit, QComboBox, QCheckBox, QSpinBox,
    QFileDialog, QDialog, QDialogButtonBox, QFormLayout,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QFont, QIcon, QColor, QPixmap
import json
import os

from config import config
from styles import styles
from utils.api_client import api_client, APIError
from widgets.template_editor import TemplateEditor


class TemplatesView(QWidget):
    """Vista de gestión de plantillas"""
    
    def __init__(self, proyecto, user_info):
        super().__init__()
        self.proyecto = proyecto
        self.user_info = user_info
        self.plantillas = []
        
        self.init_ui()
        self.load_templates()
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel(f"📄 Plantillas - {self.proyecto['nombre']}")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {config.COLORS['primary']};")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Botón de nueva plantilla (solo para roles con permisos)
        if self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
            self.new_btn = QPushButton("➕ Nueva Plantilla")
            self.new_btn.setStyleSheet(styles.get_main_style())
            self.new_btn.clicked.connect(self.new_template)
            header_layout.addWidget(self.new_btn)
            
            self.refresh_btn = QPushButton("🔄 Refrescar")
            self.refresh_btn.setStyleSheet(styles.get_main_style())
            self.refresh_btn.clicked.connect(self.load_templates)
            header_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Tabla de plantillas
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Descripción", "Creada", "Estado", "Acciones"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        
        layout.addWidget(self.table, 1)  # Stretch
        
        # Status label
        self.status_label = QLabel("Cargando plantillas...")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
    def load_templates(self):
        """Cargar plantillas desde la API"""
        try:
            response = api_client.listar_plantillas(self.proyecto['id'])
            self.plantillas = response.get('items', [])
            
            self.table.setRowCount(len(self.plantillas))
            
            for row, plantilla in enumerate(self.plantillas):
                # ID
                id_item = QTableWidgetItem(str(plantilla.get('id', '')))
                id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 0, id_item)
                
                # Nombre
                name_item = QTableWidgetItem(plantilla.get('nombre', ''))
                self.table.setItem(row, 1, name_item)
                
                # Descripción
                desc_item = QTableWidgetItem(plantilla.get('descripcion', ''))
                self.table.setItem(row, 2, desc_item)
                
                # Fecha de creación
                created = plantilla.get('created_at', '')
                if created:
                    created_item = QTableWidgetItem(created[:10])
                else:
                    created_item = QTableWidgetItem('')
                created_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 3, created_item)
                
                # Estado (basado en validación de tamaño)
                configuracion = plantilla.get('configuracion', {})
                mapeos = configuracion.get('mapeos', [])
                placeholders = configuracion.get('placeholders_detectados', [])
                
                if mapeos and placeholders and len(mapeos) >= len(placeholders):
                    estado = "✅ Configurada"
                    estado_color = QColor("#28a745")
                elif mapeos:
                    estado = "⚠️ Parcial"
                    estado_color = QColor("#ffc107")
                else:
                    estado = "❌ Sin configurar"
                    estado_color = QColor("#dc3545")
                
                estado_item = QTableWidgetItem(estado)
                estado_item.setForeground(estado_color)
                estado_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 4, estado_item)
                
                # Acciones
                actions_widget = QWidget()
                actions_layout = QHBoxLayout()
                actions_layout.setContentsMargins(5, 5, 5, 5)
                actions_layout.setSpacing(5)
                
                # Botón de vista previa (todos los roles)
                preview_btn = QPushButton("👁️")
                preview_btn.setStyleSheet("padding: 2px 6px; font-size: 12px;")
                preview_btn.setToolTip("Vista previa")
                preview_btn.clicked.connect(lambda checked, p=plantilla: self.preview_template(p))
                actions_layout.addWidget(preview_btn)
                
                # Solo roles con permisos pueden editar/eliminar
                if self.user_info['rol'] in ['SUPERADMIN', 'ANALISTA']:
                    edit_btn = QPushButton("✏️")
                    edit_btn.setStyleSheet("padding: 2px 6px; font-size: 12px;")
                    edit_btn.setToolTip("Editar plantilla")
                    edit_btn.clicked.connect(lambda checked, p=plantilla: self.edit_template(p))
                    
                    delete_btn = QPushButton("🗑️")
                    delete_btn.setStyleSheet("""
                        QPushButton {
                            padding: 2px 6px;
                            font-size: 12px;
                            background-color: #dc3545;
                            color: white;
                            border: 1px solid #dc3545;
                        }
                        QPushButton:hover {
                            background-color: #c82333;
                            border-color: #bd2130;
                        }
                    """)
                    delete_btn.setToolTip("Eliminar plantilla")
                    delete_btn.clicked.connect(lambda checked, p=plantilla: self.delete_template(p))
                    
                    duplicate_btn = QPushButton("📋")
                    duplicate_btn.setStyleSheet("padding: 2px 6px; font-size: 12px;")
                    duplicate_btn.setToolTip("Duplicar plantilla")
                    duplicate_btn.clicked.connect(lambda checked, p=plantilla: self.duplicate_template(p))
                    
                    actions_layout.addWidget(edit_btn)
                    actions_layout.addWidget(duplicate_btn)
                    actions_layout.addWidget(delete_btn)
                
                actions_layout.addStretch()
                actions_widget.setLayout(actions_layout)
                self.table.setCellWidget(row, 5, actions_widget)
            
            self.table.resizeColumnsToContents()
            self.status_label.setText(f"✓ {len(self.plantillas)} plantillas cargadas")
            
        except APIError as e:
            QMessageBox.critical(self, "Error", f"No se pudieron cargar las plantillas: {str(e)}")
            self.status_label.setText("❌ Error cargando plantillas")
            
    def new_template(self):
        """Crear nueva plantilla"""
        try:
            # Verificar si hay estructura de padrón disponible
            response = api_client.obtener_estructura_padron(self.proyecto['id'])
            estructura = response.get('estructura', [])
            
            if not estructura:
                QMessageBox.warning(
                    self,
                    "Advertencia",
                    "El proyecto no tiene estructura de padrón definida.\n"
                    "Por favor, configura el padrón antes de crear plantillas."
                )
                return
            
            # Abrir editor de plantillas
            from ..widgets.template_editor import TemplateEditor
            editor = TemplateEditor(self.proyecto, None)
            editor.template_saved.connect(self.on_template_saved)
            editor.show()
            
        except APIError as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear la plantilla: {str(e)}")
            
    def edit_template(self, plantilla):
        """Editar plantilla existente"""
        try:
            from ..widgets.template_editor import TemplateEditor
            editor = TemplateEditor(self.proyecto, plantilla)
            editor.template_saved.connect(self.on_template_saved)
            editor.show()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo editar la plantilla: {str(e)}")
            
    def delete_template(self, plantilla):
        """Eliminar plantilla"""
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Estás seguro de eliminar la plantilla '{plantilla['nombre']}'?\n\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                api_client.eliminar_plantilla(plantilla['id'])
                QMessageBox.information(
                    self,
                    "Plantilla eliminada",
                    f"La plantilla '{plantilla['nombre']}' ha sido eliminada."
                )
                self.load_templates()
            except APIError as e:
                QMessageBox.critical(self, "Error", f"No se pudo eliminar la plantilla: {str(e)}")
                
    def duplicate_template(self, plantilla):
        """Duplicar plantilla"""
        new_name, ok = QInputDialog.getText(
            self,
            "Duplicar plantilla",
            "Ingresa el nombre para la nueva plantilla:",
            text=f"Copia de {plantilla['nombre']}"
        )
        
        if ok and new_name.strip():
            try:
                # Obtener detalles completos de la plantilla
                plantilla_detalles = api_client.obtener_plantilla(plantilla['id'])
                
                # Crear nueva plantilla con los mismos datos
                response = api_client.crear_plantilla(
                    proyecto_id=self.proyecto['id'],
                    nombre=new_name.strip(),
                    descripcion=f"Copia de {plantilla['nombre']}",
                    archivo_docx=None,  # Se necesitaría duplicar el archivo
                    mapeos_json=json.dumps(plantilla_detalles.get('configuracion', {}).get('mapeos', []))
                )
                
                QMessageBox.information(
                    self,
                    "Plantilla duplicada",
                    f"La plantilla ha sido duplicada como '{new_name}'."
                )
                self.load_templates()
                
            except APIError as e:
                QMessageBox.critical(self, "Error", f"No se pudo duplicar la plantilla: {str(e)}")
                
    def preview_template(self, plantilla):
        """Ver vista previa de la plantilla"""
        try:
            # Descargar PDF de vista previa
            response = api_client.obtener_preview_plantilla(plantilla['id'])
            
            # Guardar temporalmente
            import tempfile
            import webbrowser
            import base64
            
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"preview_{plantilla['nombre']}.pdf")
            
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            
            # Abrir con el visor predeterminado
            webbrowser.open(f"file://{temp_path}")
            
        except APIError as e:
            QMessageBox.critical(self, "Error", f"No se pudo obtener la vista previa: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error inesperado: {str(e)}")
            
    def on_template_saved(self):
        """Manejar guardado de plantilla"""
        self.load_templates()
        QMessageBox.information(
            self,
            "Éxito",
            "Plantilla guardada correctamente."
        )