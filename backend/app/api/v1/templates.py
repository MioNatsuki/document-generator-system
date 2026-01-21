# Endpoints de gestión de plantillas
import os
import uuid
import json
import tempfile
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path

from app.database import get_db
from app.models import Usuario, Proyecto, Plantilla, Bitacora, ProyectoUsuario
from app.schemas import PlantillaCreate, PlantillaUpdate, PlantillaInDB, MapeoPlaceholder, PaginatedResponse
from app.api.deps import get_current_active_user, get_current_analista_or_higher, get_ip_address
from app.core.template_manager import TemplateManager
from app.utils.file_handlers import FileHandler
from app.utils.logging import setup_logger
from app.utils.docx_processor import DocxProcessor
from app.utils.pdf_utils import PDFUtils

router = APIRouter()
logger = setup_logger(__name__)


@router.post("/", response_model=PlantillaInDB)
async def crear_plantilla(
    proyecto_id: int,
    nombre: str = Form(...),
    descripcion: Optional[str] = Form(None),
    archivo_docx: UploadFile = File(...),
    mapeos_json: str = Form(...),
    current_user: Usuario = Depends(get_current_analista_or_higher),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
) -> Any:
    """
    Crear nueva plantilla para un proyecto
    """
    logger.info(f"Creando nueva plantilla para proyecto ID: {proyecto_id}")

    try:
        # Verificar permisos en el proyecto
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id,
                ProyectoUsuario.rol_en_proyecto.in_(["SUPERADMIN", "ANALISTA"])
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para crear plantillas en este proyecto"
                )

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

        # Validar archivo DOCX
        if not archivo_docx.filename or not archivo_docx.filename.lower().endswith('.docx'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser DOCX"
            )

        # Parsear mapeos
        try:
            mapeos_data = json.loads(mapeos_json)
            mapeos = [MapeoPlaceholder(**item) for item in mapeos_data]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato de mapeos inválido: {str(e)}"
            )

        # Guardar archivo temporalmente
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / f"{uuid.uuid4()}.docx"
        
        try:
            # Guardar archivo subido
            content = await archivo_docx.read()
            with open(temp_path, "wb") as f:
                f.write(content)

            # Validar tamaño de página del DOCX
            is_valid, page_size = DocxProcessor.validate_page_size(temp_path)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El documento no tiene el tamaño de página correcto. Esperado: 21.59cm x 34.01cm (México Oficio), Obtenido: {page_size}"
                )

            # Extraer placeholders del documento
            placeholders = DocxProcessor.extract_placeholders(temp_path)
            logger.info(f"Placeholders extraídos: {placeholders}")

            # Convertir DOCX a PDF para vista previa
            pdf_path = temp_dir / f"{uuid.uuid4()}.pdf"
            success = DocxProcessor.convert_to_pdf(temp_path, pdf_path)
            
            if not success:
                logger.warning("No se pudo convertir DOCX a PDF, usando fallback")

            # Guardar archivos en ubicación permanente
            uploads_dir = Path("uploads/plantillas")
            uploads_dir.mkdir(parents=True, exist_ok=True)
            
            unique_id = uuid.uuid4()
            docx_filename = f"{unique_id}.docx"
            pdf_filename = f"{unique_id}.pdf"
            
            docx_final_path = uploads_dir / docx_filename
            pdf_final_path = uploads_dir / pdf_filename
            
            # Mover archivos a ubicación permanente
            temp_path.rename(docx_final_path)
            if pdf_path.exists():
                pdf_path.rename(pdf_final_path)
                pdf_path_str = str(pdf_final_path)
            else:
                pdf_path_str = None

            # Crear plantilla en BD
            plantilla = Plantilla(
                proyecto_id=proyecto_id,
                nombre=nombre,
                descripcion=descripcion,
                archivo_docx=str(docx_final_path),
                archivo_pdf_base=pdf_path_str,
                configuracion={
                    "mapeos": [m.dict() for m in mapeos],
                    "placeholders_detectados": placeholders
                },
                tamaño_pagina=page_size
            )
            
            db.add(plantilla)
            db.flush()

            # Registrar en bitácora
            bitacora = Bitacora(
                usuario_id=current_user.id,
                accion="CREAR_PLANTILLA",
                entidad="plantilla",
                entidad_id=plantilla.id,
                detalles={
                    "proyecto": proyecto.nombre,
                    "plantilla": nombre,
                    "mapeos": len(mapeos),
                    "placeholders": len(placeholders)
                },
                ip=ip
            )
            db.add(bitacora)
            db.commit()
            db.refresh(plantilla)

            logger.info(f"Plantilla creada exitosamente: {nombre} (ID: {plantilla.id})")
            return plantilla

        finally:
            # Limpiar archivos temporales
            if temp_path.exists():
                temp_path.unlink()
            if pdf_path.exists():
                pdf_path.unlink()
                
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error de base de datos al crear plantilla: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de base de datos"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado al crear plantilla: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )


