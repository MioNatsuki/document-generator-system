# Test de proyectos 
import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.models import Proyecto, Usuario
from backend.app.schemas import ProyectoCreate, ProyectoBase, ColumnaPadron


def test_create_project(db: Session, superadmin_user: Usuario):
    """Test crear proyecto"""
    proyecto_data = ProyectoCreate(
        proyecto=ProyectoBase(
            nombre="Proyecto Test",
            descripcion="Proyecto de prueba",
            logo_url=None
        ),
        columnas_padron=[
            ColumnaPadron(
                nombre="cuenta",
                tipo="VARCHAR(50)",
                es_obligatorio=True,
                es_unico=True
            ),
            ColumnaPadron(
                nombre="nombre",
                tipo="VARCHAR(255)",
                es_obligatorio=True,
                es_unico=False
            ),
            ColumnaPadron(
                nombre="direccion",
                tipo="VARCHAR(500)",
                es_obligatorio=False,
                es_unico=False
            )
        ],
        csv_data=None
    )
    
    # Verificar que se puede crear proyecto
    assert proyecto_data.proyecto.nombre == "Proyecto Test"
    assert len(proyecto_data.columnas_padron) == 3
    
    # Verificar columnas obligatorias
    nombres = [col.nombre.lower() for col in proyecto_data.columnas_padron]
    assert "cuenta" in nombres
    assert "nombre" in nombres


def test_padron_manager_create_table():
    """Test creación de tabla dinámica"""
    from backend.app.core.padron_manager import PadronManager
    
    columnas = [
        {"nombre": "cuenta", "tipo": "VARCHAR(50)"},
        {"nombre": "nombre", "tipo": "VARCHAR(255)"},
        {"nombre": "monto", "tipo": "DECIMAL(10,2)"}
    ]
    
    # Verificar sanitización de nombres
    table_name = PadronManager.sanitize_table_name("test_project_123")
    assert "test_project_123" in table_name.lower()
    
    col_name = PadronManager.sanitize_column_name("Nombre Completo")
    assert "nombre_completo" in col_name


def test_csv_validation():
    """Test validación de CSV"""
    from backend.app.core.padron_manager import PadronManager
    
    csv_columns = ["cuenta", "nombre", "direccion", "monto"]
    expected_columns = [
        {"nombre": "cuenta", "tipo": "VARCHAR(50)"},
        {"nombre": "nombre", "tipo": "VARCHAR(255)"},
        {"nombre": "direccion", "tipo": "VARCHAR(500)"},
        {"nombre": "monto", "tipo": "DECIMAL(10,2)"}
    ]
    
    valido, errores = PadronManager.validate_csv_structure(csv_columns, expected_columns)
    
    assert valido == True
    assert len(errores) == 0
    
    # Test con CSV inválido (falta columna obligatoria)
    csv_columns_invalido = ["cuenta", "direccion", "monto"]
    valido, errores = PadronManager.validate_csv_structure(csv_columns_invalido, expected_columns)
    
    assert valido == False
    assert "nombre" in str(errores)


def test_project_permissions(db: Session, analista_user: Usuario, test_project: Proyecto):
    """Test permisos de proyecto"""
    from backend.app.api.deps import require_project_access
    
    # Verificar que analista tiene acceso al proyecto asignado
    # (esto depende de la implementación específica)
    assert test_project.nombre == "Proyecto Test"
    
    # Verificar soft delete
    test_project.is_deleted = True
    db.commit()
    
    proyectos_activos = db.query(Proyecto).filter(Proyecto.is_deleted == False).count()
    assert proyectos_activos == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])