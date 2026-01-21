# Vista de proyectos 
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox,
    QFileDialog, QMessageBox, QCheckBox, QGroupBox, QSpinBox,
    QProgressDialog, QApplication, QRadioButton, QButtonGroup,
    QScrollArea, QFrame, QListWidget, QListWidgetItem, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
import csv
import pandas as pd
from pathlib import Path
import tempfile
import os

from config import config
from styles import styles
from utils.api_client import api_client, APIError
from utils.file_dialogs import FileDialog

class NewProjectWizard(QWizard):
    """Asistente para crear nuevo proyecto"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Nuevo Proyecto")
        self.setFixedSize(900, 700)
        self.setStyleSheet(styles.get_main_style())
        
        # Datos del proyecto
        self.project_name = ""
        self.project_description = ""
        self.csv_path = None
        self.csv_data = None
        self.csv_columns = []
        self.padron_columns = []
        self.upload_method = "create"  # "create" o "upload"
        
        # Configurar wizard
        self.setOption(QWizard.WizardOption.IndependentPages, False)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        self.setOption(QWizard.WizardOption.HaveFinishButtonOnEarlyPages, False)
        
        # Crear páginas
        self.addPage(WelcomePage())
        self.addPage(ProjectInfoPage())
        self.addPage(PadronConfigPage())
        self.addPage(PadronLoadPage())
        self.addPage(ConfirmationPage())
        
        # Configurar botones
        self.setButtonText(QWizard.WizardButton.NextButton, "Siguiente")
        self.setButtonText(QWizard.WizardButton.BackButton, "Atrás")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Crear Proyecto")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancelar")
        
        # Conectar señales
        self.currentIdChanged.connect(self.on_page_changed)
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self.create_project)
        
    def on_page_changed(self, page_id):
        """Manejar cambio de página"""
        if page_id == 2:  # Página de configuración de padrón
            if self.csv_data is not None:
                config_page = self.page(2)
                config_page.load_csv_data(self.csv_data, self.csv_columns)
                
    def create_project(self):
        """Crear proyecto final"""
        try:
            # Obtener información de las páginas
            info_page = self.page(1)
            config_page = self.page(2)
            load_page = self.page(3)
            
            self.project_name = info_page.nombre_input.text().strip()
            self.project_description = info_page.descripcion_input.toPlainText().strip()
            self.padron_columns = config_page.get_columns()
            
            # Validar datos
            if not self.project_name:
                raise ValueError("El nombre del proyecto es requerido")
                
            if not self.padron_columns:
                raise ValueError("Debes configurar al menos una columna para el padrón")
            
            # Preparar datos para API
            proyecto_data = {
                "proyecto": {
                    "nombre": self.project_name,
                    "descripcion": self.project_description,
                    "logo_url": None
                },
                "columnas_padron": self.padron_columns,
                "csv_data": None
            }
            
            # Si hay datos CSV, prepararlos
            if self.csv_data is not None and load_page.use_csv_data:
                # Guardar CSV temporalmente
                temp_csv = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8')
                self.csv_data.to_csv(temp_csv.name, index=False)
                temp_csv.close()
                
                try:
                    # Leer CSV como string para enviar
                    with open(temp_csv.name, 'r', encoding='utf-8') as f:
                        csv_content = f.read()
                    
                    # Agregar al request
                    proyecto_data["csv_data"] = csv_content
                    
                finally:
                    # Limpiar archivo temporal
                    os.unlink(temp_csv.name)
            
            # Mostrar progreso
            progress = QProgressDialog("Creando proyecto...", "Cancelar", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setValue(10)
            QApplication.processEvents()
            
            # Crear proyecto
            response = api_client.crear_proyecto(proyecto_data)
            
            progress.setValue(50)
            QApplication.processEvents()
            
            # Si tenemos un archivo CSV separado para carga
            if self.csv_path and load_page.use_csv_data and self.csv_data is None:
                # Cargar archivo CSV completo
                project_id = response["id"]
                
                progress.setLabelText("Cargando datos del padrón...")
                progress.setValue(70)
                QApplication.processEvents()
                
                upload_response = api_client.cargar_padron(
                    project_id,
                    self.csv_path,
                    merge=False
                )
                
                progress.setValue(100)
                QApplication.processEvents()
            
            progress.close()
            
            QMessageBox.information(
                self,
                "Proyecto creado",
                f"El proyecto '{self.project_name}' ha sido creado exitosamente.\n\n"
                f"Columnas configuradas: {len(self.padron_columns)}\n"
                f"Datos cargados: {'Sí' if (self.csv_data is not None or self.csv_path) and load_page.use_csv_data else 'No'}"
            )
            
            return True
            
        except ValueError as e:
            QMessageBox.critical(self, "Error de validación", str(e))
            return False
            
        except APIError as e:
            QMessageBox.critical(self, "Error de API", str(e))
            return False
            
        except Exception as e:
            QMessageBox.critical(self, "Error inesperado", f"No se pudo crear el proyecto: {str(e)}")
            return False


class WelcomePage(QWizardPage):
    """Página 1: Bienvenida"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Bienvenido al Asistente de Nuevo Proyecto")
        self.setSubTitle("Este asistente te guiará en la creación de un nuevo proyecto de generación de PDFs")
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Icono/título
        icon_label = QLabel("✨")
        icon_font = QFont()
        icon_font.setPointSize(48)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel("Nuevo Proyecto")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(f"color: {config.COLORS['primary']};")
        
        subtitle_label = QLabel(
            "Vas a crear un nuevo proyecto para la generación automatizada de PDFs.\n\n"
            "El proceso consta de 4 pasos:\n"
            "1. Información básica del proyecto\n"
            "2. Configuración de la estructura del padrón\n"
            "3. Carga inicial de datos\n"
            "4. Confirmación y creación\n\n"
            "Presiona 'Siguiente' para comenzar."
        )
        subtitle_label.setWordWrap(True)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Métodos de creación
        methods_group = QGroupBox("Método de creación")
        methods_layout = QVBoxLayout()
        
        self.method_create = QRadioButton("Crear desde cero")
        self.method_create.setChecked(True)
        self.method_create.toggled.connect(self.on_method_changed)
        
        self.method_upload = QRadioButton("Crear desde archivo CSV")
        self.method_upload.toggled.connect(self.on_method_changed)
        
        methods_layout.addWidget(self.method_create)
        methods_layout.addWidget(self.method_upload)
        methods_group.setLayout(methods_layout)
        
        # Agregar al layout
        layout.addStretch()
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addStretch()
        layout.addWidget(methods_group)
        layout.addStretch()
        
        self.setLayout(layout)
        
    def on_method_changed(self):
        """Manejar cambio de método de creación"""
        wizard = self.wizard()
        if wizard:
            if self.method_upload.isChecked():
                wizard.upload_method = "upload"
            else:
                wizard.upload_method = "create"


