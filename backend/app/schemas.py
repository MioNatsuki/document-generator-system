# Pydantic schemas 
from pydantic import BaseModel, EmailStr, Field, validator, root_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


# Enums
class RolEnum(str, Enum):
    SUPERADMIN = "SUPERADMIN"
    ANALISTA = "ANALISTA"
    AUXILIAR = "AUXILIAR"


class AccionBitacoraEnum(str, Enum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    CREAR_PROYECTO = "CREAR_PROYECTO"
    EDITAR_PROYECTO = "EDITAR_PROYECTO"
    ELIMINAR_PROYECTO = "ELIMINAR_PROYECTO"
    CREAR_PLANTILLA = "CREAR_PLANTILLA"
    EDITAR_PLANTILLA = "EDITAR_PLANTILLA"
    ELIMINAR_PLANTILLA = "ELIMINAR_PLANTILLA"
    SUBIR_PADRON = "SUBIR_PADRON"
    EDITAR_PADRON = "EDITAR_PADRON"
    INICIAR_EMISION = "INICIAR_EMISION"
    EMISION_COMPLETADA = "EMISION_COMPLETADA"
    CREAR_USUARIO = "CREAR_USUARIO"
    EDITAR_USUARIO = "EDITAR_USUARIO"
    ELIMINAR_USUARIO = "ELIMINAR_USUARIO"


# Base schemas
class UsuarioBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    nombre_completo: str = Field(..., min_length=1, max_length=255)
    rol: RolEnum


class UsuarioCreate(UsuarioBase):
    password: str = Field(..., min_length=8, max_length=100)
    
    @validator('password')
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('La contraseña debe contener al menos una mayúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('La contraseña debe contener al menos un número')
        if not any(c.islower() for c in v):
            raise ValueError('La contraseña debe contener al menos una minúscula')
        return v


class UsuarioUpdate(BaseModel):
    email: Optional[EmailStr] = None
    nombre_completo: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    is_active: Optional[bool] = None
    rol: Optional[RolEnum] = None
    
    @validator('password')
    def validate_password(cls, v):
        if v is not None:
            if not any(c.isupper() for c in v):
                raise ValueError('La contraseña debe contener al menos una mayúscula')
            if not any(c.isdigit() for c in v):
                raise ValueError('La contraseña debe contener al menos un número')
            if not any(c.islower() for c in v):
                raise ValueError('La contraseña debe contener al menos una minúscula')
        return v


class UsuarioInDB(UsuarioBase):
    id: int
    uuid: UUID
    is_active: bool
    is_deleted: bool
    created_at: datetime
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int
    rol: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ProyectoBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=255)
    descripcion: Optional[str] = None
    logo_url: Optional[str] = None


class ColumnaPadron(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    tipo: str = Field(..., pattern=r'^(VARCHAR\(\d+\)|INT|DECIMAL\(\d+,\d+\)|DATE|TEXT|BOOLEAN)$')
    es_obligatorio: bool = False
    es_unico: bool = False


class ProyectoCreate(BaseModel):
    proyecto: ProyectoBase
    columnas_padron: List[ColumnaPadron]
    csv_data: Optional[bytes] = None  # CSV en base64 o similar
    
    @root_validator
    def validate_columnas(cls, values):
        columnas = values.get('columnas_padron', [])
        nombres = [col.nombre.lower() for col in columnas]
        
        # Verificar columnas obligatorias
        if 'cuenta' not in nombres:
            raise ValueError('El padrón debe contener la columna "cuenta"')
        if 'nombre' not in nombres:
            raise ValueError('El padrón debe contener la columna "nombre"')
        
        # Verificar nombres duplicados
        if len(nombres) != len(set(nombres)):
            raise ValueError('Hay nombres de columnas duplicados')
        
        return values


class ProyectoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=255)
    descripcion: Optional[str] = None
    logo_url: Optional[str] = None


class ProyectoInDB(ProyectoBase):
    id: int
    uuid: UUID
    uuid_padron: UUID
    nombre_tabla_padron: str
    estructura_padron: Dict[str, Any]
    is_deleted: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PlantillaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=255)
    descripcion: Optional[str] = None


class MapeoPlaceholder(BaseModel):
    campo_padron: str
    x: float  # En cm
    y: float  # En cm
    ancho: float  # En cm
    alto: float  # En cm
    fuente: str = "Calibri"
    tamaño: int = Field(11, ge=8, le=16)
    es_codigo_barras: bool = False
    formato: Optional[str] = None  # Para fechas, moneda, etc.


class PlantillaCreate(BaseModel):
    plantilla: PlantillaBase
    archivo_docx: bytes  # Archivo en base64
    mapeos: List[MapeoPlaceholder]
    
    @validator('mapeos')
    def validate_mapeos(cls, v):
        if not v:
            raise ValueError('Debe definir al menos un mapeo')
        return v


class PlantillaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=255)
    descripcion: Optional[str] = None
    mapeos: Optional[List[MapeoPlaceholder]] = None


class PlantillaInDB(PlantillaBase):
    id: int
    uuid: UUID
    proyecto_id: int
    archivo_docx: str
    archivo_pdf_base: Optional[str]
    configuracion: Dict[str, Any]
    tamaño_pagina: Dict[str, Any]
    is_deleted: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class EmisionCSVData(BaseModel):
    cuenta: str
    orden_impresion: int
    datos_adicionales: Optional[Dict[str, Any]] = None


class EmisionRequest(BaseModel):
    plantilla_id: int
    documento: str = Field(..., pattern=r'^(Notificación|Apercibimiento|Embargo|Carta Invitación)$')
    pmo: str = Field(..., pattern=r'^PMO \d+$')
    fecha_emision: datetime
    datos: List[EmisionCSVData]
    ruta_salida: Optional[str] = None


class EmisionInDB(BaseModel):
    id: int
    sesion_id: UUID
    proyecto_id: int
    plantilla_id: int
    usuario_id: int
    cuenta: str
    documento: str
    pmo: str
    fecha_emision: datetime
    visita: str
    ruta_archivo_pdf: str
    fecha_generacion: datetime
    
    class Config:
        from_attributes = True


class BitacoraInDB(BaseModel):
    id: int
    usuario_id: int
    accion: str
    entidad: Optional[str]
    entidad_id: Optional[int]
    detalles: Optional[Dict[str, Any]]
    ip: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int