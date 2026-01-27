# Endpoints de proyectos 
import csv
from io import StringIO
import uuid
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
from pathlib import Path

from app.database import get_db
from app.models import Usuario, Proyecto, ProyectoUsuario, Bitacora
from app.schemas import (
    ProyectoCreate, ProyectoUpdate, ProyectoInDB, 
    ColumnaPadron, PaginatedResponse, ProyectoBase
)
from app.api.deps import (
    get_current_active_user, get_current_superadmin, 
    get_current_analista_or_higher, get_ip_address,
    require_project_access
)
from app.core.padron_manager import PadronManager
from app.utils.file_handlers import FileHandler
from app.utils.logging import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.post("/", response_model=ProyectoInDB)
async def crear_proyecto(
    proyecto_create: ProyectoCreate,
    current_user: Usuario = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
) -> Any:
    """
    Crear nuevo proyecto con tabla dinámica de padrón
    """
    logger.info(f"Creando nuevo proyecto: {proyecto_create.proyecto.nombre}")
    
    try:
        # Verificar si ya existe proyecto con ese nombre
        existing = db.query(Proyecto).filter(
            Proyecto.nombre == proyecto_create.proyecto.nombre,
            Proyecto.is_deleted == False
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un proyecto con ese nombre"
            )
        
        # Validar columnas del padrón
        columnas = [col.dict() for col in proyecto_create.columnas_padron]
        
        # Verificar columnas obligatorias
        nombres_columnas = [col['nombre'].lower() for col in columnas]
        if 'cuenta' not in nombres_columnas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El padrón debe contener la columna 'cuenta'"
            )
        
        if 'nombre' not in nombres_columnas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El padrón debe contener la columna 'nombre'"
            )
        
        # Generar UUID para el padrón
        padron_uuid = uuid.uuid4()
        
        # Crear tabla dinámica
        table_name, table_base_name = PadronManager.create_padron_table(str(padron_uuid), columnas)
        
        # Crear proyecto en BD
        proyecto = Proyecto(
            nombre=proyecto_create.proyecto.nombre,
            descripcion=proyecto_create.proyecto.descripcion,
            logo_url=proyecto_create.proyecto.logo_url,
            nombre_tabla_padron=table_name,
            uuid_padron=padron_uuid,
            estructura_padron={"columnas": columnas}
        )
        
        db.add(proyecto)
        db.flush()  # Para obtener el ID sin commit
        
        # Asignar creador como superadmin del proyecto
        proyecto_usuario = ProyectoUsuario(
            proyecto_id=proyecto.id,
            usuario_id=current_user.id,
            rol_en_proyecto="SUPERADMIN"
        )
        db.add(proyecto_usuario)
        
        # Cargar datos iniciales si se proporcionaron
        if proyecto_create.csv_data:
            try:
                # Parsear CSV
                datos, csv_columns = PadronManager.parse_csv_to_dict(proyecto_create.csv_data)
                
                # Validar estructura
                valido, errores = PadronManager.validate_csv_structure(csv_columns, columnas)
                if not valido:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Error en estructura CSV: {', '.join(errores)}"
                    )
                
                # Insertar datos
                result = PadronManager.insert_padron_data(table_name, datos, merge=False)
                
                logger.info(f"Datos iniciales cargados: {result}")
                
            except Exception as e:
                logger.error(f"Error cargando datos iniciales: {str(e)}")
                # No fallamos la creación del proyecto por error en datos
        
        # Registrar en bitácora
        bitacora = Bitacora(
            usuario_id=current_user.id,
            accion="CREAR_PROYECTO",
            entidad="proyecto",
            entidad_id=proyecto.id,
            detalles={
                "nombre": proyecto.nombre,
                "tabla_padron": table_name,
                "columnas": len(columnas)
            },
            ip=ip
        )
        db.add(bitacora)
        
        db.commit()
        db.refresh(proyecto)
        
        logger.info(f"Proyecto creado exitosamente: {proyecto.nombre} (ID: {proyecto.id})")
        
        return proyecto
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error de base de datos al crear proyecto: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de base de datos"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado al crear proyecto: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )


