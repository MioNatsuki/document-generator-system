# frontend/widgets/__init__.py
"""
Widgets personalizados
"""

from widgets.dashboard_window import DashboardWindow
from widgets.kpi_card import KPICard
from widgets.charts import LineChartWidget, PieChartWidget, BarChartWidget
from widgets.project_selection_window import ProjectSelectionWindow  
from widgets.sidebar import Sidebar  

__all__ = [
    'DashboardWindow',
    'KPICard',
    'LineChartWidget',
    'PieChartWidget',
    'BarChartWidget',
    'ProjectSelectionWindow',  
    'Sidebar',  
]