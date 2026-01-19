from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from ..database import get_db
from ..models import Usuario, Proyecto, ProyectoUsuario
from ..config import settings
from ..auth import verify_token, get_current_user
from ..utils.security import SecurityManager


security = HTTPBearer(auto_error=False)


async def get_current_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[Usuario]:
    """
    Obtiene usuario actual desde token JWT
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user = get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado o inactivo",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_active_user(
    current_user: Usuario = Depends(get_current_user_from_token)
) -> Usuario:
    """
    Verifica que el usuario esté activo
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )
    return current_user


def get_current_superadmin(
    current_user: Usuario = Depends(get_current_active_user)
) -> Usuario:
    """
    Verifica que el usuario sea SUPERADMIN
    """
    if current_user.rol != "SUPERADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes. Se requiere rol SUPERADMIN"
        )
    return current_user


def get_current_analista_or_higher(
    current_user: Usuario = Depends(get_current_active_user)
) -> Usuario:
    """
    Verifica que el usuario sea ANALISTA o SUPERADMIN
    """
    if current_user.rol not in ["SUPERADMIN", "ANALISTA"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes. Se requiere rol ANALISTA o SUPERADMIN"
        )
    return current_user


async def get_ip_address(request: Request) -> str:
    """
    Obtiene dirección IP del cliente
    """
    # Obtener IP real detrás de proxy
    if request.headers.get("x-forwarded-for"):
        ip = request.headers["x-forwarded-for"].split(",")[0]
    else:
        ip = request.client.host if request.client else "0.0.0.0"
    
    return ip


async def get_user_agent(request: Request) -> str:
    """
    Obtiene User-Agent del cliente
    """
    return request.headers.get("user-agent", "Unknown")


def require_project_access(permission: str):
    """
    Factory para dependencia de acceso a proyecto
    """
    def dependency(
        project_id: int,
        current_user: Usuario = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> bool:
        """
        Verifica acceso a proyecto específico
        """
        # Superadmin tiene acceso a todo
        if current_user.rol == "SUPERADMIN":
            return True
        
        # Verificar si el usuario está asignado al proyecto
        project_user = db.query(ProyectoUsuario).filter(
            ProyectoUsuario.usuario_id == current_user.id,
            ProyectoUsuario.proyecto_id == project_id
        ).first()
        
        if not project_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a este proyecto"
            )
        
        # Verificar permiso específico según rol en proyecto
        if permission == "view":
            # Todos los roles pueden ver
            return True
        elif permission == "manage_templates":
            return project_user.rol_en_proyecto in ["SUPERADMIN", "ANALISTA"]
        elif permission == "manage_padron":
            return project_user.rol_en_proyecto in ["SUPERADMIN", "ANALISTA"]
        elif permission == "generate_pdfs":
            return True  # Todos los roles pueden generar PDFs
        elif permission == "view_stats":
            if project_user.rol_en_proyecto == "AUXILIAR":
                # Auxiliar solo puede ver sus propias estadísticas
                return False
            return True
        
        return False
    return dependency


def get_project(
    project_id: int,
    db: Session = Depends(get_db)
) -> Proyecto:
    """
    Obtiene proyecto y verifica que exista y no esté eliminado
    """
    proyecto = db.query(Proyecto).filter(
        Proyecto.id == project_id,
        Proyecto.is_deleted == False
    ).first()
    
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )
    
    return proyecto