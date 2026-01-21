# Funciones de seguridad 
import re
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import Usuario, ProyectoUsuario
from schemas import RolEnum


class SecurityManager:
    """
    Gestor centralizado de seguridad y permisos
    """
    
    @staticmethod
    def validate_password_strength(password: str) -> bool:
        """
        Valida fortaleza de contraseña
        """
        if len(password) < 8:
            return False
        
        # Debe contener al menos una mayúscula, una minúscula y un número
        if not re.search(r'[A-Z]', password):
            return False
        if not re.search(r'[a-z]', password):
            return False
        if not re.search(r'[0-9]', password):
            return False
        
        return True
    
    @staticmethod
    def get_user_permissions(db: Session, user_id: int) -> dict:
        """
        Obtiene permisos completos del usuario
        """
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        
        if not user:
            return {}
        
        permissions = {
            "global": {
                "can_manage_users": user.rol == RolEnum.SUPERADMIN.value,
                "can_manage_all_projects": user.rol == RolEnum.SUPERADMIN.value,
                "can_view_global_stats": user.rol == RolEnum.SUPERADMIN.value,
                "can_view_global_logs": user.rol == RolEnum.SUPERADMIN.value,
                "can_create_projects": user.rol == RolEnum.SUPERADMIN.value,
            },
            "project_specific": {}
        }
        
        # Obtener permisos por proyecto
        project_users = db.query(ProyectoUsuario).filter(
            ProyectoUsuario.usuario_id == user_id
        ).all()
        
        for pu in project_users:
            permissions["project_specific"][pu.proyecto_id] = {
                "can_manage_templates": pu.rol_en_proyecto in [RolEnum.SUPERADMIN.value, RolEnum.ANALISTA.value],
                "can_manage_padron": pu.rol_en_proyecto in [RolEnum.SUPERADMIN.value, RolEnum.ANALISTA.value],
                "can_view_project_stats": pu.rol_en_proyecto in [RolEnum.SUPERADMIN.value, RolEnum.ANALISTA.value, RolEnum.AUXILIAR.value],
                "can_generate_pdfs": pu.rol_en_proyecto in [RolEnum.SUPERADMIN.value, RolEnum.ANALISTA.value, RolEnum.AUXILIAR.value],
                "can_view_own_stats_only": pu.rol_en_proyecto == RolEnum.AUXILIAR.value,
                "project_role": pu.rol_en_proyecto
            }
        
        return permissions
    
    @staticmethod
    def check_project_access(db: Session, user_id: int, project_id: int, required_permission: str) -> bool:
        """
        Verifica acceso a proyecto específico
        """
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        
        # Superadmin tiene acceso a todo
        if user.rol == RolEnum.SUPERADMIN.value:
            return True
        
        # Verificar si el usuario está asignado al proyecto
        project_user = db.query(ProyectoUsuario).filter(
            ProyectoUsuario.usuario_id == user_id,
            ProyectoUsuario.proyecto_id == project_id
        ).first()
        
        if not project_user:
            return False
        
        # Verificar permiso específico
        permissions = SecurityManager.get_user_permissions(db, user_id)
        project_perms = permissions["project_specific"].get(project_id, {})
        
        return project_perms.get(required_permission, False)


def require_role(required_roles: List[str]):
    """
    Decorador para verificar roles en endpoints
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No autenticado"
                )
            
            if current_user.rol not in required_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permisos insuficientes"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator