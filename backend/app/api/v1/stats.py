"""
Endpoints de estadísticas y dashboard
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_, or_, case
from sqlalchemy.sql import extract
import json
import pandas as pd
from io import StringIO

from ...database import get_db
from ...models import (
    Usuario, Proyecto, Plantilla, EmisionAcumulada, 
    Bitacora, ProyectoUsuario
)
from ...schemas import PaginatedResponse
from ...api.deps import (
    get_current_active_user, get_current_superadmin,
    get_current_analista_or_higher, get_ip_address
)
from ...utils.logging import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


def apply_date_filter(query, model, date_filter: str = None, 
                     start_date: datetime = None, end_date: datetime = None):
    """
    Aplicar filtro de fechas a una consulta
    """
    if date_filter == "today":
        today = datetime.now().date()
        query = query.filter(
            func.date(model.created_at) == today
        )
    elif date_filter == "7d":
        week_ago = datetime.now() - timedelta(days=7)
        query = query.filter(
            model.created_at >= week_ago
        )
    elif date_filter == "30d":
        month_ago = datetime.now() - timedelta(days=30)
        query = query.filter(
            model.created_at >= month_ago
        )
    elif date_filter == "custom" and start_date and end_date:
        query = query.filter(
            model.created_at >= start_date,
            model.created_at <= end_date
        )
    
    return query


@router.get("/dashboard/kpis")
async def get_dashboard_kpis(
    proyecto_id: Optional[int] = None,
    date_filter: str = Query("30d", regex="^(today|7d|30d|custom)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Obtener KPIs principales para el dashboard
    """
    try:
        # Construir consulta base según permisos
        base_query = db.query(EmisionAcumulada)
        
        # Filtrar por proyecto si se especifica y el usuario tiene acceso
        if proyecto_id:
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
            base_query = base_query.filter(
                EmisionAcumulada.proyecto_id == proyecto_id
            )
        elif current_user.rol != "SUPERADMIN":
            # Para no superadmins, solo sus proyectos
            proyecto_ids = [
                pu.proyecto_id for pu in 
                db.query(ProyectoUsuario.proyecto_id).filter(
                    ProyectoUsuario.usuario_id == current_user.id
                ).all()
            ]
            if proyecto_ids:
                base_query = base_query.filter(
                    EmisionAcumulada.proyecto_id.in_(proyecto_ids)
                )
            else:
                # Si no tiene proyectos, retornar vacío
                return {
                    "total_pdfs": 0,
                    "pdfs_mes_actual": 0,
                    "pdfs_mes_anterior": 0,
                    "eficiencia": 0,
                    "usuarios_activos": 0,
                    "proyectos_activos": 0,
                    "tendencia": 0
                }
        
        # Aplicar filtro de fechas
        base_query = apply_date_filter(base_query, EmisionAcumulada, date_filter, start_date, end_date)
        
        # KPI 1: Total de PDFs generados (en el período)
        total_pdfs = base_query.count()
        
        # KPI 2: PDFs del mes actual vs mes anterior
        now = datetime.now()
        mes_actual_inicio = datetime(now.year, now.month, 1)
        mes_anterior_inicio = (mes_actual_inicio - timedelta(days=1)).replace(day=1)
        
        pdfs_mes_actual = base_query.filter(
            EmisionAcumulada.fecha_generacion >= mes_actual_inicio
        ).count()
        
        pdfs_mes_anterior = base_query.filter(
            EmisionAcumulada.fecha_generacion >= mes_anterior_inicio,
            EmisionAcumulada.fecha_generacion < mes_actual_inicio
        ).count()
        
        # KPI 3: Eficiencia (PDFs por segundo en el período)
        if date_filter in ["7d", "30d", "custom"]:
            # Obtener tiempo total del período
            if date_filter == "7d":
                periodo_dias = 7
            elif date_filter == "30d":
                periodo_dias = 30
            else:  # custom
                if start_date and end_date:
                    periodo_dias = (end_date - start_date).days + 1
                else:
                    periodo_dias = 30
            
            # Calcular eficiencia (asumiendo 8 horas de trabajo al día)
            horas_trabajo = periodo_dias * 8
            if horas_trabajo > 0:
                eficiencia = total_pdfs / horas_trabajo
            else:
                eficiencia = 0
        else:
            eficiencia = 0
        
        # KPI 4: Usuarios activos (que han generado PDFs en el período)
        usuarios_activos = db.query(
            func.count(func.distinct(EmisionAcumulada.usuario_id))
        ).select_from(EmisionAcumulada)
        
        if proyecto_id:
            usuarios_activos = usuarios_activos.filter(
                EmisionAcumulada.proyecto_id == proyecto_id
            )
        
        usuarios_activos = apply_date_filter(
            usuarios_activos, EmisionAcumulada, date_filter, start_date, end_date
        ).scalar() or 0
        
        # KPI 5: Proyectos activos
        proyectos_activos = db.query(
            func.count(func.distinct(EmisionAcumulada.proyecto_id))
        ).select_from(EmisionAcumulada)
        
        proyectos_activos = apply_date_filter(
            proyectos_activos, EmisionAcumulada, date_filter, start_date, end_date
        ).scalar() or 0
        
        # Calcular tendencia (crecimiento vs período anterior)
        if pdfs_mes_anterior > 0:
            tendencia = ((pdfs_mes_actual - pdfs_mes_anterior) / pdfs_mes_anterior) * 100
        else:
            tendencia = 100 if pdfs_mes_actual > 0 else 0
        
        return {
            "total_pdfs": total_pdfs,
            "pdfs_mes_actual": pdfs_mes_actual,
            "pdfs_mes_anterior": pdfs_mes_anterior,
            "eficiencia": round(eficiencia, 2),
            "usuarios_activos": usuarios_activos,
            "proyectos_activos": proyectos_activos,
            "tendencia": round(tendencia, 2),
            "periodo": date_filter,
            "fecha_consulta": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo KPIs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo KPIs: {str(e)}"
        )


