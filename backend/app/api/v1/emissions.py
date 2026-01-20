"""
Endpoints para gestión de emisiones
"""
import os
import uuid
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
import tempfile
import logging

from ...database import get_db
from ...models import Usuario, Proyecto, Plantilla, Bitacora, ProyectoUsuario
from ...schemas import EmisionRequest, EmisionCSVData, EmisionInDB
from ...api.deps import get_current_active_user, get_ip_address, require_project_access
from ...core.emission_engine import EmissionEngine
from ...utils.file_handlers import FileHandler
from ...utils.logging import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.post("/procesar-emision")
async def procesar_emision(
    proyecto_id: int,
    plantilla_id: int,
    documento: str = Form(..., description="Tipo de documento (N, A, E, CI)"),
    pmo: str = Form(..., description="PMO para la emisión (ej: 'PMO 1')"),
    fecha_emision: datetime = Form(..., description="Fecha de emisión"),
    archivo_csv: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    ip: str = Depends(get_ip_address)
):
    """
    Procesar emisión masiva desde CSV
    """
    logger.info(f"Iniciando procesamiento de emisión para proyecto {proyecto_id}")
    
    try:
        # Verificar permisos en el proyecto
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
        
        # Verificar que la plantilla existe
        plantilla = db.query(Plantilla).filter(
            Plantilla.id == plantilla_id,
            Plantilla.is_deleted == False,
            Plantilla.proyecto_id == proyecto_id
        ).first()
        
        if not plantilla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plantilla no encontrada o no pertenece al proyecto"
            )
        
        # Validar archivo CSV
        if not archivo_csv.filename or not archivo_csv.filename.lower().endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser CSV"
            )
        
        # Crear directorio temporal para el archivo
        temp_dir = Path(tempfile.gettempdir()) / "emisiones"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = temp_dir / f"{uuid.uuid4()}.csv"
        
        try:
            # Guardar archivo temporalmente
            content = await archivo_csv.read()
            with open(csv_path, "wb") as f:
                f.write(content)
            
            # Validar tamaño del archivo
            file_size = csv_path.stat().st_size
            max_size = 50 * 1024 * 1024  # 50MB
            
            if file_size > max_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El archivo es demasiado grande ({file_size / 1024 / 1024:.1f} MB). Máximo: 50 MB"
                )
            
            # Inicializar motor de emisión
            engine = EmissionEngine(
                db=db,
                proyecto_id=proyecto_id,
                plantilla_id=plantilla_id,
                usuario_id=current_user.id,
                documento=documento,
                pmo=pmo,
                fecha_emision=fecha_emision
            )
            
            # Procesar emisión
            resultados = engine.process_complete_emission(csv_path)
            
            # Registrar en bitácora
            bitacora = Bitacora(
                usuario_id=current_user.id,
                accion="INICIAR_EMISION",
                entidad="proyecto",
                entidad_id=proyecto_id,
                detalles={
                    "plantilla_id": plantilla_id,
                    "documento": documento,
                    "pmo": pmo,
                    "archivo": archivo_csv.filename,
                    "resultados": resultados
                },
                ip=ip
            )
            db.add(bitacora)
            db.commit()
            
            logger.info(f"Emisión procesada: {resultados['pdfs_generados']} PDFs generados")
            
            # Generar reporte de cuentas no encontradas si hay
            report_path = None
            if resultados.get('cuentas_no_encontradas'):
                output_dir = Path(".") / "reports"
                output_dir.mkdir(exist_ok=True)
                report_path = engine.generate_missing_accounts_report(
                    resultados['cuentas_no_encontradas'],
                    output_dir
                )
            
            # Preparar respuesta
            response_data = {
                "mensaje": "Emisión procesada exitosamente",
                "sesion_id": resultados['sesion_id'],
                "resumen": {
                    "total_registros": resultados['total_registros'],
                    "registros_procesados": resultados['registros_procesados'],
                    "pdfs_generados": resultados['pdfs_generados'],
                    "cuentas_no_encontradas": len(resultados.get('cuentas_no_encontradas', [])),
                    "tiempo_segundos": resultados.get('tiempo_procesamiento', 0),
                    "pdfs_por_segundo": resultados.get('pdfs_por_segundo', 0)
                },
                "ruta_salida": resultados.get('ruta_salida', ''),
                "reporte_cuentas_no_encontradas": str(report_path) if report_path else None
            }
            
            if resultados.get('errores'):
                response_data['errores'] = resultados['errores'][:10]  # Solo primeros 10 errores
            
            return JSONResponse(content=response_data, status_code=status.HTTP_200_OK)
            
        finally:
            # Limpiar archivo temporal
            if csv_path.exists():
                csv_path.unlink()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando emisión: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando emisión: {str(e)}"
        )


