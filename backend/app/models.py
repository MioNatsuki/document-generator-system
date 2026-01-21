# Modelos SQLAlchemy 
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, 
    ForeignKey, Text, JSON, Numeric, BigInteger,
    Table, Index, UniqueConstraint, CheckConstraint,
    event, DDL
)
from sqlalchemy.sql import func, text
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import UUID
import uuid
from uuid import uuid4
from datetime import datetime

from .database import Base


class Usuario(Base):
    """
    Modelo de usuarios del sistema
    """
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nombre_completo = Column(String(255), nullable=False)
    rol = Column(String(20), nullable=False, index=True)  # SUPERADMIN, ANALISTA, AUXILIAR
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Relaciones
    proyectos_asignados = relationship("ProyectoUsuario", back_populates="usuario", cascade="all, delete-orphan")
    emisiones = relationship("EmisionAcumulada", back_populates="usuario")
    bitacoras = relationship("Bitacora", back_populates="usuario")
    
    # Índices
    __table_args__ = (
        Index("idx_usuario_rol", "rol", "is_active"),
        Index("idx_usuario_username_active", "username", "is_active"),
    )
    
    @validates('rol')
    def validate_rol(self, key, rol):
        valid_roles = ['SUPERADMIN', 'ANALISTA', 'AUXILIAR']
        if rol not in valid_roles:
            raise ValueError(f"Rol inválido. Debe ser uno de: {valid_roles}")
        return rol
    
    @validates('email')
    def validate_email(self, key, email):
        if '@' not in email:
            raise ValueError("Email inválido")
        return email.lower()


class Proyecto(Base):
    """
    Modelo de proyectos
    """
    __tablename__ = "proyectos"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    nombre = Column(String(255), unique=True, index=True, nullable=False)
    descripcion = Column(Text)
    logo_url = Column(String(500))
    nombre_tabla_padron = Column(String(100), unique=True, nullable=False)  # Ej: padron_completo_proyecto1
    uuid_padron = Column(UUID(as_uuid=True), unique=True, default=uuid4)
    estructura_padron = Column(JSON, nullable=False)  # {"columnas": [{"nombre": "cuenta", "tipo": "VARCHAR(50)"}, ...]}
    is_deleted = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    usuarios = relationship("ProyectoUsuario", back_populates="proyecto", cascade="all, delete-orphan")
    plantillas = relationship("Plantilla", back_populates="proyecto")
    emisiones = relationship("EmisionAcumulada", back_populates="proyecto")
    
    # Índices
    __table_args__ = (
        Index("idx_proyecto_nombre_deleted", "nombre", "is_deleted"),
        Index("idx_proyecto_uuid", "uuid"),
    )
    
    @hybrid_property
    def tabla_padron_completo(self):
        return f"padron_completo_{self.uuid_padron.hex[:8]}"


class ProyectoUsuario(Base):
    """
    Relación muchos-a-muchos entre usuarios y proyectos
    """
    __tablename__ = "proyectos_usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    proyecto_id = Column(Integer, ForeignKey("proyectos.id", ondelete="CASCADE"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    rol_en_proyecto = Column(String(20), nullable=False)  # Puede diferir del rol global
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    proyecto = relationship("Proyecto", back_populates="usuarios")
    usuario = relationship("Usuario", back_populates="proyectos_asignados")
    
    # Restricciones
    __table_args__ = (
        UniqueConstraint('proyecto_id', 'usuario_id', name='uq_proyecto_usuario'),
        Index("idx_proyecto_usuario", "proyecto_id", "usuario_id"),
    )
    
    @validates('rol_en_proyecto')
    def validate_rol_en_proyecto(self, key, rol):
        valid_roles = ['SUPERADMIN', 'ANALISTA', 'AUXILIAR']
        if rol not in valid_roles:
            raise ValueError(f"Rol en proyecto inválido. Debe ser uno de: {valid_roles}")
        return rol


class Plantilla(Base):
    """
    Modelo de plantillas de documentos
    """
    __tablename__ = "plantillas"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    proyecto_id = Column(Integer, ForeignKey("proyectos.id"), nullable=False)
    nombre = Column(String(255), nullable=False)
    descripcion = Column(Text)
    archivo_docx = Column(String(500), nullable=False)  # Ruta al archivo original
    archivo_pdf_base = Column(String(500))  # Ruta al PDF convertido
    configuracion = Column(JSON, nullable=False)  # Mapeo de placeholders
    tamaño_pagina = Column(JSON, nullable=False)  # {"ancho": 21.59, "alto": 34.01, "unidad": "cm"}
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    proyecto = relationship("Proyecto", back_populates="plantillas")
    emisiones = relationship("EmisionAcumulada", back_populates="plantilla")
    
    # Índices
    __table_args__ = (
        Index("idx_plantilla_proyecto", "proyecto_id", "is_deleted"),
        Index("idx_plantilla_uuid", "uuid"),
    )


class EmisionTemp(Base):
    """
    Tabla temporal para carga de datos de emisión
    """
    __tablename__ = "emisiones_temp"
    
    id = Column(Integer, primary_key=True, index=True)
    sesion_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    proyecto_id = Column(Integer, ForeignKey("proyectos.id"), nullable=False)
    cuenta = Column(String(50), nullable=False)
    orden_impresion = Column(Integer, nullable=False)
    datos_raw = Column(JSON)  # Datos adicionales del CSV
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relación
    proyecto = relationship("Proyecto")
    
    # Índices
    __table_args__ = (
        Index("idx_emision_temp_sesion", "sesion_id", "proyecto_id"),
        Index("idx_emision_temp_cuenta", "cuenta", "proyecto_id"),
    )


class EmisionFinal(Base):
    """
    Datos finales procesados para generación
    """
    __tablename__ = "emisiones_final"
    
    id = Column(Integer, primary_key=True, index=True)
    sesion_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    proyecto_id = Column(Integer, ForeignKey("proyectos.id"), nullable=False)
    plantilla_id = Column(Integer, ForeignKey("plantillas.id"), nullable=False)
    cuenta = Column(String(50), nullable=False)
    orden_impresion = Column(Integer, nullable=False)
    datos_json = Column(JSON, nullable=False)  # Todos los datos del padrón + campos calculados
    documento = Column(String(50), nullable=False)
    pmo = Column(String(50), nullable=False)
    fecha_emision = Column(DateTime(timezone=True), nullable=False)
    visita = Column(String(50), nullable=False)
    codigo_barras = Column(String(500))
    is_generado = Column(Boolean, default=False)
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    proyecto = relationship("Proyecto")
    plantilla = relationship("Plantilla")
    
    # Índices
    __table_args__ = (
        Index("idx_emision_final_sesion", "sesion_id", "proyecto_id"),
        Index("idx_emision_final_cuenta", "cuenta", "proyecto_id"),
        Index("idx_emision_final_orden", "orden_impresion", "sesion_id"),
    )


class EmisionAcumulada(Base):
    """
    Histórico de todas las emisiones realizadas
    """
    __tablename__ = "emisiones_acumuladas"
    
    id = Column(BigInteger, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    sesion_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    proyecto_id = Column(Integer, ForeignKey("proyectos.id"), nullable=False)
    plantilla_id = Column(Integer, ForeignKey("plantillas.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    cuenta = Column(String(50), nullable=False, index=True)
    orden_impresion = Column(Integer, nullable=False)
    datos_json = Column(JSON, nullable=False)
    documento = Column(String(50), nullable=False, index=True)
    pmo = Column(String(50), nullable=False)
    fecha_emision = Column(DateTime(timezone=True), nullable=False, index=True)
    visita = Column(String(50), nullable=False)
    codigo_barras = Column(String(500))
    ruta_archivo_pdf = Column(String(500), nullable=False)
    tamaño_archivo = Column(BigInteger)  # En bytes
    hash_archivo = Column(String(64))  # SHA256 del archivo
    usuario_id_generacion = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha_generacion = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relaciones
    proyecto = relationship("Proyecto", back_populates="emisiones", foreign_keys=[proyecto_id])
    plantilla = relationship("Plantilla", back_populates="emisiones", foreign_keys=[plantilla_id])
    usuario = relationship("Usuario", back_populates="emisiones", foreign_keys=[usuario_id])
    usuario_generacion = relationship("Usuario", foreign_keys=[usuario_id_generacion])
    
    # Índices para consultas frecuentes
    __table_args__ = (
        Index("idx_emisiones_acumuladas_fecha", "fecha_emision", "proyecto_id"),
        Index("idx_emisiones_acumuladas_usuario", "usuario_id", "fecha_generacion"),
        Index("idx_emisiones_acumuladas_documento", "documento", "fecha_emision"),
        Index("idx_emisiones_acumuladas_proyecto_usuario", "proyecto_id", "usuario_id", "fecha_generacion"),
    )


class Bitacora(Base):
    """
    Registro de todas las acciones en el sistema
    """
    __tablename__ = "bitacora"
    
    id = Column(BigInteger, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    accion = Column(String(100), nullable=False, index=True)
    entidad = Column(String(50), index=True)  # 'proyecto', 'plantilla', 'emision', 'usuario'
    entidad_id = Column(Integer, index=True)
    detalles = Column(JSON)
    ip = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relación
    usuario = relationship("Usuario", back_populates="bitacoras")
    
    # Índices
    __table_args__ = (
        Index("idx_bitacora_accion_fecha", "accion", "created_at"),
        Index("idx_bitacora_usuario_fecha", "usuario_id", "created_at"),
        Index("idx_bitacora_entidad", "entidad", "entidad_id"),
    )


# Evento para crear trigger de actualización de updated_at
@event.listens_for(Base.metadata, "after_create")
def create_updated_at_triggers(target, connection, **kw):
    """
    Crea triggers PostgreSQL para actualizar automáticamente updated_at
    Versión corregida: solo crea triggers para tablas que tienen columna updated_at
    """
    # Solo tablas que tienen columna updated_at
    tables_with_updated_at = [
        "usuarios", "proyectos", "plantillas", 
        "emisiones_temp", "emisiones_final", "emisiones_acumuladas"
    ]
    
    for table in tables_with_updated_at:
        # Primero, crear la función de trigger si no existe
        trigger_function = f"""
        CREATE OR REPLACE FUNCTION update_{table}_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
        
        try:
            connection.execute(text(trigger_function))
        except Exception as e:
            print(f"Error creando función para {table}: {str(e)}")
            # Continuar con la siguiente tabla
        
        # Luego crear el trigger
        trigger = f"""
        DROP TRIGGER IF EXISTS trigger_update_{table}_updated_at ON {table};
        CREATE TRIGGER trigger_update_{table}_updated_at
        BEFORE UPDATE ON {table}
        FOR EACH ROW
        EXECUTE FUNCTION update_{table}_updated_at();
        """
        
        try:
            connection.execute(text(trigger))
            print(f"Trigger creado para tabla: {table}")
        except Exception as e:
            print(f"Error creando trigger para {table}: {str(e)}")
            # Posiblemente la tabla no tiene columna updated_at, continuar
    
    # También crear función genérica para futuras tablas
    generic_function = """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
    
    try:
        connection.execute(text(generic_function))
        print("Función genérica update_updated_at_column creada")
    except Exception as e:
        print(f"Error creando función genérica: {str(e)}")
    
    connection.commit()