"""
Asistente para procesamiento de emisiones
"""
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QDateEdit,
    QFileDialog, QMessageBox, QProgressBar, QTextEdit,
    QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QSpinBox, QListWidget, QListWidgetItem,
    QWidget, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QColor
import csv
import tempfile
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from ..config import config
from ..styles import styles
from ..utils.api_client import api_client, APIError


class EmissionWorker(QThread):
    """Trabajador para procesamiento de emisión en segundo plano"""
    
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, proyecto_id, plantilla_id, documento, pmo, fecha_emision, csv_path):
        super().__init__()
        self.proyecto_id = proyecto_id
        self.plantilla_id = plantilla_id
        self.documento = documento
        self.pmo = pmo
        self.fecha_emision = fecha_emision
        self.csv_path = csv_path
    
    def run(self):
        try:
            self.progress.emit(0, "Iniciando procesamiento...")
            
            # Aquí iría la llamada a la API para procesar la emisión
            # Por ahora, simulamos el procesamiento
            import time
            
            for i in range(1, 101):
                time.sleep(0.05)  # Simular trabajo
                self.progress.emit(i, f"Procesando registro {i} de 100...")
            
            self.finished.emit({
                'success': True,
                'message': 'Emisión procesada exitosamente',
                'pdfs_generados': 95,
                'errores': 5
            })
            
        except Exception as e:
            self.error.emit(str(e))


class EmissionWizard(QWizard):
    """Asistente para procesamiento de emisiones"""
    
    emission_completed = pyqtSignal(dict)
    
    def __init__(self, proyecto, parent=None):
        super().__init__(parent)
        self.proyecto = proyecto
        self.csv_path = None
        self.plantillas = []
        
        self.setWindowTitle(f"Emisión de Documentos - {proyecto['nombre']}")
        self.setFixedSize(800, 600)
        self.setStyleSheet(styles.get_main_style())
        
        # Configurar wizard
        self.setOption(QWizard.WizardOption.IndependentPages, False)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        
        # Crear páginas
        self.addPage(ConfigPage())
        self.addPage(FilePage())
        self.addPage(ValidationPage())
        self.addPage(ProcessingPage())
        
        # Configurar botones
        self.setButtonText(QWizard.WizardButton.NextButton, "Siguiente")
        self.setButtonText(QWizard.WizardButton.BackButton, "Atrás")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Iniciar Emisión")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancelar")
        
        # Cargar plantillas
        self.load_templates()
    
    def load_templates(self):
        """Cargar plantillas del proyecto"""
        try:
            response = api_client.listar_plantillas(self.proyecto['id'])
            self.plantillas = response.get('items', [])
        except APIError as e:
            QMessageBox.warning(self, "Advertencia", f"No se pudieron cargar las plantillas: {str(e)}")
    
    def validate_config(self):
        """Validar configuración antes de procesar"""
        config_page = self.page(0)
        
        if not config_page.plantilla_combo.currentText():
            return False, "Selecciona una plantilla"
        
        if not config_page.documento_combo.currentText():
            return False, "Selecciona un tipo de documento"
        
        if not config_page.pmo_input.text():
            return False, "Ingresa un PMO válido"
        
        return True, ""
    
    def start_emission(self):
        """Iniciar procesamiento de emisión"""
        config_page = self.page(0)
        file_page = self.page(1)
        
        if not self.csv_path:
            QMessageBox.warning(self, "Advertencia", "Debes seleccionar un archivo CSV")
            return
        
        # Validar configuración
        valido, mensaje = self.validate_config()
        if not valido:
            QMessageBox.warning(self, "Validación", mensaje)
            return
        
        # Obtener parámetros
        plantilla_nombre = config_page.plantilla_combo.currentText()
        plantilla_id = next((p['id'] for p in self.plantillas if p['nombre'] == plantilla_nombre), 0)
        
        documento = config_page.documento_combo.currentText()
        pmo = config_page.pmo_input.text()
        fecha_emision = config_page.fecha_date.date().toPyDate()
        
        # Crear y ejecutar trabajador
        self.worker = EmissionWorker(
            proyecto_id=self.proyecto['id'],
            plantilla_id=plantilla_id,
            documento=documento,
            pmo=pmo,
            fecha_emision=fecha_emision,
            csv_path=self.csv_path
        )
        
        processing_page = self.page(3)
        processing_page.start_processing(self.worker)
        
        self.worker.finished.connect(self.on_emission_finished)
        self.worker.error.connect(self.on_emission_error)
        
        self.worker.start()
    
    def on_emission_finished(self, resultados):
        """Manejar finalización de emisión"""
        processing_page = self.page(3)
        processing_page.on_processing_finished(resultados)
        
        self.emission_completed.emit(resultados)
    
    def on_emission_error(self, error_message):
        """Manejar error en emisión"""
        processing_page = self.page(3)
        processing_page.on_processing_error(error_message)