@router.post("/preprocesar-csv")
async def preprocesar_csv(
    proyecto_id: int,
    archivo_csv: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Preprocesar CSV para validar cuentas antes de la emisión
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
        
        # Validar archivo
        if not archivo_csv.filename or not archivo_csv.filename.lower().endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser CSV"
            )
        
        # Guardar temporalmente
        temp_dir = Path(tempfile.gettempdir()) / "emisiones"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = temp_dir / f"preproceso_{uuid.uuid4()}.csv"
        
        try:
            content = await archivo_csv.read()
            with open(csv_path, "wb") as f:
                f.write(content)
            
            # Cargar CSV usando el motor
            engine = EmissionEngine(
                db=db,
                proyecto_id=proyecto_id,
                plantilla_id=0,  # No necesitamos plantilla para preproceso
                usuario_id=current_user.id,
                documento="PREPROCESO",
                pmo="PMO 0",
                fecha_emision=datetime.now()
            )
            
            registros_csv, cuentas_csv = engine.load_emission_csv(csv_path)
            
            # Hacer matching
            datos_padron, cuentas_no_encontradas = engine.match_with_padron(cuentas_csv)
            
            # Preparar respuesta
            response = {
                "archivo": archivo_csv.filename,
                "total_registros": len(registros_csv),
                "cuentas_unicas": len(cuentas_csv),
                "cuentas_encontradas": len(datos_padron),
                "cuentas_no_encontradas": len(cuentas_no_encontradas),
                "lista_cuentas_no_encontradas": cuentas_no_encontradas[:100],  # Limitar a 100
                "porcentaje_exito": (len(datos_padron) / len(cuentas_csv) * 100) if cuentas_csv else 0
            }
            
            if cuentas_no_encontradas:
                response['advertencia'] = f"{len(cuentas_no_encontradas)} cuentas no se encontraron en el padrón"
            
            return response
            
        finally:
            if csv_path.exists():
                csv_path.unlink()
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error preprocesando CSV: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error preprocesando CSV: {str(e)}"
        )


