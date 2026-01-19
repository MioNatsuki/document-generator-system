# Aplicación principal PyQt6 
import sys
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPixmap, QFont, QColor
import logging
import traceback

from .config import config
from .styles import styles
from .widgets.login_window import LoginWindow
from .widgets.dashboard_window import DashboardWindow
from .utils.api_client import api_client, APIError


class PDFGeneratorApp:
    """Aplicación principal del sistema de generación de PDFs"""
    
    def __init__(self):
        # Crear aplicación
        self.app = QApplication(sys.argv)
        self.app.setApplicationName(config.APP_NAME)
        self.app.setApplicationVersion(config.APP_VERSION)
        
        # Configurar estilo global
        self.app.setStyleSheet(styles.get_main_style())
        
        # Configurar logging
        self.setup_logging()
        
        # Crear directorios necesarios
        config.ensure_directories()
        
        # Mostrar splash screen
        self.show_splash_screen()
        
        # Crear ventanas
        self.login_window = None
        self.dashboard_window = None
        
        # Timer para token
        self.token_timer = QTimer()
        self.token_timer.timeout.connect(self.validate_token)
        
        # Manejar excepciones no capturadas
        sys.excepthook = self.handle_exception
        
    def setup_logging(self):
        """Configurar sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/app.log'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        
    def show_splash_screen(self):
        """Mostrar splash screen de inicio"""
        # Crear pixmap para splash screen
        splash_pixmap = QPixmap(400, 300)
        splash_pixmap.fill(QColor(config.COLORS['color4']))
        
        # En una implementación real, cargarías una imagen
        # splash_pixmap = QPixmap("path/to/splash.png")
        
        self.splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint)
        
        # Configurar texto
        self.splash.showMessage(
            f"Inicializando {config.APP_NAME}...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor(config.COLORS['dark'])
        )
        
        self.splash.show()
        
        # Procesar eventos para mostrar splash
        self.app.processEvents()
        
        # Simular tiempo de carga
        QTimer.singleShot(1500, self.show_login)
        
    def show_login(self):
        """Mostrar ventana de login"""
        self.splash.close()
        
        self.login_window = LoginWindow()
        self.login_window.login_successful.connect(self.on_login_success)
        self.login_window.show()
        
        # Iniciar timer de validación de token
        self.token_timer.start(60000)  # Cada minuto
        
        # Probar conexión con backend
        self.test_backend_connection()
        
    def test_backend_connection(self):
        """Probar conexión con backend"""
        try:
            if api_client.test_connection():
                self.logger.info("✅ Conectado al backend")
            else:
                self.logger.warning("❌ No se pudo conectar al backend")
        except Exception as e:
            self.logger.error(f"Error probando conexión: {str(e)}")
            
    def on_login_success(self, user_info):
        """Manejar inicio de sesión exitoso"""
        self.logger.info(f"Login exitoso para usuario: {user_info['username']}")
        
        if self.login_window:
            self.login_window.hide()
            
        self.dashboard_window = DashboardWindow(user_info)
        self.dashboard_window.show()
        
    def validate_token(self):
        """Validar token periódicamente"""
        if api_client.token:
            try:
                api_client.validate_token()
                self.logger.debug("Token válido")
            except APIError as e:
                if e.status_code == 401:  # Token expirado
                    self.logger.warning("Token expirado, cerrando sesión")
                    self.handle_token_expired()
            except Exception as e:
                self.logger.error(f"Error validando token: {str(e)}")
                
    def handle_token_expired(self):
        """Manejar token expirado"""
        if self.dashboard_window:
            self.dashboard_window.close()
            self.dashboard_window = None
            
        if self.login_window:
            self.login_window.clear_fields()
            self.login_window.show()
            
        QMessageBox.warning(
            None,
            "Sesión expirada",
            "Tu sesión ha expirado. Por favor, inicia sesión nuevamente."
        )
        
    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """Manejar excepciones no capturadas"""
        self.logger.critical(
            "Excepción no capturada",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        
        # Mostrar mensaje de error amigable
        error_msg = f"""
        <h3>❌ Error inesperado</h3>
        <p>Ha ocurrido un error inesperado en la aplicación.</p>
        <p><b>Error:</b> {str(exc_value)}</p>
        <p style="color: #666; font-size: 10px;">
        Para más detalles, consulta el archivo de logs.
        </p>
        """
        
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Error")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(error_msg)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.exec()
        
    def run(self):
        """Ejecutar aplicación"""
        return self.app.exec()


def main():
    """Función principal"""
    try:
        app = PDFGeneratorApp()
        sys.exit(app.run())
    except Exception as e:
        print(f"Error fatal: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()