class ConfigPage(QWizardPage):
    """Página 1: Configuración de emisión"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Configuración de Emisión")
        self.setSubTitle("Configura los parámetros para la generación de documentos")
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Formulario de configuración
        form_group = QGroupBox("Parámetros de Emisión")
        form_layout = QFormLayout()
        
        # Plantilla
        self.plantilla_combo = QComboBox()
        form_layout.addRow("Plantilla:*", self.plantilla_combo)
        
        # Tipo de documento
        self.documento_combo = QComboBox()
        self.documento_combo.addItems(["Notificación (N)", "Apercibimiento (A)", "Embargo (E)", "Carta Invitación (CI)"])
        form_layout.addRow("Tipo de documento:*", self.documento_combo)
        
        # PMO
        self.pmo_input = QLineEdit()
        self.pmo_input.setPlaceholderText("Ej: PMO 1")
        form_layout.addRow("PMO:*", self.pmo_input)
        
        # Fecha de emisión
        self.fecha_date = QDateEdit()
        self.fecha_date.setDate(QDate.currentDate())
        self.fecha_date.setCalendarPopup(True)
        form_layout.addRow("Fecha de emisión:*", self.fecha_date)
        
        # Opciones adicionales
        options_group = QGroupBox("Opciones Adicionales")
        options_layout = QVBoxLayout()
        
        self.validar_check = QCheckBox("Validar cuentas antes de procesar")
        self.validar_check.setChecked(True)
        
        self.reporte_check = QCheckBox("Generar reporte de cuentas no encontradas")
        self.reporte_check.setChecked(True)
        
        options_layout.addWidget(self.validar_check)
        options_layout.addWidget(self.reporte_check)
        options_group.setLayout(options_layout)
        
        form_group.setLayout(form_layout)
        
        # Agregar al layout
        layout.addWidget(form_group)
        layout.addWidget(options_group)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def initializePage(self):
        """Inicializar página con datos del wizard"""
        wizard = self.wizard()
        if wizard:
            self.plantilla_combo.clear()
            for plantilla in wizard.plantillas:
                self.plantilla_combo.addItem(plantilla['nombre'])


class FilePage(QWizardPage):
    """Página 2: Selección de archivo CSV"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Archivo CSV de Emisión")
        self.setSubTitle("Selecciona el archivo CSV con las cuentas a procesar")
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Instrucciones
        instructions = QLabel(
            "Selecciona el archivo CSV que contiene las cuentas a procesar.\n\n"
            "<b>Requisitos del CSV:</b>\n"
            "• Debe contener las columnas 'cuenta' y 'orden_impresion'\n"
            "• Codificación: UTF-8\n"
            "• Separador: Coma (,)\n"
            "• Tamaño máximo: 50 MB\n\n"
            "Las cuentas serán validadas contra el padrón del proyecto."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 10px; background-color: #f8f9fa; border-radius: 5px;")
        
        # Botón de selección
        self.select_btn = QPushButton("📁 Seleccionar archivo CSV")
        self.select_btn.setStyleSheet(styles.get_main_style())
        self.select_btn.clicked.connect(self.select_csv)
        
        # Información del archivo
        self.file_label = QLabel("No se ha seleccionado archivo")
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("color: #666; padding: 10px; border: 1px dashed #ccc; border-radius: 5px;")
        
        # Vista previa (opcional)
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(2)
        self.preview_table.setHorizontalHeaderLabels(["Cuenta", "Orden Impresión"])
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setMaximumHeight(150)
        self.preview_table.hide()
        
        # Agregar al layout
        layout.addWidget(instructions)
        layout.addWidget(self.select_btn)
        layout.addWidget(self.file_label)
        layout.addWidget(self.preview_table)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def select_csv(self):
        """Seleccionar archivo CSV"""
        file_path = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo CSV",
            str(Path.home()),
            "Archivos CSV (*.csv);;Todos los archivos (*)"
        )[0]
        
        if file_path:
            try:
                # Validar archivo
                if not file_path.lower().endswith('.csv'):
                    QMessageBox.warning(self, "Archivo inválido", "El archivo debe ser CSV")
                    return
                
                # Leer primeras líneas para vista previa
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    
                    # Verificar columnas requeridas
                    if 'cuenta' not in reader.fieldnames or 'orden_impresion' not in reader.fieldnames:
                        QMessageBox.warning(
                            self,
                            "Columnas faltantes",
                            "El CSV debe contener las columnas 'cuenta' y 'orden_impresion'"
                        )
                        return
                    
                    # Contar registros
                    lines = f.readlines()
                    total_lines = len(lines) - 1  # Excluir header
                    
                    # Mostrar información
                    self.file_label.setText(f"📄 {Path(file_path).name}\n"
                                          f"📊 {total_lines} registros\n"
                                          f"🗂️ Columnas: {', '.join(reader.fieldnames[:5])}{'...' if len(reader.fieldnames) > 5 else ''}")
                    
                    # Mostrar vista previa
                    self.show_preview(file_path)
                    
                    # Guardar en wizard
                    wizard = self.wizard()
                    if wizard:
                        wizard.csv_path = file_path
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo leer el archivo: {str(e)}")
    
    def show_preview(self, file_path):
        """Mostrar vista previa del CSV"""
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                rows = list(reader)[:5]  # Solo primeras 5 filas
                
                self.preview_table.setRowCount(len(rows))
                
                for i, row in enumerate(rows):
                    self.preview_table.setItem(i, 0, QTableWidgetItem(row.get('cuenta', '')))
                    self.preview_table.setItem(i, 1, QTableWidgetItem(row.get('orden_impresion', '')))
                
                self.preview_table.resizeColumnsToContents()
                self.preview_table.show()
                
        except Exception as e:
            logger.warning(f"Error mostrando vista previa: {str(e)}")
    
    def validatePage(self):
        """Validar que se haya seleccionado un archivo"""
        wizard = self.wizard()
        if not wizard or not wizard.csv_path:
            QMessageBox.warning(self, "Archivo requerido", "Debes seleccionar un archivo CSV para continuar.")
            return False
        
        return True


