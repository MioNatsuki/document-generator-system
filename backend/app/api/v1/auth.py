# Endpoints de autenticación 
from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Usuario
from ...schemas import LoginRequest, Token, RefreshTokenRequest
from ...auth import (
    authenticate_user, 
    create_access_token, 
    create_refresh_token,
    verify_token,
    update_last_login,
    register_failed_login
)
from ...api.deps import get_ip_address, get_user_agent, get_current_active_user
from ...utils.logging import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address),
    user_agent: str = Depends(get_user_agent)
) -> Any:
    """
    Inicio de sesión con username/email y password
    """
    logger.info(f"Intento de login desde IP: {ip}, User-Agent: {user_agent}")
    
    try:
        # Autenticar usuario
        user = authenticate_user(db, form_data.username, form_data.password)
        
        if not user:
            # Registrar intento fallido
            register_failed_login(db, form_data.username, ip)
            
            logger.warning(f"Login fallido para usuario: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Actualizar último login
        update_last_login(db, user, ip)
        
        # Crear tokens
        access_token = create_access_token(
            data={"sub": user.username, "rol": user.rol}
        )
        refresh_token = create_refresh_token(
            data={"sub": user.username}
        )
        
        logger.info(f"Login exitoso para usuario: {user.username}")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        logger.error(f"Error en login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Refrescar token de acceso usando refresh token
    """
    try:
        # Verificar refresh token
        token_payload = verify_token(refresh_request.refresh_token)
        
        if not token_payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido o expirado"
            )
        
        # Obtener usuario
        user = db.query(Usuario).filter(
            Usuario.username == token_payload.sub,
            Usuario.is_active == True,
            Usuario.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado"
            )
        
        # Crear nuevos tokens
        access_token = create_access_token(
            data={"sub": user.username, "rol": user.rol}
        )
        new_refresh_token = create_refresh_token(
            data={"sub": user.username}
        )
        
        logger.info(f"Token refrescado para usuario: {user.username}")
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refrescando token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.post("/logout")
async def logout(
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
) -> Any:
    """
    Cerrar sesión (registrar en bitácora)
    """
    try:
        from ...models import Bitacora
        
        bitacora = Bitacora(
            usuario_id=current_user.id,
            accion="LOGOUT",
            entidad="usuario",
            entidad_id=current_user.id,
            detalles={"ip": ip},
            ip=ip
        )
        db.add(bitacora)
        db.commit()
        
        logger.info(f"Logout exitoso para usuario: {current_user.username}")
        
        return {"message": "Sesión cerrada exitosamente"}
        
    except Exception as e:
        logger.error(f"Error en logout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.get("/me")
async def read_users_me(
    current_user: Usuario = Depends(get_current_active_user)
) -> Any:
    """
    Obtener información del usuario actual
    """
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "nombre_completo": current_user.nombre_completo,
        "rol": current_user.rol,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login
    }


@router.post("/validate-token")
async def validate_token(
    current_user: Usuario = Depends(get_current_active_user)
) -> Any:
    """
    Validar token JWT (para mantener sesión activa en frontend)
    """
    return {
        "valid": True,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "rol": current_user.rol
        }
    }