@router.get("/", response_model=PaginatedResponse)
async def listar_plantillas(
    proyecto_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Listar plantillas de un proyecto
    """
    try:
        # Verificar acceso al proyecto
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

        query = db.query(Plantilla).filter(
            Plantilla.proyecto_id == proyecto_id,
            Plantilla.is_deleted == False
        )
        
        total = query.count()
        plantillas = query.offset(skip).limit(limit).all()

        return {
            "items": plantillas,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "size": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listando plantillas: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.get("/{plantilla_id}", response_model=PlantillaInDB)
async def obtener_plantilla(
    plantilla_id: int,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Obtener plantilla por ID
    """
    try:
        plantilla = db.query(Plantilla).filter(
            Plantilla.id == plantilla_id,
            Plantilla.is_deleted == False
        ).first()
        
        if not plantilla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plantilla no encontrada"
            )

        # Verificar acceso al proyecto de la plantilla
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == plantilla.proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes acceso a esta plantilla"
                )

        return plantilla
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo plantilla: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.put("/{plantilla_id}", response_model=PlantillaInDB)
async def actualizar_plantilla(
    plantilla_id: int,
    plantilla_update: PlantillaUpdate,
    current_user: Usuario = Depends(get_current_analista_or_higher),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
) -> Any:
    """
    Actualizar plantilla
    """
    logger.info(f"Actualizando plantilla ID: {plantilla_id}")

    try:
        plantilla = db.query(Plantilla).filter(
            Plantilla.id == plantilla_id,
            Plantilla.is_deleted == False
        ).first()
        
        if not plantilla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plantilla no encontrado"
            )

        # Verificar permisos en el proyecto
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == plantilla.proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id,
                ProyectoUsuario.rol_en_proyecto.in_(["SUPERADMIN", "ANALISTA"])
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para editar plantillas en este proyecto"
                )

        # Actualizar campos
        update_data = plantilla_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(plantilla, field):
                setattr(plantilla, field, value)

        db.add(plantilla)

        # Registrar en bitácora
        bitacora = Bitacora(
            usuario_id=current_user.id,
            accion="EDITAR_PLANTILLA",
            entidad="plantilla",
            entidad_id=plantilla.id,
            detalles={"cambios": update_data},
            ip=ip
        )
        db.add(bitacora)
        
        db.commit()
        db.refresh(plantilla)

        logger.info(f"Plantilla actualizada: {plantilla.nombre}")
        return plantilla
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error de base de datos al actualizar plantilla: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de base de datos"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado al actualizar plantilla: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.delete("/{plantilla_id}")
async def eliminar_plantilla(
    plantilla_id: int,
    current_user: Usuario = Depends(get_current_analista_or_higher),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
) -> Any:
    """
    Eliminar plantilla (soft delete)
    """
    logger.warning(f"Eliminando plantilla ID: {plantilla_id}")

    try:
        plantilla = db.query(Plantilla).filter(
            Plantilla.id == plantilla_id,
            Plantilla.is_deleted == False
        ).first()
        
        if not plantilla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plantilla no encontrada"
            )

        # Verificar permisos en el proyecto
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == plantilla.proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id,
                ProyectoUsuario.rol_en_proyecto.in_(["SUPERADMIN", "ANALISTA"])
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para eliminar plantillas en este proyecto"
                )

        # Soft delete
        plantilla.is_deleted = True

        # Registrar en bitácora
        bitacora = Bitacora(
            usuario_id=current_user.id,
            accion="ELIMINAR_PLANTILLA",
            entidad="plantilla",
            entidad_id=plantilla.id,
            detalles={"plantilla": plantilla.nombre},
            ip=ip
        )
        db.add(bitacora)
        
        db.commit()

        logger.info(f"Plantilla eliminada: {plantilla.nombre}")
        return {"message": f"Plantilla '{plantilla.nombre}' eliminada exitosamente"}
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error de base de datos al eliminar plantilla: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de base de datos"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado al eliminar plantilla: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.get("/{plantilla_id}/preview")
async def obtener_preview_plantilla(
    plantilla_id: int,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Obtener archivo PDF de la plantilla para vista previa
    """
    try:
        plantilla = db.query(Plantilla).filter(
            Plantilla.id == plantilla_id,
            Plantilla.is_deleted == False
        ).first()
        
        if not plantilla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plantilla no encontrada"
            )

        # Verificar acceso al proyecto
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == plantilla.proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes acceso a esta plantilla"
                )

        if not plantilla.archivo_pdf_base or not os.path.exists(plantilla.archivo_pdf_base):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Archivo PDF no encontrado"
            )

        return FileResponse(
            plantilla.archivo_pdf_base,
            media_type="application/pdf",
            filename=f"{plantilla.nombre}.pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo preview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.post("/{plantilla_id}/preview-data")
async def generar_preview_con_datos(
    plantilla_id: int,
    cuenta: Optional[str] = None,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Generar preview con datos reales del padrón
    """
    try:
        plantilla = db.query(Plantilla).filter(
            Plantilla.id == plantilla_id,
            Plantilla.is_deleted == False
        ).first()
        
        if not plantilla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plantilla no encontrada"
            )

        # Verificar acceso al proyecto
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == plantilla.proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes acceso a esta plantilla"
                )

        # Obtener datos de muestra del padrón
        from ...core.padron_manager import PadronManager
        
        if cuenta:
            # Obtener datos específicos para una cuenta
            query = f"SELECT * FROM {plantilla.proyecto.nombre_tabla_padron} WHERE cuenta = :cuenta AND is_deleted = false LIMIT 1"
            import textwrap
            from sqlalchemy import text
            with db.connection() as conn:
                result = conn.execute(text(query), {"cuenta": cuenta}).fetchone()
                if result:
                    data = dict(result._mapping)
                else:
                    # Obtener cualquier dato de muestra
                    muestra = PadronManager.get_sample_data(plantilla.proyecto.nombre_tabla_padron, 1)
                    data = muestra[0] if muestra else {}
        else:
            # Obtener un registro aleatorio
            muestra = PadronManager.get_sample_data(plantilla.proyecto.nombre_tabla_padron, 1)
            data = muestra[0] if muestra else {}

        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay datos en el padrón para generar preview"
            )

        # Generar PDF de prueba
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        
        pdf_path = temp_dir / f"preview_{uuid.uuid4()}.pdf"
        
        # Usar TemplateManager para generar PDF
        success = TemplateManager.generate_test_pdf(
            plantilla.archivo_docx,
            plantilla.configuracion.get("mapeos", []),
            data,
            pdf_path
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo generar el PDF de prueba"
            )

        # Leer PDF como bytes
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        # Eliminar archivo temporal
        pdf_path.unlink()

        return {
            "pdf_base64": pdf_bytes.hex(),  # Enviar como hex para JSON
            "datos_usados": data,
            "plantilla": plantilla.nombre
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando preview con datos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando preview: {str(e)}"
        )


