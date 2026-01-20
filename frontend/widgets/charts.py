"""
Widgets para gráficas usando Matplotlib
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

from ..config import config
from ..styles import styles


class ChartWidget(QWidget):
    """Widget base para gráficas"""
    
    def __init__(self, title):
        super().__init__()
        self.title = title
        self.data = []
        
        self.init_ui()
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Título
        title_label = QLabel(self.title)
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {config.COLORS['primary']}; padding: 5px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title_label)
        
        # Figura de matplotlib
        self.figure = Figure(figsize=(6, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        
        layout.addWidget(self.canvas)
        
        # Barra de herramientas
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        
        # Botón de exportación
        export_btn = QPushButton("💾 Exportar")
        export_btn.setStyleSheet("""
            QPushButton {
                padding: 3px 8px;
                font-size: 10px;
                margin: 5px;
            }
        """)
        export_btn.clicked.connect(self.export_chart)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(export_btn)
        
        layout.addLayout(btn_layout)
        
    def update_data(self, data):
        """Actualizar datos de la gráfica (debe implementarse en subclases)"""
        self.data = data
        self.update_chart()
        
    def update_chart(self):
        """Actualizar gráfica (debe implementarse en subclases)"""
        pass
        
    def export_chart(self):
        """Exportar gráfica como imagen"""
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar gráfica",
            f"{self.title.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg)"
        )
        
        if file_path:
            self.figure.savefig(file_path, dpi=300, bbox_inches='tight')


class LineChartWidget(ChartWidget):
    """Gráfica de líneas para emisiones en el tiempo"""
    
    def __init__(self, title):
        super().__init__(title)
        
    def update_chart(self):
        """Actualizar gráfica de líneas"""
        self.figure.clear()
        
        if not self.data:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'Sin datos', 
                   ha='center', va='center', 
                   transform=ax.transAxes,
                   fontsize=14, color='gray')
            ax.set_facecolor('#f8f9fa')
            self.canvas.draw()
            return
        
        ax = self.figure.add_subplot(111)
        
        # Extraer datos
        periodos = [item.get('periodo_display', '') for item in self.data]
        valores = [item.get('total', 0) for item in self.data]
        
        # Crear gráfica
        x = range(len(periodos))
        ax.plot(x, valores, marker='o', linewidth=2, color=config.COLORS['color4'])
        ax.fill_between(x, 0, valores, alpha=0.2, color=config.COLORS['color4'])
        
        # Configurar ejes
        ax.set_xticks(x)
        ax.set_xticklabels(periodos, rotation=45, ha='right')
        ax.set_ylabel('Número de PDFs')
        ax.set_title('Emisiones en el tiempo', fontsize=12, pad=10)
        
        # Colores
        ax.set_facecolor('#f8f9fa')
        self.figure.patch.set_facecolor('#ffffff')
        
        # Ajustar layout
        self.figure.tight_layout()
        self.canvas.draw()


class PieChartWidget(ChartWidget):
    """Gráfica de pastel para distribución"""
    
    def __init__(self, title):
        super().__init__(title)
        
    def update_chart(self):
        """Actualizar gráfica de pastel"""
        self.figure.clear()
        
        if not self.data:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'Sin datos', 
                   ha='center', va='center', 
                   transform=ax.transAxes,
                   fontsize=14, color='gray')
            ax.set_facecolor('#f8f9fa')
            self.canvas.draw()
            return
        
        ax = self.figure.add_subplot(111)
        
        # Extraer datos
        labels = [item.get('documento', '') for item in self.data]
        valores = [item.get('total', 0) for item in self.data]
        porcentajes = [item.get('porcentaje', 0) for item in self.data]
        
        # Colores de la paleta
        colors = [
            config.COLORS['color1'],
            config.COLORS['color2'],
            config.COLORS['color3'],
            config.COLORS['color4'],
            config.COLORS['color5'],
            config.COLORS['pastel_pink'],
            config.COLORS['pastel_peach'],
            config.COLORS['pastel_mint'],
            config.COLORS['pastel_sky'],
            config.COLORS['pastel_lavender']
        ]
        
        # Crear gráfica de pastel
        wedges, texts, autotexts = ax.pie(
            valores, 
            labels=labels,
            autopct=lambda p: f'{p:.1f}%' if p > 0 else '',
            colors=colors[:len(labels)],
            startangle=90,
            textprops={'fontsize': 9}
        )
        
        # Mejorar etiquetas
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            
        ax.set_title('Distribución por tipo de documento', fontsize=12, pad=10)
        ax.axis('equal')  # Pastel circular
        
        # Leyenda
        legend_labels = [f'{label} ({val})' for label, val in zip(labels, valores)]
        ax.legend(wedges, legend_labels, 
                 title="Documentos",
                 loc="center left",
                 bbox_to_anchor=(1, 0, 0.5, 1))
        
        self.figure.patch.set_facecolor('#ffffff')
        self.figure.tight_layout()
        self.canvas.draw()


class BarChartWidget(ChartWidget):
    """Gráfica de barras para productividad"""
    
    def __init__(self, title):
        super().__init__(title)
        
    def update_chart(self):
        """Actualizar gráfica de barras"""
        self.figure.clear()
        
        if not self.data:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'Sin datos', 
                   ha='center', va='center', 
                   transform=ax.transAxes,
                   fontsize=14, color='gray')
            ax.set_facecolor('#f8f9fa')
            self.canvas.draw()
            return
        
        ax = self.figure.add_subplot(111)
        
        # Extraer datos
        usuarios = [item.get('username', '')[:10] + '...' for item in self.data]
        valores = [item.get('total_pdfs', 0) for item in self.data]
        
        # Colores por rol
        colors = []
        for item in self.data:
            rol = item.get('rol', '')
            if rol == 'SUPERADMIN':
                colors.append(config.COLORS['color1'])
            elif rol == 'ANALISTA':
                colors.append(config.COLORS['color4'])
            else:
                colors.append(config.COLORS['color3'])
        
        # Crear gráfica de barras
        x = range(len(usuarios))
        bars = ax.bar(x, valores, color=colors, edgecolor='white', linewidth=1)
        
        # Agregar etiquetas de valor
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=9)
        
        # Configurar ejes
        ax.set_xticks(x)
        ax.set_xticklabels(usuarios, rotation=45, ha='right')
        ax.set_ylabel('PDFs generados')
        ax.set_title('Productividad por usuario', fontsize=12, pad=10)
        
        # Grid
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)
        
        # Colores de fondo
        ax.set_facecolor('#f8f9fa')
        self.figure.patch.set_facecolor('#ffffff')
        
        # Leyenda
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=config.COLORS['color1'], label='Superadmin'),
            Patch(facecolor=config.COLORS['color4'], label='Analista'),
            Patch(facecolor=config.COLORS['color3'], label='Auxiliar')
        ]
        ax.legend(handles=legend_elements, loc='upper right')
        
        self.figure.tight_layout()
        self.canvas.draw()