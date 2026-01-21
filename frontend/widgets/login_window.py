# Ventana de login 
# Ventana de login 
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFrame, QMessageBox, 
    QApplication, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QIcon
import sys
import os

from config import config
from styles import styles
from utils.api_client import api_client, APIError


class LoginWindow(QWidget):
    """Ventana de inicio de sesión"""
    
    login_successful = pyqtSignal(dict)  # Señal emitida al iniciar sesión exitosamente
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} - Login")
        self.setObjectName("LoginWindow")
        self.setFixedSize(500, 450)
        self.setStyleSheet(styles.get_login_style())
        
        # Intentar conexión automática
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.check_backend_connection)
        self.connection_timer.start(2000)  # Intentar cada 2 segundos
        
        self.init_ui()
        self.attempting_connection = False
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)
        
        # Frame principal
        frame = QFrame()
        frame.setObjectName("LoginFrame")
        frame_layout = QVBoxLayout()
        frame_layout.setContentsMargins(30, 30, 30, 30)
        frame_layout.setSpacing(20)
        
        # Título
        title_label = QLabel(config.APP_NAME)
        title_label.setObjectName("TitleLabel")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        subtitle_label = QLabel("Sistema de Generación Automatizada de PDFs")
        subtitle_label.setObjectName("SubtitleLabel")
        
        # Estado de conexión
        self.connection_label = QLabel("Conectando con el servidor...")
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_label.setStyleSheet("color: #666; font-style: italic;")
        
        # Campos de entrada (inicialmente deshabilitados)
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)
        
        # Usuario
        user_layout = QVBoxLayout()
        user_label = QLabel("Usuario o Email:")
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Ingresa tu usuario o email")
        self.user_input.setEnabled(False)
        user_layout.addWidget(user_label)
        user_layout.addWidget(self.user_input)
        
        # Contraseña
        pass_layout = QVBoxLayout()
        pass_label = QLabel("Contraseña:")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Ingresa tu contraseña")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setEnabled(False)
        pass_layout.addWidget(pass_label)
        pass_layout.addWidget(self.pass_input)
        
        # Recordar sesión (placeholder para futura implementación)
        remember_layout = QHBoxLayout()
        self.remember_check = QCheckBox("Recordar sesión")
        self.remember_check.setEnabled(False)
        remember_layout.addWidget(self.remember_check)
        remember_layout.addStretch()
        
        # Botón de login
        self.login_button = QPushButton("Iniciar Sesión")
        self.login_button.setStyleSheet(styles.get_main_style())
        self.login_button.clicked.connect(self.handle_login)
        self.login_button.setEnabled(False)
        
        # Conectar Enter para login
        self.user_input.returnPressed.connect(self.handle_login)
        self.pass_input.returnPressed.connect(self.handle_login)
        
        # Agregar al layout
        form_layout.addLayout(user_layout)
        form_layout.addLayout(pass_layout)
        form_layout.addLayout(remember_layout)
        form_layout.addWidget(self.login_button)
        
        # Información de versión
        version_label = QLabel(f"v{config.APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #999; font-size: 10px;")
        
        # Agregar al frame
        frame_layout.addWidget(title_label)
        frame_layout.addWidget(subtitle_label)
        frame_layout.addWidget(self.connection_label)
        frame_layout.addStretch(1)
        frame_layout.addLayout(form_layout)
        frame_layout.addStretch(1)
        frame_layout.addWidget(version_label)
        
        frame.setLayout(frame_layout)
        
        # Agregar frame al layout principal
        main_layout.addWidget(frame)
        self.setLayout(main_layout)
        
    def check_backend_connection(self):
        """Verificar conexión con el backend"""
        if self.attempting_connection:
            return
            
        self.attempting_connection = True
        
        try:
            # Intentar conectar
            if api_client.test_connection():
                self.connection_label.setText("Conectado al servidor")
                self.connection_label.setStyleSheet("color: #28a745; font-weight: bold;")
                
                # Habilitar controles
                self.user_input.setEnabled(True)
                self.pass_input.setEnabled(True)
                self.remember_check.setEnabled(True)
                self.login_button.setEnabled(True)
                
                # Detener el timer
                self.connection_timer.stop()
            else:
                self.connection_label.setText("No se pudo conectar al servidor")
                self.connection_label.setStyleSheet("color: #dc3545;")
                
        except Exception as e:
            self.connection_label.setText("Error de conexión")
            self.connection_label.setStyleSheet("color: #dc3545;")
            
        finally:
            self.attempting_connection = False
            
    def handle_login(self):
        """Manejar intento de login"""
        username = self.user_input.text().strip()
        password = self.pass_input.text().strip()
        
        if not username:
            self.show_error("Campo requerido", "Por favor, ingresa tu usuario o email.")
            self.user_input.setFocus()
            return
            
        if not password:
            self.show_error("Campo requerido", "Por favor, ingresa tu contraseña.")
            self.pass_input.setFocus()
            return
        
        # Deshabilitar controles durante login
        self.set_controls_enabled(False)
        self.login_button.setText("Iniciando sesión...")
        QApplication.processEvents()
        
        try:
            # Intentar login
            response = api_client.login(username, password)
            
            # Obtener información del usuario
            user_info = api_client.get_current_user()
            
            # Emitir señal de éxito
            self.login_successful.emit(user_info)
            
        except APIError as e:
            self.show_error("Error de inicio de sesión", str(e))
            self.pass_input.clear()
            self.set_controls_enabled(True)
            self.login_button.setText("Iniciar Sesión")
            
        except Exception as e:
            self.show_error("Error inesperado", f"Ocurrió un error inesperado: {str(e)}")
            self.set_controls_enabled(True)
            self.login_button.setText("Iniciar Sesión")
            
    def set_controls_enabled(self, enabled: bool):
        """Habilitar/deshabilitar controles"""
        self.user_input.setEnabled(enabled)
        self.pass_input.setEnabled(enabled)
        self.remember_check.setEnabled(enabled)
        self.login_button.setEnabled(enabled)
        
    def show_error(self, title: str, message: str):
        """Mostrar mensaje de error"""
        QMessageBox.critical(self, title, message)
        
    def clear_fields(self):
        """Limpiar campos del formulario"""
        self.user_input.clear()
        self.pass_input.clear()
        self.set_controls_enabled(True)
        self.login_button.setText("Iniciar Sesión")
        
    def closeEvent(self, event):
        """Manejar cierre de ventana"""
        self.connection_timer.stop()
        event.accept()