class ProjectInfoPage(QWizardPage):
    """Página 2: Información básica del proyecto"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Información del Proyecto")
        self.setSubTitle("Ingresa la información básica del nuevo proyecto")
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Nombre del proyecto
        nombre_group = QGroupBox("Nombre del proyecto")
        nombre_layout = QVBoxLayout()
        
        self.nombre_input = QLineEdit()
        self.nombre_input.setPlaceholderText("Ej: Proyecto Fiscalización 2024")
        self.nombre_input.textChanged.connect(self.on_nombre_changed)
        
        nombre_layout.addWidget(QLabel("Nombre:*"))
        nombre_layout.addWidget(self.nombre_input)
        nombre_group.setLayout(nombre_layout)
        
        # Descripción
        desc_group = QGroupBox("Descripción")
        desc_layout = QVBoxLayout()
        
        self.descripcion_input = QTextEdit()
        self.descripcion_input.setPlaceholderText("Describe el propósito de este proyecto...")
        self.descripcion_input.setMaximumHeight(100)
        
        desc_layout.addWidget(QLabel("Descripción (opcional):"))
        desc_layout.addWidget(self.descripcion_input)
        desc_group.setLayout(desc_layout)
        
        # Logo (placeholder)
        logo_group = QGroupBox("Logo del proyecto")
        logo_layout = QVBoxLayout()
        
        logo_label = QLabel("La funcionalidad de logo estará disponible en futuras versiones")
        logo_label.setStyleSheet("color: #666; font-style: italic;")
        
        logo_layout.addWidget(logo_label)
        logo_group.setLayout(logo_layout)
        
        # Si el método es "upload", mostrar opción de CSV
        self.csv_group = QGroupBox("Archivo CSV inicial")
        csv_layout = QVBoxLayout()
        
        csv_info = QLabel(
            "Puedes subir un archivo CSV para extraer automáticamente la estructura de columnas.\n"
            "El CSV debe contener al menos las columnas 'cuenta' y 'nombre'."
        )
        csv_info.setWordWrap(True)
        
        self.csv_button = QPushButton("Seleccionar archivo CSV")
        self.csv_button.setStyleSheet(styles.get_main_style())
        self.csv_button.clicked.connect(self.select_csv)
        
        self.csv_label = QLabel("No se ha seleccionado archivo")
        self.csv_label.setStyleSheet("color: #666;")
        self.csv_label.setWordWrap(True)
        
        csv_layout.addWidget(csv_info)
        csv_layout.addWidget(self.csv_button)
        csv_layout.addWidget(self.csv_label)
        self.csv_group.setLayout(csv_layout)
        
        # Agregar al layout
        layout.addWidget(nombre_group)
        layout.addWidget(desc_group)
        layout.addWidget(logo_group)
        
        # Solo mostrar grupo CSV si el método es "upload"
        wizard = self.wizard()
        if wizard and wizard.upload_method == "upload":
            layout.addWidget(self.csv_group)
        else:
            self.csv_group.hide()
        
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Registrar campo obligatorio
        self.registerField("nombre*", self.nombre_input)
        
    def select_csv(self):
        """Seleccionar archivo CSV"""
        file_path = FileDialog.open_csv_file(self)
        
        if file_path:
            self.csv_label.setText(f"📄 {Path(file_path).name}")
            
            try:
                # Leer CSV para preview y validación
                df = pd.read_csv(file_path, nrows=10)  # Solo primeras 10 filas
                
                # Guardar en el wizard
                wizard = self.wizard()
                if wizard:
                    wizard.csv_path = file_path
                    wizard.csv_data = df
                    wizard.csv_columns = list(df.columns)
                
                # Mostrar preview
                self.show_csv_preview(df)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo leer el CSV: {str(e)}")
                self.csv_label.setText("Error leyendo archivo")
                
    def show_csv_preview(self, df):
        """Mostrar preview del CSV"""
        preview_text = f"<b>Columnas detectadas ({len(df.columns)}):</b><br>"
        preview_text += ", ".join(df.columns.tolist())
        preview_text += f"<br><br><b>Primeras {len(df)} filas:</b><br>"
        preview_text += df.head().to_html(index=False)
        
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Preview del CSV")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(preview_text)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
        
    def on_nombre_changed(self, text):
        """Validar nombre del proyecto"""
        if len(text.strip()) < 3:
            self.nombre_input.setStyleSheet("border: 2px solid #dc3545;")
        else:
            self.nombre_input.setStyleSheet("")


class PadronConfigPage(QWizardPage):
    """Página 3: Configuración del padrón"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Configuración del Padrón")
        self.setSubTitle("Configura las columnas del padrón. Las columnas 'cuenta' y 'nombre' son obligatorias.")
        
        self.columnas = []
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Instrucciones
        instructions = QLabel(
            "Configura el tipo de dato y propiedades para cada columna del padrón.<br>"
            "<b>Nota:</b> La columna 'cuenta' debe ser única y será usada como identificador."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #555; padding: 10px; background-color: #f8f9fa; border-radius: 5px;")
        
        # Tabla de columnas
        self.columns_table = QTableWidget()
        self.columns_table.setColumnCount(6)
        self.columns_table.setHorizontalHeaderLabels([
            "Nombre", "Tipo", "Longitud", "Obligatorio", "Único", "Acciones"
        ])
        
        # Configurar headers
        header = self.columns_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        self.columns_table.verticalHeader().setVisible(False)
        self.columns_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.columns_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # Controles para agregar columnas
        controls_frame = QFrame()
        controls_layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Agregar columna")
        add_btn.setStyleSheet(styles.get_main_style())
        add_btn.clicked.connect(self.add_manual_column)
        
        import_btn = QPushButton("📁 Importar desde CSV")
        import_btn.setStyleSheet(styles.get_main_style())
        import_btn.clicked.connect(self.import_from_csv)
        
        clear_btn = QPushButton("🗑️ Limpiar todas")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {config.COLORS['danger']};
                color: white;
                border: 2px solid {config.COLORS['danger']};
            }}
        """)
        clear_btn.clicked.connect(self.clear_all_columns)
        
        controls_layout.addWidget(add_btn)
        controls_layout.addWidget(import_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(clear_btn)
        controls_frame.setLayout(controls_layout)
        
        # Validación
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        
        # Agregar al layout
        layout.addWidget(instructions)
        layout.addWidget(self.columns_table)
        layout.addWidget(controls_frame)
        layout.addWidget(self.validation_label)
        layout.addStretch()
        
        self.setLayout(layout)
        
    def load_csv_data(self, df, columns):
        """Cargar datos del CSV"""
        self.columns_table.setRowCount(len(columns))
        
        for row, column in enumerate(columns):
            # Nombre de columna (no editable para columnas del CSV)
            name_item = QTableWidgetItem(column)
            self.columns_table.setItem(row, 0, name_item)
            
            # Tipo de dato (inferir del CSV)
            if df.empty:
                tipo = "VARCHAR(255)"
            else:
                dtype = str(df[column].dtype)
                if 'int' in dtype:
                    tipo = "INT"
                elif 'float' in dtype:
                    tipo = "DECIMAL(10,2)"
                elif 'datetime' in dtype:
                    tipo = "DATE"
                else:
                    # Estimar longitud
                    if df[column].notna().any():
                        max_len = df[column].astype(str).str.len().max()
                        tipo = f"VARCHAR({min(max(50, max_len * 2), 255)})"
                    else:
                        tipo = "VARCHAR(255)"
            
            tipo_combo = QComboBox()
            tipo_combo.addItems([
                "VARCHAR(50)", "VARCHAR(100)", "VARCHAR(255)", "VARCHAR(500)",
                "INT", "BIGINT", "DECIMAL(10,2)", "DECIMAL(15,2)",
                "DATE", "TIMESTAMP", "TEXT", "BOOLEAN"
            ])
            
            # Extraer tipo base para seleccionar
            if '(' in tipo:
                tipo_base = tipo.split('(')[0]
                if tipo_base == "DECIMAL":
                    tipo_combo.setCurrentText("DECIMAL(10,2)")
                else:
                    tipo_combo.setCurrentText(tipo)
            else:
                tipo_combo.setCurrentText(tipo)
            
            self.columns_table.setCellWidget(row, 1, tipo_combo)
            
            # Longitud (para VARCHAR)
            length_spin = QSpinBox()
            length_spin.setRange(1, 5000)
            length_spin.setValue(255)
            length_spin.setEnabled("VARCHAR" in tipo)
            self.columns_table.setCellWidget(row, 2, length_spin)
            
            # Conectar cambio de tipo para habilitar/deshabilitar longitud
            tipo_combo.currentTextChanged.connect(
                lambda text, spin=length_spin: spin.setEnabled("VARCHAR" in text)
            )
            
            # Obligatorio
            obligatorio_check = QCheckBox()
            obligatorio_check.setChecked(column.lower() in ['cuenta', 'nombre'])
            self.columns_table.setCellWidget(row, 3, obligatorio_check)
            
            # Único
            unico_check = QCheckBox()
            unico_check.setChecked(column.lower() == 'cuenta')
            self.columns_table.setCellWidget(row, 4, unico_check)
            
            # Acciones
            actions_widget = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(2)
            
            delete_btn = QPushButton("🗑️")
            delete_btn.setStyleSheet("padding: 2px 6px; font-size: 12px;")
            delete_btn.clicked.connect(lambda checked, r=row: self.delete_column(r))
            delete_btn.setToolTip("Eliminar columna")
            
            actions_layout.addWidget(delete_btn)
            actions_layout.addStretch()
            
            actions_widget.setLayout(actions_layout)
            self.columns_table.setCellWidget(row, 5, actions_widget)
        
        # Validar
        self.validate_columns()
        
    def add_manual_column(self):
        """Agregar columna manualmente"""
        row = self.columns_table.rowCount()
        self.columns_table.insertRow(row)
        
        # Nombre de columna
        name_item = QTableWidgetItem("nueva_columna")
        self.columns_table.setItem(row, 0, name_item)
        
        # Tipo de dato
        tipo_combo = QComboBox()
        tipo_combo.addItems([
            "VARCHAR(50)", "VARCHAR(100)", "VARCHAR(255)", "VARCHAR(500)",
            "INT", "BIGINT", "DECIMAL(10,2)", "DECIMAL(15,2)",
            "DATE", "TIMESTAMP", "TEXT", "BOOLEAN"
        ])
        self.columns_table.setCellWidget(row, 1, tipo_combo)
        
        # Longitud
        length_spin = QSpinBox()
        length_spin.setRange(1, 5000)
        length_spin.setValue(255)
        length_spin.setEnabled(True)
        self.columns_table.setCellWidget(row, 2, length_spin)
        
        # Conectar cambio de tipo
        tipo_combo.currentTextChanged.connect(
            lambda text, spin=length_spin: spin.setEnabled("VARCHAR" in text)
        )
        
        # Obligatorio
        obligatorio_check = QCheckBox()
        self.columns_table.setCellWidget(row, 3, obligatorio_check)
        
        # Único
        unico_check = QCheckBox()
        self.columns_table.setCellWidget(row, 4, unico_check)
        
        # Acciones
        actions_widget = QWidget()
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(2)
        
        delete_btn = QPushButton("🗑️")
        delete_btn.setStyleSheet("padding: 2px 6px; font-size: 12px;")
        delete_btn.clicked.connect(lambda checked, r=row: self.delete_column(r))
        
        actions_layout.addWidget(delete_btn)
        actions_layout.addStretch()
        
        actions_widget.setLayout(actions_layout)
        self.columns_table.setCellWidget(row, 5, actions_widget)
        
        # Validar
        self.validate_columns()
        
    def import_from_csv(self):
        """Importar estructura desde CSV"""
        file_path = FileDialog.open_csv_file(self)
        
        if file_path:
            try:
                df = pd.read_csv(file_path, nrows=1)  # Solo headers
                columns = list(df.columns)
                
                # Agregar cada columna
                for column in columns:
                    row = self.columns_table.rowCount()
                    self.columns_table.insertRow(row)
                    
                    # Nombre
                    name_item = QTableWidgetItem(column)
                    self.columns_table.setItem(row, 0, name_item)
                    
                    # Tipo (predeterminado)
                    tipo_combo = QComboBox()
                    tipo_combo.addItems([
                        "VARCHAR(50)", "VARCHAR(100)", "VARCHAR(255)", "VARCHAR(500)",
                        "INT", "BIGINT", "DECIMAL(10,2)", "DECIMAL(15,2)",
                        "DATE", "TIMESTAMP", "TEXT", "BOOLEAN"
                    ])
                    tipo_combo.setCurrentText("VARCHAR(255)")
                    self.columns_table.setCellWidget(row, 1, tipo_combo)
                    
                    # Longitud
                    length_spin = QSpinBox()
                    length_spin.setRange(1, 5000)
                    length_spin.setValue(255)
                    length_spin.setEnabled(True)
                    self.columns_table.setCellWidget(row, 2, length_spin)
                    
                    # Obligatorio
                    obligatorio_check = QCheckBox()
                    obligatorio_check.setChecked(column.lower() in ['cuenta', 'nombre'])
                    self.columns_table.setCellWidget(row, 3, obligatorio_check)
                    
                    # Único
                    unico_check = QCheckBox()
                    unico_check.setChecked(column.lower() == 'cuenta')
                    self.columns_table.setCellWidget(row, 4, unico_check)
                    
                    # Acciones
                    actions_widget = QWidget()
                    actions_layout = QHBoxLayout()
                    actions_layout.setContentsMargins(0, 0, 0, 0)
                    
                    delete_btn = QPushButton("🗑️")
                    delete_btn.setStyleSheet("padding: 2px 6px; font-size: 12px;")
                    delete_btn.clicked.connect(lambda checked, r=row: self.delete_column(r))
                    
                    actions_layout.addWidget(delete_btn)
                    actions_layout.addStretch()
                    
                    actions_widget.setLayout(actions_layout)
                    self.columns_table.setCellWidget(row, 5, actions_widget)
                
                self.validate_columns()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo importar el CSV: {str(e)}")
                
    def delete_column(self, row):
        """Eliminar columna"""
        self.columns_table.removeRow(row)
        self.validate_columns()
        
    def clear_all_columns(self):
        """Limpiar todas las columnas"""
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "¿Estás seguro de eliminar todas las columnas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.columns_table.setRowCount(0)
            self.validate_columns()
            
    def validate_columns(self):
        """Validar columnas"""
        has_cuenta = False
        has_nombre = False
        errors = []
        
        # Verificar nombres únicos
        nombres = []
        for row in range(self.columns_table.rowCount()):
            item = self.columns_table.item(row, 0)
            if item:
                nombre = item.text().strip().lower()
                if nombre:
                    nombres.append(nombre)
        
        # Verificar duplicados
        if len(nombres) != len(set(nombres)):
            errors.append("Hay nombres de columnas duplicados")
        
        # Buscar 'cuenta' y 'nombre'
        for row in range(self.columns_table.rowCount()):
            item = self.columns_table.item(row, 0)
            if item:
                nombre = item.text().strip().lower()
                if nombre == 'cuenta':
                    has_cuenta = True
                    # Verificar que cuenta sea única
                    check = self.columns_table.cellWidget(row, 4)
                    if check and not check.isChecked():
                        errors.append("La columna 'cuenta' debe ser única")
                elif nombre == 'nombre':
                    has_nombre = True
        
        if not has_cuenta:
            errors.append("Debe existir la columna 'cuenta'")
        if not has_nombre:
            errors.append("Debe existir la columna 'nombre'")
        
        # Actualizar mensaje de validación
        if errors:
            self.validation_label.setText(" ❌ " + "; ".join(errors))
            self.setComplete(False)
        else:
            self.validation_label.setText(" ✅ Estructura válida")
            self.setComplete(True)
            
    def setComplete(self, is_complete):
        """Establecer si la página está completa"""
        self.complete = is_complete
        self.completeChanged.emit()
        
    def isComplete(self):
        """Verificar si la página está completa"""
        return getattr(self, 'complete', False)
        
    def get_columns(self):
        """Obtener lista de columnas configuradas"""
        columns = []
        
        for row in range(self.columns_table.rowCount()):
            name_item = self.columns_table.item(row, 0)
            if not name_item:
                continue
                
            nombre = name_item.text().strip()
            if not nombre:
                continue
            
            tipo_widget = self.columns_table.cellWidget(row, 1)
            length_widget = self.columns_table.cellWidget(row, 2)
            obligatorio_widget = self.columns_table.cellWidget(row, 3)
            unico_widget = self.columns_table.cellWidget(row, 4)
            
            if not all([tipo_widget, length_widget, obligatorio_widget, unico_widget]):
                continue
            
            tipo = tipo_widget.currentText()
            
            # Si es VARCHAR, usar longitud del spinbox
            if "VARCHAR" in tipo and length_widget.isEnabled():
                tipo = f"VARCHAR({length_widget.value()})"
            
            columns.append({
                "nombre": nombre,
                "tipo": tipo,
                "es_obligatorio": obligatorio_widget.isChecked(),
                "es_unico": unico_widget.isChecked()
            })
        
        return columns


class PadronLoadPage(QWizardPage):
    """Página 4: Carga inicial del padrón"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Carga del Padrón")
        self.setSubTitle("Configura la carga inicial de datos para el padrón")
        
        self.use_csv_data = True
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Opciones de carga
        options_group = QGroupBox("Opciones de carga inicial")
        options_layout = QVBoxLayout()
        
        self.load_data_radio = QRadioButton("Cargar datos iniciales desde CSV")
        self.load_data_radio.setChecked(True)
        self.load_data_radio.toggled.connect(self.on_load_option_changed)
        
        self.empty_data_radio = QRadioButton("Crear padrón vacío (sin datos iniciales)")
        self.empty_data_radio.toggled.connect(self.on_load_option_changed)
        
        options_layout.addWidget(self.load_data_radio)
        options_layout.addWidget(self.empty_data_radio)
        options_group.setLayout(options_layout)
        
        # Panel de carga de CSV (inicialmente visible)
        self.csv_panel = QFrame()
        csv_layout = QVBoxLayout()
        csv_layout.setSpacing(15)
        
        csv_info = QLabel(
            "Selecciona el archivo CSV con los datos iniciales para el padrón.<br>"
            "<b>Importante:</b> El CSV debe coincidir con la estructura configurada."
        )
        csv_info.setWordWrap(True)
        
        self.csv_select_btn = QPushButton("Seleccionar archivo CSV")
        self.csv_select_btn.setStyleSheet(styles.get_main_style())
        self.csv_select_btn.clicked.connect(self.select_csv_file)
        
        self.csv_info_label = QLabel("No se ha seleccionado archivo")
        self.csv_info_label.setStyleSheet("color: #666;")
        self.csv_info_label.setWordWrap(True)
        
        # Opciones de carga
        load_options = QGroupBox("Opciones de carga")
        load_options_layout = QVBoxLayout()
        
        self.merge_check = QCheckBox("Fusionar con datos existentes (si aplica)")
        self.merge_check.setChecked(True)
        self.merge_check.setToolTip("Si hay datos existentes, se actualizarán los registros coincidentes")
        
        self.validate_check = QCheckBox("Validar estructura antes de cargar")
        self.validate_check.setChecked(True)
        
        load_options_layout.addWidget(self.merge_check)
        load_options_layout.addWidget(self.validate_check)
        load_options.setLayout(load_options_layout)
        
        csv_layout.addWidget(csv_info)
        csv_layout.addWidget(self.csv_select_btn)
        csv_layout.addWidget(self.csv_info_label)
        csv_layout.addWidget(load_options)
        
        self.csv_panel.setLayout(csv_layout)
        
        # Panel para padrón vacío (inicialmente oculto)
        self.empty_panel = QFrame()
        empty_layout = QVBoxLayout()
        
        empty_info = QLabel(
            "El padrón se creará sin datos iniciales.<br>"
            "Podrás cargar datos posteriormente desde la ventana del proyecto."
        )
        empty_info.setWordWrap(True)
        empty_info.setStyleSheet("color: #666; padding: 20px;")
        
        empty_layout.addWidget(empty_info)
        empty_layout.addStretch()
        self.empty_panel.setLayout(empty_layout)
        self.empty_panel.hide()
        
        # Agregar al layout principal
        layout.addWidget(options_group)
        layout.addWidget(self.csv_panel)
        layout.addWidget(self.empty_panel)
        layout.addStretch()
        
        self.setLayout(layout)
        
    def on_load_option_changed(self):
        """Manejar cambio de opción de carga"""
        wizard = self.wizard()
        if not wizard:
            return
        
        if self.load_data_radio.isChecked():
            self.use_csv_data = True
            self.csv_panel.show()
            self.empty_panel.hide()
            
            # Si ya hay un CSV cargado desde página anterior, mostrarlo
            if wizard.csv_path:
                self.csv_info_label.setText(f"📄 {Path(wizard.csv_path).name} (cargado anteriormente)")
                self.csv_select_btn.setText("Cambiar archivo CSV")
        else:
            self.use_csv_data = False
            self.csv_panel.hide()
            self.empty_panel.show()
            
    def select_csv_file(self):
        """Seleccionar archivo CSV para carga"""
        file_path = FileDialog.open_csv_file(self)
        
        if file_path:
            wizard = self.wizard()
            if wizard:
                wizard.csv_path = file_path
                wizard.csv_data = None  # Limpiar datos de preview
                
                self.csv_info_label.setText(f"📄 {Path(file_path).name}")
                self.csv_select_btn.setText("Cambiar archivo CSV")
                
                # Validar tamaño
                from ..utils.file_dialogs import FileDialog
                valido, mensaje = FileDialog.validate_file_size(file_path, 50)
                if not valido:
                    QMessageBox.warning(self, "Archivo grande", mensaje)
    
    def initializePage(self):
        """Inicializar página"""
        wizard = self.wizard()
        if wizard and wizard.csv_path:
            self.csv_info_label.setText(f"📄 {Path(wizard.csv_path).name} (cargado anteriormente)")
            self.csv_select_btn.setText("Cambiar archivo CSV")


class ConfirmationPage(QWizardPage):
    """Página 5: Confirmación"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Confirmación")
        self.setSubTitle("Revisa la configuración del proyecto antes de crearlo")
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Resumen
        summary_group = QGroupBox("Resumen del proyecto")
        summary_layout = QVBoxLayout()
        
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("padding: 15px; background-color: #f8f9fa; border-radius: 5px;")
        
        summary_layout.addWidget(self.summary_label)
        summary_group.setLayout(summary_layout)
        
        # Advertencias
        warnings_group = QGroupBox("Información importante")
        warnings_layout = QVBoxLayout()
        
        warnings = QLabel(
            "⚠️ <b>Una vez creado el proyecto:</b><br><br>"
            "• La estructura del padrón no podrá modificarse fácilmente<br>"
            "• Los datos iniciales se cargarán según la configuración<br>"
            "• Se creará una tabla dinámica en la base de datos<br>"
            "• El proyecto estará disponible para los usuarios asignados"
        )
        warnings.setWordWrap(True)
        warnings.setStyleSheet("color: #856404; background-color: #fff3cd; padding: 15px; border-radius: 5px;")
        
        warnings_layout.addWidget(warnings)
        warnings_group.setLayout(warnings_layout)
        
        # Agregar al layout
        layout.addWidget(summary_group)
        layout.addWidget(warnings_group)
        layout.addStretch()
        
        self.setLayout(layout)
        
    def initializePage(self):
        """Inicializar página con datos del proyecto"""
        wizard = self.wizard()
        if not wizard:
            return
        
        # Construir resumen
        summary = f"""
        <h3>Proyecto: {wizard.project_name}</h3>
        
        <b>Descripción:</b><br>
        {wizard.project_description or 'Sin descripción'}<br><br>
        
        <b>Estructura del padrón:</b><br>
        • Total de columnas: {len(wizard.padron_columns)}<br>
        • Columnas obligatorias: {sum(1 for c in wizard.padron_columns if c['es_obligatorio'])}<br>
        • Columnas únicas: {sum(1 for c in wizard.padron_columns if c['es_unico'])}<br><br>
        """
        
        # Agregar columnas
        if wizard.padron_columns:
            summary += "<b>Columnas configuradas:</b><br>"
            for col in wizard.padron_columns:
                obligatorio = "✓" if col['es_obligatorio'] else ""
                unico = "🔑" if col['es_unico'] else ""
                summary += f"• {col['nombre']} ({col['tipo']}) {obligatorio} {unico}<br>"
            summary += "<br>"
        
        # Agregar información de carga
        load_page = wizard.page(3)
        if load_page and load_page.use_csv_data:
            if wizard.csv_path:
                summary += f"<b>Datos iniciales:</b> Desde archivo '{Path(wizard.csv_path).name}'<br>"
            elif wizard.csv_data is not None:
                summary += f"<b>Datos iniciales:</b> Desde CSV cargado anteriormente ({len(wizard.csv_data)} filas)<br>"
        else:
            summary += "<b>Datos iniciales:</b> Padrón vacío<br>"
        
        self.summary_label.setText(summary)