@router.get("/{plantilla_id}/placeholders")
async def obtener_placeholders_plantilla(
    plantilla_id: int,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Obtener placeholders detectados en la plantilla
    """
    try:
        plantilla = db.query(Plantilla).filter(
            Plantilla.id == plantilla_id,
            Plantilla.is_deleted == False
        ).first()
        
        if not plantilla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plantilla no encontrada"
            )

        # Verificar acceso al proyecto
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == plantilla.proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes acceso a esta plantilla"
                )

        placeholders = plantilla.configuracion.get("placeholders_detectados", [])
        mapeos = plantilla.configuracion.get("mapeos", [])

        return {
            "plantilla_id": plantilla_id,
            "plantilla_nombre": plantilla.nombre,
            "placeholders_detectados": placeholders,
            "mapeos_configurados": mapeos,
            "total_placeholders": len(placeholders),
            "total_mapeos": len(mapeos)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo placeholders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


@router.post("/{plantilla_id}/validate-size")
async def validar_tamaño_plantilla(
    plantilla_id: int,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Validar tamaño de página de la plantilla
    """
    try:
        plantilla = db.query(Plantilla).filter(
            Plantilla.id == plantilla_id,
            Plantilla.is_deleted == False
        ).first()
        
        if not plantilla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plantilla no encontrada"
            )

        # Verificar acceso al proyecto
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == plantilla.proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes acceso a esta plantilla"
                )

        # Validar tamaño del PDF si existe
        validation_result = {
            "plantilla_id": plantilla_id,
            "plantilla_nombre": plantilla.nombre,
            "tamaño_configurado": plantilla.tamaño_pagina,
            "es_valido": False,
            "errores": [],
            "advertencias": []
        }

        if plantilla.archivo_pdf_base and os.path.exists(plantilla.archivo_pdf_base):
            # Validar tamaño del PDF
            is_valid, errors, warnings = PDFUtils.validate_pdf_size(plantilla.archivo_pdf_base)
            
            validation_result["es_valido"] = is_valid
            validation_result["errores"] = errors
            validation_result["advertencias"] = warnings
        else:
            validation_result["errores"].append("No se encontró archivo PDF para validar")

        return validation_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validando tamaño: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )
