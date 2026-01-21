# Asistente para creación de plantillas
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QFileDialog, QMessageBox,
    QApplication, QGroupBox, QFormLayout, QListWidget, QListWidgetItem,
    QComboBox, QSpinBox, QCheckBox, QDoubleSpinBox, QRadioButton,
    QButtonGroup, QTableWidget, QTableWidgetItem, QHeaderView, QProgressDialog,
    QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QColor
import json
import tempfile
from pathlib import Path

from config import config
from styles import styles
from utils.api_client import api_client, APIError
from utils.file_dialogs import FileDialog


class TemplateWizard(QWizard):
    """Asistente para crear nueva plantilla"""
    
    template_created = pyqtSignal(dict)
    
    def __init__(self, proyecto, parent=None):
        super().__init__(parent)
        self.proyecto = proyecto
        self.docx_path = None
        self.placeholders = []
        self.mappings = []
        self.padron_fields = []
        
        self.setWindowTitle(f"Nueva Plantilla - {proyecto['nombre']}")
        self.setFixedSize(900, 700)
        self.setStyleSheet(styles.get_main_style())
        
        # Configurar wizard
        self.setOption(QWizard.WizardOption.IndependentPages, False)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        
        # Crear páginas
        self.addPage(WelcomePage())
        self.addPage(DocumentPage())
        self.addPage(MappingPage())
        self.addPage(PreviewPage())
        self.addPage(ConfirmationPage())
        
        # Configurar botones
        self.setButtonText(QWizard.WizardButton.NextButton, "Siguiente")
        self.setButtonText(QWizard.WizardButton.BackButton, "Atrás")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Crear Plantilla")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancelar")
        
        # Conectar señales
        self.currentIdChanged.connect(self.on_page_changed)
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self.create_template)
    
    def on_page_changed(self, page_id):
        """Manejar cambio de página"""
        if page_id == 2:  # Página de mapeo
            mapping_page = self.page(2)
            mapping_page.load_data(self.placeholders, self.padron_fields)
        
        elif page_id == 3:  # Página de vista previa
            preview_page = self.page(3)
            preview_page.load_preview(self.mappings)
    
    def create_template(self):
        """Crear la plantilla final"""
        try:
            # Obtener información de las páginas
            doc_page = self.page(1)
            mapping_page = self.page(2)
            
            nombre = doc_page.nombre_input.text().strip()
            descripcion = doc_page.descripcion_input.toPlainText().strip()
            
            if not nombre:
                raise ValueError("El nombre de la plantilla es requerido")
            
            if not self.docx_path:
                raise ValueError("Debes cargar un documento DOCX")
            
            # Validar mapeos
            if not self.mappings:
                reply = QMessageBox.question(
                    self,
                    "Confirmar",
                    "No hay mapeos configurados. ¿Deseas crear la plantilla sin mapeos?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return False
            
            # Mostrar progreso
            progress = QProgressDialog("Creando plantilla...", "Cancelar", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setValue(10)
            QApplication.processEvents()
            
            # Crear plantilla
            response = api_client.crear_plantilla(
                proyecto_id=self.proyecto['id'],
                nombre=nombre,
                descripcion=descripcion,
                archivo_docx=str(self.docx_path),
                mapeos_json=json.dumps(self.mappings)
            )
            
            progress.setValue(100)
            progress.close()
            
            QMessageBox.information(
                self,
                "Plantilla creada",
                f"La plantilla '{nombre}' ha sido creada exitosamente.\n\n"
                f"Placeholders detectados: {len(self.placeholders)}\n"
                f"Mapeos configurados: {len(self.mappings)}"
            )
            
            self.template_created.emit(response)
            return True
            
        except ValueError as e:
            QMessageBox.critical(self, "Error de validación", str(e))
            return False
        except APIError as e:
            QMessageBox.critical(self, "Error de API", str(e))
            return False
        except Exception as e:
            QMessageBox.critical(self, "Error inesperado", f"No se pudo crear la plantilla: {str(e)}")
            return False


class WelcomePage(QWizardPage):
    """Página 1: Bienvenida"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Nueva Plantilla")
        self.setSubTitle("Este asistente te guiará en la creación de una nueva plantilla de documentos")
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Icono/título
        icon_label = QLabel("📄")
        icon_font = QFont()
        icon_font.setPointSize(48)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel("Nueva Plantilla de Documentos")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(f"color: {config.COLORS['primary']};")
        
        subtitle_label = QLabel(
            "Vas a crear una nueva plantilla para la generación automática de PDFs.\n\n"
            "El proceso consta de 4 pasos:\n"
            "1. Información básica y carga del documento\n"
            "2. Mapeo de placeholders con campos del padrón\n"
            "3. Vista previa y validación\n"
            "4. Confirmación y creación\n\n"
            "<b>Importante:</b> El documento debe tener tamaño México Oficio (21.59cm x 34.01cm)"
        )
        subtitle_label.setWordWrap(True)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Agregar al layout
        layout.addStretch()
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addStretch()
        
        self.setLayout(layout)


class DocumentPage(QWizardPage):
    """Página 2: Documento e información"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Documento Base")
        self.setSubTitle("Carga el documento DOCX y proporciona información básica")
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Información de la plantilla
        info_group = QGroupBox("📋 Información de la Plantilla")
        info_layout = QFormLayout()
        
        self.nombre_input = QLineEdit()
        self.nombre_input.setPlaceholderText("Ej: Notificación de Pago")
        self.nombre_input.textChanged.connect(self.on_nombre_changed)
        
        self.descripcion_input = QTextEdit()
        self.descripcion_input.setPlaceholderText("Describe el propósito de esta plantilla...")
        self.descripcion_input.setMaximumHeight(100)
        
        info_layout.addRow("Nombre:*", self.nombre_input)
        info_layout.addRow("Descripción:", self.descripcion_input)
        info_group.setLayout(info_layout)
        
        # Carga de documento
        doc_group = QGroupBox("📄 Documento Base")
        doc_layout = QVBoxLayout()
        
        doc_info = QLabel(
            "Carga el documento DOCX que servirá como plantilla.\n"
            "<b>Requisitos:</b>\n"
            "• Tamaño: México Oficio (21.59cm x 34.01cm)\n"
            "• Formatos: DOCX (Word 2007+)\n"
            "• Tamaño máximo: 10MB\n"
            "• Debe contener placeholders entre {{ }}"
        )
        doc_info.setWordWrap(True)
        
        self.doc_button = QPushButton("Seleccionar archivo DOCX")
        self.doc_button.setStyleSheet(styles.get_main_style())
        self.doc_button.clicked.connect(self.select_document)
        
        self.doc_label = QLabel("No se ha seleccionado archivo")
        self.doc_label.setStyleSheet("color: #666;")
        self.doc_label.setWordWrap(True)
        
        self.placeholders_label = QLabel("Placeholders detectados: Ninguno")
        self.placeholders_label.setStyleSheet("color: #666; font-style: italic;")
        
        doc_layout.addWidget(doc_info)
        doc_layout.addWidget(self.doc_button)
        doc_layout.addWidget(self.doc_label)
        doc_layout.addWidget(self.placeholders_label)
        doc_group.setLayout(doc_layout)
        
        # Validación de tamaño
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #dc3545;")
        
        # Agregar al layout
        layout.addWidget(info_group)
        layout.addWidget(doc_group)
        layout.addWidget(self.validation_label)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Registrar campo obligatorio
        self.registerField("nombre*", self.nombre_input)
    
    def select_document(self):
        """Seleccionar documento DOCX"""
        file_path = FileDialog.open_docx_file(self)
        
        if file_path:
            self.doc_label.setText(f"📄 {Path(file_path).name}")
            
            # Validar tamaño
            valido, mensaje = FileDialog.validate_file_size(file_path, 10)
            if not valido:
                QMessageBox.warning(self, "Archivo grande", mensaje)
                return
            
            # Guardar en el wizard
            wizard = self.wizard()
            if wizard:
                wizard.docx_path = Path(file_path)
                
                # Simular extracción de placeholders
                wizard.placeholders = [
                    "nombre", "cuenta", "direccion", "monto", "fecha",
                    "referencia", "observaciones", "codigo_barras"
                ]
                
                self.placeholders_label.setText(f"Placeholders detectados: {len(wizard.placeholders)}")
                
                # Validar tamaño de página (simulado)
                self.validation_label.setText("✅ Documento válido (simulación)")
    
    def on_nombre_changed(self, text):
        """Validar nombre"""
        if len(text.strip()) < 3:
            self.nombre_input.setStyleSheet("border: 2px solid #dc3545;")
        else:
            self.nombre_input.setStyleSheet("")
    
    def validatePage(self):
        """Validar página"""
        wizard = self.wizard()
        if not wizard or not wizard.docx_path:
            QMessageBox.warning(self, "Documento requerido", "Debes cargar un documento DOCX para continuar.")
            return False
        
        if not self.nombre_input.text().strip():
            QMessageBox.warning(self, "Nombre requerido", "El nombre de la plantilla es obligatorio.")
            return False
        
        return True


class MappingPage(QWizardPage):
    """Página 3: Mapeo de placeholders"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Mapeo de Placeholders")
        self.setSubTitle("Asocia cada placeholder del documento con un campo del padrón")
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Instrucciones
        instructions = QLabel(
            "Asocia cada placeholder del documento con un campo del padrón.\n"
            "Arrastra y suelta o usa los botones para crear asociaciones."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 10px; background-color: #f8f9fa; border-radius: 5px;")
        
        # Panel dividido
        split_layout = QHBoxLayout()
        
        # Lista de placeholders
        left_group = QGroupBox("🔍 Placeholders del Documento")
        left_layout = QVBoxLayout()
        
        self.placeholders_list = QListWidget()
        self.placeholders_list.setAlternatingRowColors(True)
        
        left_layout.addWidget(self.placeholders_list)
        left_group.setLayout(left_layout)
        
        # Lista de campos del padrón
        right_group = QGroupBox("🗃️ Campos del Padrón")
        right_layout = QVBoxLayout()
        
        self.fields_list = QListWidget()
        self.fields_list.setAlternatingRowColors(True)
        
        right_layout.addWidget(self.fields_list)
        right_group.setLayout(right_layout)
        
        split_layout.addWidget(left_group)
        split_layout.addWidget(right_group)
        
        # Controles de mapeo
        controls_group = QGroupBox("🗺️ Mapeos Configurados")
        controls_layout = QVBoxLayout()
        
        self.mappings_table = QTableWidget()
        self.mappings_table.setColumnCount(3)
        self.mappings_table.setHorizontalHeaderLabels(["Placeholder", "Campo", "Acciones"])
        
        header = self.mappings_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        self.mappings_table.verticalHeader().setVisible(False)
        self.mappings_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        controls_layout.addWidget(self.mappings_table)
        controls_group.setLayout(controls_layout)
        
        # Agregar al layout
        layout.addWidget(instructions)
        layout.addLayout(split_layout, 1)  # Stretch
        layout.addWidget(controls_group)
        
        self.setLayout(layout)
    
    def load_data(self, placeholders, padron_fields):
        """Cargar datos en las listas"""
        self.placeholders_list.clear()
        self.fields_list.clear()
        
        for placeholder in placeholders:
            item = QListWidgetItem(f"{{{{{placeholder}}}}}")
            item.setData(Qt.ItemDataRole.UserRole, placeholder)
            self.placeholders_list.addItem(item)
        
        for field in padron_fields:
            item = QListWidgetItem(field)
            item.setData(Qt.ItemDataRole.UserRole, field)
            self.fields_list.addItem(item)
        
        # Actualizar tabla de mapeos
        wizard = self.wizard()
        if wizard:
            self.update_mappings_table(wizard.mappings)
    
    def update_mappings_table(self, mappings):
        """Actualizar tabla de mapeos"""
        self.mappings_table.setRowCount(len(mappings))
        
        for row, mapping in enumerate(mappings):
            placeholder = mapping.get('campo_padron', '')
            field = mapping.get('campo_padron', '')  # En este contexto es lo mismo
            
            self.mappings_table.setItem(row, 0, QTableWidgetItem(placeholder))
            self.mappings_table.setItem(row, 1, QTableWidgetItem(field))
            
            # Botón para eliminar
            delete_btn = QPushButton("🗑️")
            delete_btn.setStyleSheet("padding: 2px 6px;")
            delete_btn.clicked.connect(lambda checked, r=row: self.delete_mapping(r))
            
            widget = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(delete_btn)
            widget.setLayout(layout)
            
            self.mappings_table.setCellWidget(row, 2, widget)
    
    def delete_mapping(self, row):
        """Eliminar mapeo"""
        wizard = self.wizard()
        if wizard and 0 <= row < len(wizard.mappings):
            del wizard.mappings[row]
            self.update_mappings_table(wizard.mappings)
    
    def validatePage(self):
        """Validar página"""
        wizard = self.wizard()
        if not wizard:
            return False
        
        # Verificar si hay placeholders no mapeados
        mapeados = {m.get('campo_padron') for m in wizard.mappings}
        no_mapeados = [p for p in wizard.placeholders if p not in mapeados]
        
        if no_mapeados:
            reply = QMessageBox.question(
                self,
                "Placeholders no mapeados",
                f"Hay {len(no_mapeados)} placeholders sin mapear:\n{', '.join(no_mapeados)}\n\n¿Deseas continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            return reply == QMessageBox.StandardButton.Yes
        
        return True


class PreviewPage(QWizardPage):
    """Página 4: Vista previa"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Vista Previa")
        self.setSubTitle("Revisa la configuración de la plantilla antes de crearla")
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Resumen
        summary_group = QGroupBox("📋 Resumen de la Plantilla")
        summary_layout = QVBoxLayout()
        
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("padding: 15px; background-color: #f8f9fa; border-radius: 5px;")
        
        summary_layout.addWidget(self.summary_label)
        summary_group.setLayout(summary_layout)
        
        # Validación
        validation_group = QGroupBox("✅ Validación")
        validation_layout = QVBoxLayout()
        
        self.validation_label = QLabel("No se ha validado la plantilla")
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("padding: 15px; background-color: #fff3cd; border-radius: 5px; color: #856404;")
        
        validate_btn = QPushButton("🔍 Validar plantilla")
        validate_btn.setStyleSheet(styles.get_main_style())
        validate_btn.clicked.connect(self.validate_template)
        
        validation_layout.addWidget(self.validation_label)
        validation_layout.addWidget(validate_btn)
        validation_group.setLayout(validation_layout)
        
        # Agregar al layout
        layout.addWidget(summary_group, 1)  # Stretch
        layout.addWidget(validation_group)
        
        self.setLayout(layout)
    
    def load_preview(self, mappings):
        """Cargar vista previa"""
        wizard = self.wizard()
        if not wizard:
            return
        
        # Construir resumen
        summary = f"""
        <h3>Plantilla: {wizard.page(1).nombre_input.text()}</h3>
        
        <b>Documento base:</b><br>
        {wizard.docx_path.name if wizard.docx_path else 'No cargado'}<br><br>
        
        <b>Placeholders detectados:</b><br>
        • Total: {len(wizard.placeholders)}<br>
        • Lista: {', '.join(wizard.placeholders[:5])}{'...' if len(wizard.placeholders) > 5 else ''}<br><br>
        
        <b>Mapeos configurados:</b><br>
        • Total: {len(mappings)}<br>
        """
        
        if mappings:
            summary += "<b>Detalle de mapeos:</b><br>"
            for i, mapping in enumerate(mappings[:10], 1):
                campo = mapping.get('campo_padron', '')
                x = mapping.get('x', 0)
                y = mapping.get('y', 0)
                summary += f"{i}. {campo} → Posición: ({x:.1f}, {y:.1f})<br>"
            
            if len(mappings) > 10:
                summary += f"... y {len(mappings) - 10} más<br>"
        
        self.summary_label.setText(summary)
    
    def validate_template(self):
        """Validar plantilla"""
        wizard = self.wizard()
        if not wizard:
            return
        
        errors = []
        warnings = []
        
        # Validaciones básicas
        if not wizard.docx_path:
            errors.append("No se ha cargado documento DOCX")
        
        if not wizard.placeholders:
            warnings.append("No se detectaron placeholders en el documento")
        
        # Validar mapeos
        mapeados = {m.get('campo_padron') for m in wizard.mappings}
        for placeholder in wizard.placeholders:
            if placeholder not in mapeados:
                warnings.append(f"Placeholder '{placeholder}' no está mapeado")
        
        for mapping in wizard.mappings:
            campo = mapping.get('campo_padron')
            if campo not in wizard.placeholders:
                warnings.append(f"Campo mapeado '{campo}' no existe en el documento")
        
        # Mostrar resultados
        if errors:
            self.validation_label.setText(
                f"<b style='color: #dc3545;'>❌ Errores encontrados:</b><br>"
                f"{'<br>'.join(errors)}"
            )
        elif warnings:
            self.validation_label.setText(
                f"<b style='color: #ffc107;'>⚠️ Advertencias:</b><br>"
                f"{'<br>'.join(warnings[:5])}"
            )
        else:
            self.validation_label.setText(
                f"<b style='color: #28a745;'>✅ Plantilla válida</b><br>"
                f"La plantilla pasa todas las validaciones"
            )


