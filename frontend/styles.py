# Estilos y paleta de colores 
from config import config


class Styles:
    """Clase para gestionar estilos de la aplicación"""
    
    @staticmethod
    def get_main_style() -> str:
        """Estilo principal de la aplicación"""
        return f"""
        /* Estilos generales */
        QMainWindow, QWidget {{
            background-color: {config.COLORS['bg_light']};
            font-family: '{config.FONTS['main']}', {', '.join(config.FONTS['fallback'])};
            font-size: {config.FONT_SIZES['base']};
            color: {config.COLORS['text_dark']};
        }}
        
        /* Botones */
        QPushButton {{
            background-color: {config.COLORS['color4']};
            color: {config.COLORS['dark']};
            border: 2px solid {config.COLORS['color4']};
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: bold;
            min-height: 32px;
        }}
        
        QPushButton:hover {{
            background-color: {config.COLORS['color5']};
            border-color: {config.COLORS['color5']};
        }}
        
        QPushButton:pressed {{
            background-color: {config.COLORS['color3']};
            border-color: {config.COLORS['color3']};
        }}
        
        QPushButton:disabled {{
            background-color: #cccccc;
            border-color: #aaaaaa;
            color: #666666;
        }}
        
        /* Botones especiales */
        QPushButton.primary {{
            background-color: {config.COLORS['primary']};
            border-color: {config.COLORS['primary']};
            color: white;
        }}
        
        QPushButton.success {{
            background-color: {config.COLORS['success']};
            border-color: {config.COLORS['success']};
            color: white;
        }}
        
        QPushButton.warning {{
            background-color: {config.COLORS['warning']};
            border-color: {config.COLORS['warning']};
            color: white;
        }}
        
        QPushButton.danger {{
            background-color: {config.COLORS['danger']};
            border-color: {config.COLORS['danger']};
            color: white;
        }}
        
        /* Campos de entrada */
        QLineEdit, QTextEdit, QComboBox {{
            background-color: white;
            border: 2px solid {config.COLORS['color4']};
            border-radius: 6px;
            padding: 6px 8px;
            selection-background-color: {config.COLORS['color4']};
        }}
        
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border-color: {config.COLORS['color5']};
        }}
        
        QLineEdit[error="true"] {{
            border-color: {config.COLORS['danger']};
            background-color: #fff5f5;
        }}
        
        /* Labels */
        QLabel {{
            color: {config.COLORS['text_dark']};
        }}
        
        QLabel.title {{
            font-size: {config.FONT_SIZES['2xl']};
            font-weight: bold;
            color: {config.COLORS['primary']};
        }}
        
        QLabel.subtitle {{
            font-size: {config.FONT_SIZES['lg']};
            color: {config.COLORS['secondary']};
        }}
        
        /* Group boxes */
        QGroupBox {{
            font-weight: bold;
            border: 2px solid {config.COLORS['color2']};
            border-radius: 10px;
            margin-top: 10px;
            padding-top: 15px;
            background-color: white;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 10px 0 10px;
            color: {config.COLORS['primary']};
        }}
        
        /* Tablas */
        QTableWidget {{
            background-color: white;
            alternate-background-color: {config.COLORS['color1']}20;
            selection-background-color: {config.COLORS['color4']}60;
            gridline-color: {config.COLORS['color4']}40;
            border: 1px solid {config.COLORS['color4']}40;
            border-radius: 6px;
        }}
        
        QHeaderView::section {{
            background-color: {config.COLORS['color4']};
            color: {config.COLORS['dark']};
            padding: 8px;
            border: 1px solid {config.COLORS['color4']}80;
            font-weight: bold;
        }}
        
        /* Tabs */
        QTabWidget::pane {{
            border: 2px solid {config.COLORS['color2']};
            background-color: white;
            border-radius: 8px;
        }}
        
        QTabBar::tab {{
            background-color: {config.COLORS['color2']};
            color: {config.COLORS['dark']};
            padding: 10px 20px;
            margin-right: 3px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-weight: bold;
        }}
        
        QTabBar::tab:selected {{
            background-color: {config.COLORS['color3']};
            color: {config.COLORS['dark']};
        }}
        
        QTabBar::tab:hover:!selected {{
            background-color: {config.COLORS['color1']};
        }}
        
        /* Progress bars */
        QProgressBar {{
            border: 2px solid {config.COLORS['color4']};
            border-radius: 6px;
            text-align: center;
            background-color: white;
        }}
        
        QProgressBar::chunk {{
            background-color: {config.COLORS['color3']};
            border-radius: 4px;
        }}
        
        /* Scrollbars */
        QScrollBar:vertical {{
            background-color: {config.COLORS['color1']}20;
            width: 14px;
            border-radius: 7px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {config.COLORS['color4']};
            border-radius: 7px;
            min-height: 30px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {config.COLORS['color5']};
        }}
        
        /* Menús */
        QMenuBar {{
            background-color: {config.COLORS['color4']};
            color: {config.COLORS['dark']};
        }}
        
        QMenuBar::item:selected {{
            background-color: {config.COLORS['color5']};
        }}
        
        QMenu {{
            background-color: white;
            border: 2px solid {config.COLORS['color4']};
            border-radius: 6px;
        }}
        
        QMenu::item:selected {{
            background-color: {config.COLORS['color4']};
        }}
        
        /* Toolbars */
        QToolBar {{
            background-color: {config.COLORS['color3']};
            border: 1px solid {config.COLORS['color2']};
            spacing: 5px;
            padding: 5px;
        }}
        
        /* Status bar */
        QStatusBar {{
            background-color: {config.COLORS['color4']};
            color: {config.COLORS['dark']};
        }}
        
        /* Frames decorativos */
        QFrame.decorative {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {config.COLORS['color1']}, 
                stop:0.3 {config.COLORS['color2']}, 
                stop:0.6 {config.COLORS['color3']}, 
                stop:1 {config.COLORS['color4']});
            border-radius: 12px;
            border: 2px solid {config.COLORS['color5']};
        }}
        
        /* Tooltips */
        QToolTip {{
            background-color: white;
            color: {config.COLORS['dark']};
            border: 2px solid {config.COLORS['color4']};
            border-radius: 6px;
            padding: 8px;
        }}
        """
    
    @staticmethod
    def get_login_style() -> str:
        """Estilo específico para la ventana de login"""
        return f"""
        QWidget#LoginWindow {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {config.COLORS['color1']}, 
                stop:0.3 {config.COLORS['color2']}, 
                stop:0.6 {config.COLORS['color3']}, 
                stop:1 {config.COLORS['color4']});
        }}
        
        QFrame#LoginFrame {{
            background-color: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            border: 3px solid {config.COLORS['color5']};
        }}
        
        QLabel#TitleLabel {{
            font-size: {config.FONT_SIZES['3xl']};
            font-weight: bold;
            color: {config.COLORS['color5']};
            qproperty-alignment: AlignCenter;
        }}
        
        QLabel#SubtitleLabel {{
            font-size: {config.FONT_SIZES['lg']};
            color: {config.COLORS['secondary']};
            qproperty-alignment: AlignCenter;
        }}
        """
    
    @staticmethod
    def get_card_style() -> str:
        """Estilo para cards/tarjetas"""
        return f"""
        QFrame.card {{
            background-color: white;
            border: 2px solid {config.COLORS['color4']};
            border-radius: 12px;
            padding: 15px;
        }}
        
        QFrame.card:hover {{
            border-color: {config.COLORS['color5']};
            background-color: {config.COLORS['color1']}10;
        }}
        
        QFrame.card-selected {{
            border-color: {config.COLORS['primary']};
            background-color: {config.COLORS['color4']}20;
        }}
        """
    
    @staticmethod
    def get_badge_style(color: str = "primary") -> str:
        """Estilo para badges/etiquetas"""
        color_map = {
            "primary": config.COLORS['primary'],
            "success": config.COLORS['success'],
            "warning": config.COLORS['warning'],
            "danger": config.COLORS['danger'],
            "info": config.COLORS['info'],
        }
        
        badge_color = color_map.get(color, config.COLORS['primary'])
        
        return f"""
        QLabel.badge {{
            background-color: {badge_color};
            color: white;
            border-radius: 12px;
            padding: 2px 10px;
            font-size: {config.FONT_SIZES['xs']};
            font-weight: bold;
        }}
        """
    
    @staticmethod
    def get_icon_button_style() -> str:
        """Estilo para botones con iconos"""
        return f"""
        QPushButton.icon-button {{
            background-color: transparent;
            border: 2px solid transparent;
            border-radius: 6px;
            padding: 6px;
            min-width: 40px;
            min-height: 40px;
        }}
        
        QPushButton.icon-button:hover {{
            background-color: {config.COLORS['color4']}40;
            border-color: {config.COLORS['color4']};
        }}
        
        QPushButton.icon-button:pressed {{
            background-color: {config.COLORS['color5']}40;
            border-color: {config.COLORS['color5']};
        }}
        """
    
    @staticmethod
    def get_dashboard_style() -> str:
        """Estilo específico para dashboard"""
        return f"""
        /* Dashboard specific styles */
        QFrame.kpi-card {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(171, 228, 255, 0.1),
                stop:1 rgba(255, 255, 255, 0.3));
            border: 2px solid {config.COLORS['color4']};
            border-radius: 15px;
            padding: 20px;
        }}
        
        QLabel.kpi-value {{
            font-size: 32px;
            font-weight: bold;
            color: {config.COLORS['primary']};
        }}
        
        QLabel.kpi-title {{
            font-size: 14px;
            font-weight: bold;
            color: {config.COLORS['dark']};
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        QComboBox.filter-combo {{
            min-height: 30px;
            padding: 5px 10px;
            background-color: white;
            border: 2px solid {config.COLORS['color2']};
            border-radius: 8px;
        }}
        
        QDateEdit.filter-date {{
            min-height: 30px;
            padding: 5px;
            background-color: white;
            border: 2px solid {config.COLORS['color2']};
            border-radius: 8px;
        }}
        
        /* Table styling for dashboard */
        QTableWidget.dashboard-table {{
            alternate-background-color: {config.COLORS['color3']}10;
            selection-background-color: {config.COLORS['color4']}40;
        }}
        
        QTableWidget.dashboard-table::item {{
            padding: 8px;
        }}
        
        /* Chart containers */
        QWidget.chart-container {{
            background-color: white;
            border: 2px solid {config.COLORS['color1']}40;
            border-radius: 10px;
            padding: 10px;
        }}
        
        /* Navigation buttons */
        QPushButton.nav-button {{
            background-color: {config.COLORS['color4']};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 5px 15px;
            font-weight: bold;
        }}
        
        QPushButton.nav-button:hover {{
            background-color: {config.COLORS['color5']};
        }}
        
        QPushButton.nav-button:disabled {{
            background-color: #cccccc;
            color: #666666;
        }}
        """


# Instancia global de estilos
styles = Styles()