@router.get("/estado/{sesion_id}")
async def obtener_estado_emision(
    sesion_id: str,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Obtener estado de una emisión por sesión ID
    """
    try:
        # Buscar emisiones finales de esta sesión
        from ...models import EmisionFinal
        emisiones = db.query(EmisionFinal).filter(
            EmisionFinal.sesion_id == sesion_id
        ).all()
        
        if not emisiones:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión de emisión no encontrada"
            )
        
        # Verificar permisos (primera emisión para obtener proyecto)
        primera_emision = emisiones[0]
        
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == primera_emision.proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes acceso a esta emisión"
                )
        
        # Contar por estado
        total = len(emisiones)
        generados = sum(1 for e in emisiones if e.is_generado)
        fallidos = sum(1 for e in emisiones if e.error)
        
        # Obtener detalles de errores
        errores = []
        for emision in emisiones:
            if emision.error:
                errores.append({
                    'cuenta': emision.cuenta,
                    'error': emision.error[:100]  # Limitar longitud
                })
        
        # Obtener proyecto y plantilla
        proyecto = db.query(Proyecto).filter(Proyecto.id == primera_emision.proyecto_id).first()
        plantilla = db.query(Plantilla).filter(Plantilla.id == primera_emision.plantilla_id).first()
        
        return {
            'sesion_id': sesion_id,
            'proyecto': proyecto.nombre if proyecto else 'Desconocido',
            'plantilla': plantilla.nombre if plantilla else 'Desconocido',
            'estadisticas': {
                'total': total,
                'generados': generados,
                'fallidos': fallidos,
                'porcentaje_exito': (generados / total * 100) if total > 0 else 0
            },
            'documento': primera_emision.documento,
            'pmo': primera_emision.pmo,
            'fecha_emision': primera_emision.fecha_emision,
            'errores': errores[:10],  # Limitar a 10 errores
            'ruta_salida': emisiones[0].ruta_archivo_pdf if emisiones[0].ruta_archivo_pdf else ''
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo estado de emisión: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado: {str(e)}"
        )


@router.get("/descargar-zip/{sesion_id}")
async def descargar_emision_zip(
    sesion_id: str,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Descargar emisión completa como archivo ZIP
    """
    try:
        # Buscar emisiones de esta sesión
        from ...models import EmisionAcumulada
        emisiones = db.query(EmisionAcumulada).filter(
            EmisionAcumulada.sesion_id == sesion_id
        ).limit(1).all()
        
        if not emisiones:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión de emisión no encontrada"
            )
        
        primera_emision = emisiones[0]
        
        # Verificar permisos
        if current_user.rol != "SUPERADMIN":
            proyecto_usuario = db.query(ProyectoUsuario).filter(
                ProyectoUsuario.proyecto_id == primera_emision.proyecto_id,
                ProyectoUsuario.usuario_id == current_user.id
            ).first()
            
            if not proyecto_usuario:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes acceso a esta emisión"
                )
        
        # Verificar si existe el directorio de salida
        ruta_base = Path(primera_emision.ruta_archivo_pdf).parent if primera_emision.ruta_archivo_pdf else None
        
        if not ruta_base or not ruta_base.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Los archivos de emisión no están disponibles"
            )
        
        # Crear archivo ZIP (en producción, esto sería más sofisticado)
        import zipfile
        from io import BytesIO
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Agregar archivos PDF
            pdf_files = list(ruta_base.glob("*.pdf"))
            for pdf_file in pdf_files:
                zip_file.write(pdf_file, pdf_file.name)
            
            # Agregar archivo de resumen
            resumen_content = f"Resumen de Emisión\nSesión: {sesion_id}\n"
            zip_file.writestr("RESUMEN.txt", resumen_content)
        
        zip_buffer.seek(0)
        
        # Nombre del archivo ZIP
        fecha_str = primera_emision.fecha_emision.strftime("%Y%m%d")
        zip_filename = f"emision_{primera_emision.proyecto_id}_{fecha_str}_{sesion_id[:8]}.zip"
        
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando ZIP de emisión: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando ZIP: {str(e)}"
        )


@router.post("/generar-prueba")
async def generar_prueba_pdf(
    proyecto_id: int,
    plantilla_id: int,
    cuenta: str = Form(...),
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generar PDF de prueba con datos reales
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
        
        plantilla = db.query(Plantilla).filter(
            Plantilla.id == plantilla_id,
            Plantilla.is_deleted == False,
            Plantilla.proyecto_id == proyecto_id
        ).first()
        
        if not plantilla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plantilla no encontrada"
            )
        
        # Buscar datos del padrón para la cuenta
        table_name = proyecto.nombre_tabla_padron
        sql = f"SELECT * FROM {table_name} WHERE cuenta = :cuenta AND is_deleted = false LIMIT 1"
        
        result = db.execute(text(sql), {"cuenta": cuenta}).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cuenta {cuenta} no encontrada en el padrón"
            )
        
        datos_padron = dict(result._mapping)
        
        # Inicializar motor para cálculos
        engine = EmissionEngine(
            db=db,
            proyecto_id=proyecto_id,
            plantilla_id=plantilla_id,
            usuario_id=current_user.id,
            documento="PRUEBA",
            pmo="PMO 0",
            fecha_emision=datetime.now()
        )
        
        # Calcular campos automáticos
        campos_calculados = engine.calculate_automatic_fields(cuenta, datos_padron)
        datos_completos = {**datos_padron, **campos_calculados}
        
        # Generar PDF de prueba
        from ...utils.pdf_generator import PDFGenerator
        pdf_generator = PDFGenerator()
        
        temp_dir = Path(tempfile.gettempdir()) / "pruebas"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_path = temp_dir / f"prueba_{cuenta}_{uuid.uuid4()[:8]}.pdf"
        
        success = pdf_generator.generate_test_pdf(
            output_path=pdf_path,
            data=datos_completos,
            template_config=plantilla.configuracion
        )
        
        if not success or not pdf_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo generar el PDF de prueba"
            )
        
        # Devolver archivo
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"prueba_{cuenta}.pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generando PDF de prueba: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando PDF de prueba: {str(e)}"
        )