@router.get("/", response_model=PaginatedResponse)
async def listar_proyectos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Listar proyectos según permisos del usuario
    """
    try:
        # Si es superadmin, ver todos los proyectos
        if current_user.rol == "SUPERADMIN":
            query = db.query(Proyecto).filter(Proyecto.is_deleted == False)
            total = query.count()
            proyectos = query.offset(skip).limit(limit).all()
        else:
            # Solo proyectos asignados
            query = db.query(Proyecto).join(
                ProyectoUsuario, Proyecto.id == ProyectoUsuario.proyecto_id
            ).filter(
                ProyectoUsuario.usuario_id == current_user.id,
                Proyecto.is_deleted == False
            )
            total = query.count()
            proyectos = query.offset(skip).limit(limit).all()
        
        # **CONVERTIR A DICCIONARIO SIMPLE PARA SERIALIZACIÓN**
        proyectos_simple = []
        for proyecto in proyectos:
            proyectos_simple.append({
                "id": proyecto.id,
                "uuid": proyecto.uuid,
                "nombre": proyecto.nombre,
                "descripcion": proyecto.descripcion,
                "logo_url": proyecto.logo_url,
                "nombre_tabla_padron": proyecto.nombre_tabla_padron,
                "uuid_padron": proyecto.uuid_padron,
                "estructura_padron": proyecto.estructura_padron,
                "is_deleted": proyecto.is_deleted,
                "created_at": proyecto.created_at,
                "updated_at": proyecto.updated_at,
                # No incluir relaciones
            })
        
        return {
            "items": proyectos_simple,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "size": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 1
        }
        
    except Exception as e:
        logger.error(f"Error listando proyectos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.get("/{proyecto_id}", response_model=ProyectoInDB)
async def obtener_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Obtener proyecto por ID
    """
    try:
        # Verificar permisos
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes acceso a este proyecto"
                )
        
        proyecto = db.query(Proyecto).filter(
            Proyecto.id == proyecto_id,
            Proyecto.is_deleted == False
        ).first()
        
        if not proyecto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado"
            )
        
        return proyecto
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo proyecto: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.put("/{proyecto_id}", response_model=ProyectoInDB)
async def actualizar_proyecto(
    proyecto_id: int,
    proyecto_update: ProyectoUpdate,
    current_user: Usuario = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
) -> Any:
    """
    Actualizar proyecto (solo superadmin)
    """
    logger.info(f"Actualizando proyecto ID: {proyecto_id}")
    
    try:
        proyecto = db.query(Proyecto).filter(
            Proyecto.id == proyecto_id,
            Proyecto.is_deleted == False
        ).first()
        
        if not proyecto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado"
            )
        
        # Actualizar campos
        update_data = proyecto_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(proyecto, field):
                setattr(proyecto, field, value)
        
        db.add(proyecto)
        
        # Registrar en bitácora
        bitacora = Bitacora(
            usuario_id=current_user.id,
            accion="EDITAR_PROYECTO",
            entidad="proyecto",
            entidad_id=proyecto.id,
            detalles={"cambios": update_data},
            ip=ip
        )
        db.add(bitacora)
        
        db.commit()
        db.refresh(proyecto)
        
        logger.info(f"Proyecto actualizado: {proyecto.nombre}")
        
        return proyecto
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando proyecto: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.delete("/{proyecto_id}")
async def eliminar_proyecto(
    proyecto_id: int,
    confirmacion: bool = Form(..., description="Confirmar eliminación"),
    current_user: Usuario = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
) -> Any:
    """
    Eliminar proyecto (soft delete)
    """
    if not confirmacion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere confirmación para eliminar"
        )
    
    logger.warning(f"Eliminando proyecto ID: {proyecto_id}")
    
    try:
        proyecto = db.query(Proyecto).filter(
            Proyecto.id == proyecto_id,
            Proyecto.is_deleted == False
        ).first()
        
        if not proyecto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado"
            )
        
        # Verificar si hay emisiones históricas
        from ...models import EmisionAcumulada
        emisiones_count = db.query(EmisionAcumulada).filter(
            EmisionAcumulada.proyecto_id == proyecto_id
        ).count()
        
        # Soft delete
        proyecto.is_deleted = True
        
        # Eliminar tabla de padrón
        success = PadronManager.drop_padron_table(proyecto.nombre_tabla_padron)
        if not success:
            logger.warning(f"No se pudo eliminar tabla de padrón: {proyecto.nombre_tabla_padron}")
        
        # Registrar en bitácora
        bitacora = Bitacora(
            usuario_id=current_user.id,
            accion="ELIMINAR_PROYECTO",
            entidad="proyecto",
            entidad_id=proyecto.id,
            detalles={
                "nombre": proyecto.nombre,
                "emisiones_historicas": emisiones_count,
                "tabla_eliminada": success
            },
            ip=ip
        )
        db.add(bitacora)
        
        db.commit()
        
        logger.info(f"Proyecto eliminado: {proyecto.nombre}")
        
        return {
            "message": f"Proyecto '{proyecto.nombre}' eliminado exitosamente",
            "emisiones_historicas": emisiones_count,
            "tabla_padron_eliminada": success
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error eliminando proyecto: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.post("/{proyecto_id}/cargar-padron")
async def cargar_padron_csv(
    proyecto_id: int,
    archivo: UploadFile = File(...),  # ← NOMBRE CORRECTO: 'archivo' no 'archivo_csv'
    merge: bool = Form(True, description="Fusionar con datos existentes"),
    current_user: Usuario = Depends(get_current_analista_or_higher),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
) -> Any:
    """
    Cargar o actualizar padrón desde CSV
    """
    logger.info(f"Cargando padrón para proyecto ID: {proyecto_id}")
    
    try:
        # Verificar permisos
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id,
                ProyectoUsuario.rol_en_proyecto.in_(["SUPERADMIN", "ANALISTA"])
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para gestionar el padrón"
                )
        
        proyecto = db.query(Proyecto).filter(
            Proyecto.id == proyecto_id,
            Proyecto.is_deleted == False
        ).first()
        
        if not proyecto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado"
            )
        
        # Validar archivo - CORREGIR: el parámetro se llama 'archivo' no 'archivo_csv'
        if not archivo.filename or not archivo.filename.lower().endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser CSV"
            )
        
        # Leer contenido del archivo
        contenido = await archivo.read()
        contenido_decoded = contenido.decode('utf-8-sig')  # utf-8-sig maneja BOM
        
        # Parsear CSV
        datos, csv_columns = PadronManager.parse_csv_to_dict(contenido_decoded)
        
        if not datos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El CSV está vacío o no se pudo parsear"
            )
        
        # Validar estructura contra la definición del proyecto
        estructura_esperada = proyecto.estructura_padron["columnas"]
        valido, errores = PadronManager.validate_csv_structure(csv_columns, estructura_esperada)
        
        if not valido:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error en estructura CSV: {', '.join(errores)}"
            )
        
        # Insertar/actualizar en tabla dinámica
        result = PadronManager.insert_padron_data(proyecto.nombre_tabla_padron, datos, merge)
        
        # Registrar en bitácora
        bitacora = Bitacora(
            usuario_id=current_user.id,
            accion="SUBIR_PADRON",
            entidad="proyecto",
            entidad_id=proyecto.id,
            detalles={
                "archivo": archivo.filename,
                "registros": len(datos),
                "merge": merge,
                "resultado": result
            },
            ip=ip
        )
        db.add(bitacora)
        db.commit()
        
        logger.info(f"Padrón cargado: {len(datos)} registros para proyecto {proyecto.nombre}")
        
        return {
            "message": "Padrón cargado exitosamente",
            "registros_procesados": len(datos),
            "detalles": result,
            "proyecto": proyecto.nombre
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error cargando padrón: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando CSV: {str(e)}"
        )

@router.get("/{proyecto_id}/padron/estructura")
async def obtener_estructura_padron(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Obtener estructura del padrón
    """
    try:
        # Verificar permisos
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes acceso a este proyecto"
                )
        
        proyecto = db.query(Proyecto).filter(
            Proyecto.id == proyecto_id,
            Proyecto.is_deleted == False
        ).first()
        
        if not proyecto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado"
            )
        
        # Verificar que la tabla existe
        if not PadronManager.table_exists(proyecto.nombre_tabla_padron):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tabla de padrón no encontrada"
            )
        
        estructura = PadronManager.get_table_structure(proyecto.nombre_tabla_padron)
        muestra = PadronManager.get_sample_data(proyecto.nombre_tabla_padron, 5)
        
        return {
            "proyecto_id": proyecto_id,
            "nombre_proyecto": proyecto.nombre,
            "nombre_tabla": proyecto.nombre_tabla_padron,
            "estructura": estructura,
            "muestra": muestra,
            "total_columnas": len(estructura)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo estructura: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.get("/{proyecto_id}/padron/muestra")
async def obtener_muestra_padron(
    proyecto_id: int,
    limit: int = Query(10, ge=1, le=100),
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Obtener muestra de datos del padrón
    """
    try:
        # Verificar permisos
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes acceso a este proyecto"
                )
        
        proyecto = db.query(Proyecto).filter(
            Proyecto.id == proyecto_id,
            Proyecto.is_deleted == False
        ).first()
        
        if not proyecto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado"
            )
        
        # Verificar que la tabla existe
        if not PadronManager.table_exists(proyecto.nombre_tabla_padron):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tabla de padrón no encontrada"
            )
        
        datos = PadronManager.get_sample_data(proyecto.nombre_tabla_padron, limit)
        
        return {
            "proyecto_id": proyecto_id,
            "nombre_proyecto": proyecto.nombre,
            "muestra": datos,
            "total_registros": len(datos)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo muestra: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.post("/{proyecto_id}/usuarios")
async def asignar_usuario_proyecto(
    proyecto_id: int,
    usuario_id: int = Form(...),
    rol_en_proyecto: str = Form(..., description="Rol en el proyecto"),
    current_user: Usuario = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
) -> Any:
    """
    Asignar usuario a proyecto
    """
    logger.info(f"Asignando usuario {usuario_id} a proyecto {proyecto_id}")
    
    try:
        # Verificar que el proyecto existe
        proyecto = db.query(Proyecto).filter(
            Proyecto.id == proyecto_id,
            Proyecto.is_deleted == False
        ).first()
        
        if not proyecto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado"
            )
        
        # Verificar que el usuario existe
        usuario = db.query(Usuario).filter(
            Usuario.id == usuario_id,
            Usuario.is_active == True,
            Usuario.is_deleted == False
        ).first()
        
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Verificar rol válido
        if rol_en_proyecto not in ["SUPERADMIN", "ANALISTA", "AUXILIAR"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rol inválido. Debe ser: SUPERADMIN, ANALISTA o AUXILIAR"
            )
        
        # Verificar si ya está asignado
        existing = db.query(ProyectoUsuario).filter(
            ProyectoUsuario.proyecto_id == proyecto_id,
            ProyectoUsuario.usuario_id == usuario_id
        ).first()
        
        if existing:
            # Actualizar rol
            existing.rol_en_proyecto = rol_en_proyecto
            db.add(existing)
            accion = "ACTUALIZAR_ASIGNACION"
            mensaje = "Rol de usuario actualizado"
        else:
            # Crear asignación
            proyecto_usuario = ProyectoUsuario(
                proyecto_id=proyecto_id,
                usuario_id=usuario_id,
                rol_en_proyecto=rol_en_proyecto
            )
            db.add(proyecto_usuario)
            accion = "ASIGNAR_USUARIO"
            mensaje = "Usuario asignado al proyecto"
        
        # Registrar en bitácora
        bitacora = Bitacora(
            usuario_id=current_user.id,
            accion=accion,
            entidad="proyecto",
            entidad_id=proyecto_id,
            detalles={
                "usuario_id": usuario_id,
                "usuario_nombre": usuario.nombre_completo,
                "rol_asignado": rol_en_proyecto
            },
            ip=ip
        )
        db.add(bitacora)
        
        db.commit()
        
        return {
            "message": mensaje,
            "proyecto": proyecto.nombre,
            "usuario": usuario.nombre_completo,
            "rol": rol_en_proyecto
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error asignando usuario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.get("/{proyecto_id}/usuarios")
async def listar_usuarios_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_superadmin),
    db: Session = Depends(get_db)
) -> Any:
    """
    Listar usuarios asignados a un proyecto
    """
    try:
        proyecto = db.query(Proyecto).filter(
            Proyecto.id == proyecto_id,
            Proyecto.is_deleted == False
        ).first()
        
        if not proyecto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado"
            )
        
        # Obtener usuarios asignados
        usuarios = db.query(Usuario, ProyectoUsuario.rol_en_proyecto).join(
            ProyectoUsuario, Usuario.id == ProyectoUsuario.usuario_id
        ).filter(
            ProyectoUsuario.proyecto_id == proyecto_id,
            Usuario.is_active == True,
            Usuario.is_deleted == False
        ).all()
        
        resultado = []
        for usuario, rol_proyecto in usuarios:
            resultado.append({
                "id": usuario.id,
                "username": usuario.username,
                "email": usuario.email,
                "nombre_completo": usuario.nombre_completo,
                "rol_global": usuario.rol,
                "rol_en_proyecto": rol_proyecto,
                "last_login": usuario.last_login
            })
        
        return {
            "proyecto": proyecto.nombre,
            "total_usuarios": len(resultado),
            "usuarios": resultado
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listando usuarios: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.post("/crear-con-csv")
async def crear_proyecto_con_csv(
    nombre: str = Form(...),
    descripcion: Optional[str] = Form(None),
    archivo_csv: UploadFile = File(...),
    detectar_tipos: bool = Form(True, description="Detectar tipos de datos automáticamente"),
    current_user: Usuario = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
) -> Any:
    """
    Crear proyecto desde CSV (simplificado)
    """
    logger.info(f"Creando proyecto desde CSV: {nombre}")
    
    try:
        # Verificar si ya existe proyecto con ese nombre
        existing = db.query(Proyecto).filter(
            Proyecto.nombre == nombre,
            Proyecto.is_deleted == False
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un proyecto con ese nombre"
            )
        
        # Leer CSV
        contenido = await archivo_csv.read()
        contenido_decoded = contenido.decode('utf-8-sig')
        
        # Parsear CSV
        datos, csv_columns = PadronManager.parse_csv_to_dict(contenido_decoded)
        
        if not datos or not csv_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El CSV está vacío o no se pudo parsear"
            )
        
        # Verificar columnas obligatorias
        csv_columns_lower = [col.lower() for col in csv_columns]
        if 'cuenta' not in csv_columns_lower:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El CSV debe contener la columna 'cuenta'"
            )
        
        if 'nombre' not in csv_columns_lower:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El CSV debe contener la columna 'nombre'"
            )
        
        # Crear estructura de columnas
        columnas = []
        df = pd.read_csv(StringIO(contenido_decoded))
        
        for col in csv_columns:
            # Determinar tipo de dato
            if detectar_tipos and not df.empty:
                dtype = str(df[col].dtype)
                if 'int' in dtype:
                    tipo = "INT"
                elif 'float' in dtype:
                    tipo = "DECIMAL(10,2)"
                elif 'datetime' in dtype:
                    tipo = "DATE"
                else:
                    # Estimar longitud máxima
                    max_len = df[col].astype(str).str.len().max()
                    tipo = f"VARCHAR({min(max_len * 2, 255)})"
            else:
                tipo = "VARCHAR(255)"
            
            columnas.append({
                "nombre": col,
                "tipo": tipo,
                "es_obligatorio": col.lower() in ['cuenta', 'nombre'],
                "es_unico": col.lower() == 'cuenta'
            })
        
        # Generar UUID para el padrón
        padron_uuid = uuid.uuid4()
        
        # Crear tabla dinámica
        table_name, table_base_name = PadronManager.create_padron_table(str(padron_uuid), columnas)
        
        # Crear proyecto
        proyecto = Proyecto(
            nombre=nombre,
            descripcion=descripcion,
            nombre_tabla_padron=table_name,
            uuid_padron=padron_uuid,
            estructura_padron={"columnas": columnas}
        )
        
        db.add(proyecto)
        db.flush()
        
        # Asignar creador
        proyecto_usuario = ProyectoUsuario(
            proyecto_id=proyecto.id,
            usuario_id=current_user.id,
            rol_en_proyecto="SUPERADMIN"
        )
        db.add(proyecto_usuario)
        
        # Insertar datos
        result = PadronManager.insert_padron_data(table_name, datos, merge=False)
        
        # Registrar en bitácora
        bitacora = Bitacora(
            usuario_id=current_user.id,
            accion="CREAR_PROYECTO",
            entidad="proyecto",
            entidad_id=proyecto.id,
            detalles={
                "nombre": nombre,
                "archivo": archivo_csv.filename,
                "columnas": len(columnas),
                "registros": len(datos),
                "desde_csv": True
            },
            ip=ip
        )
        db.add(bitacora)
        
        db.commit()
        db.refresh(proyecto)
        
        logger.info(f"Proyecto creado desde CSV: {nombre} con {len(datos)} registros")
        
        return {
            "message": "Proyecto creado exitosamente desde CSV",
            "proyecto": proyecto,
            "datos_cargados": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creando proyecto desde CSV: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando proyecto: {str(e)}"
        )