class ValidationPage(QWizardPage):
    """Página 3: Validación de cuentas"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Validación de Cuentas")
        self.setSubTitle("Verifica las cuentas que no se encuentran en el padrón")
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Botón de validación
        self.validate_btn = QPushButton("🔍 Validar cuentas ahora")
        self.validate_btn.setStyleSheet(styles.get_main_style())
        self.validate_btn.clicked.connect(self.validate_accounts)
        
        # Resultados de validación
        self.results_label = QLabel("Presiona 'Validar cuentas ahora' para verificar las cuentas del CSV contra el padrón.")
        self.results_label.setWordWrap(True)
        self.results_label.setStyleSheet("padding: 15px; background-color: #f8f9fa; border-radius: 5px;")
        
        # Lista de cuentas no encontradas
        self.missing_list = QListWidget()
        self.missing_list.setMaximumHeight(200)
        self.missing_list.hide()
        
        # Advertencia
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        
        layout.addWidget(self.validate_btn)
        layout.addWidget(self.results_label)
        layout.addWidget(self.missing_list)
        layout.addWidget(self.warning_label)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def validate_accounts(self):
        """Validar cuentas contra el padrón"""
        wizard = self.wizard()
        if not wizard or not wizard.csv_path:
            QMessageBox.warning(self, "Datos faltantes", "Primero selecciona un archivo CSV.")
            return
        
        try:
            # Aquí iría la llamada a la API para preprocesar
            # Por ahora, simulamos la validación
            
            self.results_label.setText("Validando cuentas...")
            QApplication.processEvents()
            
            # Simular validación
            import time
            time.sleep(2)
            
            # Resultados simulados
            total = 100
            found = 85
            missing = 15
            
            missing_list = [f"CUENTA-{i:04d}" for i in range(1, missing + 1)]
            
            # Mostrar resultados
            self.results_label.setText(
                f"✅ Validación completada\n\n"
                f"• Total de cuentas en CSV: {total}\n"
                f"• Cuentas encontradas en padrón: {found}\n"
                f"• Cuentas no encontradas: {missing}\n"
                f"• Porcentaje de éxito: {(found/total*100):.1f}%"
            )
            
            # Mostrar cuentas no encontradas
            if missing > 0:
                self.missing_list.clear()
                for cuenta in missing_list:
                    item = QListWidgetItem(cuenta)
                    self.missing_list.addItem(item)
                
                self.missing_list.show()
                
                self.warning_label.setText(
                    f"⚠️ <b>Advertencia:</b> {missing} cuentas no se encontraron en el padrón.\n"
                    f"Estas cuentas serán omitidas durante el procesamiento."
                )
                self.warning_label.setStyleSheet("color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 5px;")
                self.warning_label.show()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error validando cuentas: {str(e)}")


class ProcessingPage(QWizardPage):
    """Página 4: Procesamiento de emisión"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Procesamiento de Emisión")
        self.setSubTitle("Generando documentos PDF...")
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Icono de procesamiento
        self.icon_label = QLabel("🔄")
        icon_font = QFont()
        icon_font.setPointSize(48)
        self.icon_label.setFont(icon_font)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Mensaje de estado
        self.status_label = QLabel("Listo para iniciar el procesamiento")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        
        # Detalles del progreso
        self.details_label = QLabel()
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.details_label.setStyleSheet("color: #666;")
        
        # Resultados
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(200)
        self.results_text.hide()
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.details_label)
        layout.addWidget(self.results_text)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def start_processing(self, worker):
        """Iniciar procesamiento"""
        self.icon_label.setText("🔄")
        self.status_label.setText("Procesando emisión...")
        self.progress_bar.setValue(0)
        self.details_label.setText("Iniciando...")
        
        # Conectar señales del trabajador
        worker.progress.connect(self.update_progress)
    
    def update_progress(self, value, message):
        """Actualizar progreso"""
        self.progress_bar.setValue(value)
        self.details_label.setText(message)
        
        if value >= 100:
            self.icon_label.setText("✅")
            self.status_label.setText("Procesamiento completado")
    
    def on_processing_finished(self, resultados):
        """Manejar finalización del procesamiento"""
        self.icon_label.setText("✅")
        self.status_label.setText("Emisión procesada exitosamente")
        self.progress_bar.setValue(100)
        
        # Mostrar resultados
        resultados_text = (
            f"📊 <b>Resumen de emisión:</b>\n\n"
            f"• PDFs generados: {resultados.get('pdfs_generados', 0)}\n"
            f"• Errores: {resultados.get('errores', 0)}\n"
            f"• Tiempo estimado: {resultados.get('tiempo_segundos', 0):.1f} segundos\n"
            f"• Velocidad: {resultados.get('pdfs_por_segundo', 0):.1f} PDFs/segundo\n\n"
            f"📁 <b>Archivos guardados en:</b>\n"
            f"{resultados.get('ruta_salida', '')}"
        )
        
        self.results_text.setHtml(resultados_text)
        self.results_text.show()
        
        self.details_label.setText("Haz clic en 'Finalizar' para cerrar el asistente.")
    
    def on_processing_error(self, error_message):
        """Manejar error en el procesamiento"""
        self.icon_label.setText("❌")
        self.status_label.setText("Error en el procesamiento")
        self.details_label.setText(f"Error: {error_message}")
        
        QMessageBox.critical(self, "Error", f"Error procesando emisión: {error_message}")