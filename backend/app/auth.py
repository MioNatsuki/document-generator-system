# Autenticación JWT 
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from loguru import logger

from config import settings
from models import Usuario, Bitacora
from schemas import TokenPayload


# Configuración de bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si la contraseña en texto plano coincide con el hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Genera hash de contraseña usando bcrypt
    """
    return pwd_context.hash(password, rounds=12)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Crea token JWT de acceso
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    logger.debug(f"Token de acceso creado para {data.get('sub')}, expira: {expire}")
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Crea token JWT de refresh
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    logger.debug(f"Token de refresh creado para {data.get('sub')}, expira: {expire}")
    return encoded_jwt


def verify_token(token: str) -> Optional[TokenPayload]:
    """
    Verifica y decodifica token JWT
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        token_payload = TokenPayload(
            sub=payload.get("sub"),
            exp=payload.get("exp"),
            rol=payload.get("rol")
        )
        
        return token_payload
    except JWTError as e:
        logger.error(f"Error decodificando token JWT: {str(e)}")
        return None


def authenticate_user(db: Session, username: str, password: str) -> Optional[Usuario]:
    """
    Autentica usuario con username y password
    """
    logger.info(f"Intentando autenticar usuario: {username}")
    
    user = db.query(Usuario).filter(
        (Usuario.username == username) | (Usuario.email == username),
        Usuario.is_active == True,
        Usuario.is_deleted == False
    ).first()
    
    if not user:
        logger.warning(f"Usuario no encontrado: {username}")
        return None
    
    if not verify_password(password, user.hashed_password):
        logger.warning(f"Contraseña incorrecta para usuario: {username}")
        return None
    
    logger.info(f"Usuario autenticado exitosamente: {username}")
    return user


def update_last_login(db: Session, user: Usuario, ip_address: Optional[str] = None) -> None:
    """
    Actualiza última fecha de login del usuario
    """
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Registrar en bitácora
    bitacora = Bitacora(
        usuario_id=user.id,
        accion="LOGIN",
        entidad="usuario",
        entidad_id=user.id,
        detalles={"ip": ip_address},
        ip=ip_address
    )
    db.add(bitacora)
    db.commit()
    
    logger.info(f"Último login actualizado para usuario: {user.username}")


def register_failed_login(db: Session, username: str, ip_address: Optional[str] = None) -> None:
    """
    Registra intento fallido de login en bitácora
    """
    bitacora = Bitacora(
        usuario_id=None,  # Usuario no autenticado
        accion="LOGIN_FAILED",
        entidad="usuario",
        entidad_id=None,
        detalles={"username": username, "ip": ip_address},
        ip=ip_address
    )
    db.add(bitacora)
    db.commit()
    
    logger.warning(f"Intento fallido de login para usuario: {username}, IP: {ip_address}")


def get_current_user(db: Session, token: str) -> Optional[Usuario]:
    """
    Obtiene usuario actual a partir del token JWT
    """
    token_payload = verify_token(token)
    
    if not token_payload:
        return None
    
    username = token_payload.sub
    
    user = db.query(Usuario).filter(
        Usuario.username == username,
        Usuario.is_active == True,
        Usuario.is_deleted == False
    ).first()
    
    return user


def validate_token_role(token_payload: TokenPayload, required_roles: list) -> bool:
    """
    Valida que el rol del usuario esté en la lista de roles requeridos
    """
    return token_payload.rol in required_roles