class ConfirmationPage(QWizardPage):
    """Página 5: Confirmación"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Confirmación")
        self.setSubTitle("Revisa la configuración antes de crear la plantilla")
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Mensaje de confirmación
        message = QLabel(
            "<h3>¿Estás listo para crear la plantilla?</h3>"
            "<p>La plantilla será creada con la siguiente configuración:</p>"
            "<ul>"
            "<li>Se creará una nueva entrada en la base de datos</li>"
            "<li>El documento DOCX será almacenado en el servidor</li>"
            "<li>Los mapeos configurados serán guardados</li>"
            "<li>La plantilla estará disponible para generar PDFs</li>"
            "</ul>"
            "<p><b>Nota:</b> Una vez creada, podrás editarla desde la ventana de plantillas.</p>"
        )
        message.setWordWrap(True)
        
        # Advertencias
        warning = QLabel(
            "⚠️ <b>Verifica que:</b><br>"
            "• El documento tenga el tamaño correcto (México Oficio)<br>"
            "• Todos los placeholders importantes estén mapeados<br>"
            "• Los nombres de campos sean correctos<br>"
            "• No haya conflictos en los mapeos"
        )
        warning.setStyleSheet("color: #856404; background-color: #fff3cd; padding: 15px; border-radius: 5px;")
        warning.setWordWrap(True)
        
        layout.addWidget(message)
        layout.addWidget(warning)
        layout.addStretch()
        
        self.setLayout(layout)