@router.get("/dashboard/emisiones-tiempo")
async def get_emisiones_tiempo(
    proyecto_id: Optional[int] = None,
    date_filter: str = Query("30d", regex="^(today|7d|30d|custom)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    agrupacion: str = Query("day", regex="^(hour|day|week|month)$"),
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Obtener datos para gráfica de emisiones en el tiempo
    """
    try:
        # Construir consulta base según permisos
        base_query = db.query(
            func.date_trunc(agrupacion, EmisionAcumulada.fecha_generacion).label('periodo'),
            func.count().label('total')
        ).group_by('periodo').order_by('periodo')
        
        # Filtrar por proyecto si se especifica
        if proyecto_id:
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
            base_query = base_query.filter(
                EmisionAcumulada.proyecto_id == proyecto_id
            )
        elif current_user.rol != "SUPERADMIN":
            # Para no superadmins, solo sus proyectos
            proyecto_ids = [
                pu.proyecto_id for pu in 
                db.query(ProyectoUsuario.proyecto_id).filter(
                    ProyectoUsuario.usuario_id == current_user.id
                ).all()
            ]
            if proyecto_ids:
                base_query = base_query.filter(
                    EmisionAcumulada.proyecto_id.in_(proyecto_ids)
                )
            else:
                return []
        
        # Aplicar filtro de fechas
        base_query = apply_date_filter(base_query, EmisionAcumulada, date_filter, start_date, end_date)
        
        # Ejecutar consulta
        resultados = base_query.all()
        
        # Formatear respuesta
        datos = []
        for periodo, total in resultados:
            datos.append({
                "periodo": periodo.isoformat() if periodo else "",
                "total": total,
                "periodo_display": format_period(periodo, agrupacion)
            })
        
        return datos
        
    except Exception as e:
        logger.error(f"Error obteniendo emisiones en tiempo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo datos: {str(e)}"
        )


def format_period(periodo, agrupacion):
    """Formatear período para display"""
    if not periodo:
        return ""
    
    if agrupacion == "hour":
        return periodo.strftime("%H:%M")
    elif agrupacion == "day":
        return periodo.strftime("%d/%m")
    elif agrupacion == "week":
        semana = periodo.isocalendar()[1]
        return f"Sem {semana}"
    elif agrupacion == "month":
        return periodo.strftime("%b")
    return str(periodo)


@router.get("/dashboard/distribucion-documentos")
async def get_distribucion_documentos(
    proyecto_id: Optional[int] = None,
    date_filter: str = Query("30d", regex="^(today|7d|30d|custom)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Obtener distribución por tipo de documento
    """
    try:
        # Construir consulta base
        base_query = db.query(
            EmisionAcumulada.documento,
            func.count().label('total'),
            func.round(
                func.count() * 100.0 / func.sum(func.count()).over(), 2
            ).label('porcentaje')
        ).group_by(EmisionAcumulada.documento).order_by(func.count().desc())
        
        # Filtrar por proyecto si se especifica
        if proyecto_id:
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
            base_query = base_query.filter(
                EmisionAcumulada.proyecto_id == proyecto_id
            )
        elif current_user.rol != "SUPERADMIN":
            # Para no superadmins, solo sus proyectos
            proyecto_ids = [
                pu.proyecto_id for pu in 
                db.query(ProyectoUsuario.proyecto_id).filter(
                    ProyectoUsuario.usuario_id == current_user.id
                ).all()
            ]
            if proyecto_ids:
                base_query = base_query.filter(
                    EmisionAcumulada.proyecto_id.in_(proyecto_ids)
                )
            else:
                return []
        
        # Aplicar filtro de fechas
        base_query = apply_date_filter(base_query, EmisionAcumulada, date_filter, start_date, end_date)
        
        # Ejecutar consulta
        resultados = base_query.all()
        
        # Formatear respuesta
        datos = []
        for documento, total, porcentaje in resultados:
            datos.append({
                "documento": documento,
                "total": total,
                "porcentaje": float(porcentaje) if porcentaje else 0
            })
        
        return datos
        
    except Exception as e:
        logger.error(f"Error obteniendo distribución: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo distribución: {str(e)}"
        )


@router.get("/dashboard/productividad-usuarios")
async def get_productividad_usuarios(
    proyecto_id: Optional[int] = None,
    date_filter: str = Query("30d", regex="^(today|7d|30d|custom)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(10, ge=1, le=50),
    current_user: Usuario = Depends(get_current_superadmin),  # Solo superadmin
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Obtener productividad por usuario (solo para Superadmin)
    """
    try:
        # Consulta para productividad
        base_query = db.query(
            Usuario.username,
            Usuario.nombre_completo,
            Usuario.rol,
            func.count(EmisionAcumulada.id).label('total_pdfs'),
            func.round(
                func.avg(
                    case(
                        (EmisionAcumulada.tamaño_archivo.isnot(None), EmisionAcumulada.tamaño_archivo),
                        else_=0
                    )
                ) / 1024.0, 2  # Convertir a KB
            ).label('tamaño_promedio_kb'),
            func.max(EmisionAcumulada.fecha_generacion).label('ultima_actividad')
        ).join(
            EmisionAcumulada, Usuario.id == EmisionAcumulada.usuario_id
        ).group_by(
            Usuario.id, Usuario.username, Usuario.nombre_completo, Usuario.rol
        ).order_by(func.count(EmisionAcumulada.id).desc()).limit(limit)
        
        # Filtrar por proyecto si se especifica
        if proyecto_id:
            base_query = base_query.filter(
                EmisionAcumulada.proyecto_id == proyecto_id
            )
        
        # Aplicar filtro de fechas
        base_query = apply_date_filter(base_query, EmisionAcumulada, date_filter, start_date, end_date)
        
        # Ejecutar consulta
        resultados = base_query.all()
        
        # Formatear respuesta
        datos = []
        for username, nombre, rol, total, tamaño, ultima in resultados:
            datos.append({
                "username": username,
                "nombre_completo": nombre,
                "rol": rol,
                "total_pdfs": total,
                "tamaño_promedio_kb": float(tamaño) if tamaño else 0,
                "ultima_actividad": ultima.isoformat() if ultima else None
            })
        
        return datos
        
    except Exception as e:
        logger.error(f"Error obteniendo productividad: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo productividad: {str(e)}"
        )


@router.get("/bitacora")
async def get_bitacora(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    usuario_id: Optional[int] = None,
    accion: Optional[str] = None,
    entidad: Optional[str] = None,
    date_filter: str = Query("30d", regex="^(today|7d|30d|custom)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search: Optional[str] = None,
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Obtener registros de bitácora con filtros
    """
    try:
        # Construir consulta base
        query = db.query(Bitacora).join(Usuario, Bitacora.usuario_id == Usuario.id)
        
        # Si no es superadmin, solo ver sus propios registros
        if current_user.rol != "SUPERADMIN":
            query = query.filter(Bitacora.usuario_id == current_user.id)
        
        # Aplicar filtros
        if usuario_id:
            query = query.filter(Bitacora.usuario_id == usuario_id)
        
        if accion:
            query = query.filter(Bitacora.accion.ilike(f"%{accion}%"))
        
        if entidad:
            query = query.filter(Bitacora.entidad == entidad)
        
        if search:
            search_filter = or_(
                Usuario.username.ilike(f"%{search}%"),
                Usuario.nombre_completo.ilike(f"%{search}%"),
                Bitacora.accion.ilike(f"%{search}%"),
                Bitacora.detalles.cast(text).ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        # Aplicar filtro de fechas
        query = apply_date_filter(query, Bitacora, date_filter, start_date, end_date)
        
        # Obtener total y registros
        total = query.count()
        registros = query.order_by(
            Bitacora.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        # Formatear respuesta
        items = []
        for registro in registros:
            items.append({
                "id": registro.id,
                "fecha": registro.created_at.isoformat() if registro.created_at else None,
                "usuario": {
                    "id": registro.usuario.id if registro.usuario else None,
                    "username": registro.usuario.username if registro.usuario else None,
                    "nombre_completo": registro.usuario.nombre_completo if registro.usuario else None
                },
                "accion": registro.accion,
                "entidad": registro.entidad,
                "entidad_id": registro.entidad_id,
                "detalles": registro.detalles,
                "ip": registro.ip
            })
        
        return {
            "items": items,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "size": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 1
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo bitácora: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo bitácora: {str(e)}"
        )


@router.post("/bitacora/export")
async def export_bitacora(
    filters: Dict[str, Any],
    format: str = Query("csv", regex="^(csv|json)$"),
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Exportar bitácora a CSV o JSON
    """
    try:
        # Reconstruir filtros desde el request
        query = db.query(Bitacora).join(Usuario, Bitacora.usuario_id == Usuario.id)
        
        # Aplicar mismos filtros que en GET
        if current_user.rol != "SUPERADMIN":
            query = query.filter(Bitacora.usuario_id == current_user.id)
        
        if filters.get('usuario_id'):
            query = query.filter(Bitacora.usuario_id == filters['usuario_id'])
        
        if filters.get('accion'):
            query = query.filter(Bitacora.accion.ilike(f"%{filters['accion']}%"))
        
        if filters.get('entidad'):
            query = query.filter(Bitacora.entidad == filters['entidad'])
        
        if filters.get('search'):
            search_filter = or_(
                Usuario.username.ilike(f"%{filters['search']}%"),
                Usuario.nombre_completo.ilike(f"%{filters['search']}%"),
                Bitacora.accion.ilike(f"%{filters['search']}%"),
                Bitacora.detalles.cast(text).ilike(f"%{filters['search']}%")
            )
            query = query.filter(search_filter)
        
        # Aplicar filtro de fechas
        date_filter = filters.get('date_filter', '30d')
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        query = apply_date_filter(query, Bitacora, date_filter, start_date, end_date)
        
        # Obtener todos los registros (sin paginación)
        registros = query.order_by(Bitacora.created_at.desc()).all()
        
        # Preparar datos
        data = []
        for registro in registros:
            data.append({
                "Fecha": registro.created_at.isoformat() if registro.created_at else "",
                "Usuario": registro.usuario.username if registro.usuario else "",
                "Nombre": registro.usuario.nombre_completo if registro.usuario else "",
                "Acción": registro.accion,
                "Entidad": registro.entidad or "",
                "ID Entidad": registro.entidad_id or "",
                "Detalles": json.dumps(registro.detalles) if registro.detalles else "",
                "IP": registro.ip or ""
            })
        
        if format == "csv":
            # Convertir a CSV
            df = pd.DataFrame(data)
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()
            
            return {
                "content": csv_content,
                "filename": f"bitacora_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "mime_type": "text/csv"
            }
        else:  # json
            return {
                "content": json.dumps(data, indent=2, ensure_ascii=False),
                "filename": f"bitacora_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "mime_type": "application/json"
            }
        
    except Exception as e:
        logger.error(f"Error exportando bitácora: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exportando bitácora: {str(e)}"
        )


@router.get("/stats/detalladas")
async def get_stats_detalladas(
    proyecto_id: Optional[int] = None,
    date_filter: str = Query("30d", regex="^(today|7d|30d|custom)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    group_by: str = Query("day", regex="^(day|week|month|documento|usuario)$"),
    current_user: Usuario = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Obtener estadísticas detalladas con agrupaciones
    """
    try:
        # Determinar campo de agrupación
        if group_by == "documento":
            group_field = EmisionAcumulada.documento
        elif group_by == "usuario":
            group_field = Usuario.username
        else:  # day, week, month
            group_field = func.date_trunc(group_by, EmisionAcumulada.fecha_generacion)
        
        # Construir consulta base
        query = db.query(
            group_field.label('grupo'),
            func.count().label('total'),
            func.sum(EmisionAcumulada.tamaño_archivo).label('tamaño_total'),
            func.avg(EmisionAcumulada.tamaño_archivo).label('tamaño_promedio')
        )
        
        # Joins necesarios
        if group_by == "usuario":
            query = query.join(Usuario, EmisionAcumulada.usuario_id == Usuario.id)
        
        # Filtrar por proyecto si se especifica
        if proyecto_id:
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
            query = query.filter(EmisionAcumulada.proyecto_id == proyecto_id)
        elif current_user.rol != "SUPERADMIN":
            # Para no superadmins, solo sus proyectos
            proyecto_ids = [
                pu.proyecto_id for pu in 
                db.query(ProyectoUsuario.proyecto_id).filter(
                    ProyectoUsuario.usuario_id == current_user.id
                ).all()
            ]
            if proyecto_ids:
                query = query.filter(EmisionAcumulada.proyecto_id.in_(proyecto_ids))
            else:
                return {"grupos": [], "total_general": 0, "tamaño_total_general": 0}
        
        # Aplicar filtro de fechas
        query = apply_date_filter(query, EmisionAcumulada, date_filter, start_date, end_date)
        
        # Agrupar y ordenar
        query = query.group_by('grupo').order_by(func.count().desc())
        
        # Ejecutar consulta
        resultados = query.all()
        
        # Calcular totales generales
        total_general = sum(r.total for r in resultados)
        tamaño_total_general = sum(r.tamaño_total or 0 for r in resultados)
        
        # Formatear respuesta
        grupos = []
        for grupo, total, tamaño_total, tamaño_promedio in resultados:
            if grupo is None:
                continue
                
            grupos.append({
                "grupo": str(grupo) if not hasattr(grupo, 'isoformat') else grupo.isoformat(),
                "total": total,
                "tamaño_total": float(tamaño_total) if tamaño_total else 0,
                "tamaño_promedio": float(tamaño_promedio) if tamaño_promedio else 0,
                "porcentaje": round((total / total_general * 100) if total_general > 0 else 0, 2)
            })
        
        return {
            "grupos": grupos,
            "total_general": total_general,
            "tamaño_total_general": float(tamaño_total_general) if tamaño_total_general else 0,
            "group_by": group_by,
            "filtros": {
                "date_filter": date_filter,
                "proyecto_id": proyecto_id
            }
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas detalladas: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )