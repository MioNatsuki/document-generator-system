"""
Motor de procesamiento masivo de emisiones
"""
import os
import uuid
import csv
import json
import math
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import tempfile
import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings
from app.models import EmisionTemp, EmisionFinal, EmisionAcumulada, Proyecto, Plantilla
from app.utils.pdf_generator import PDFGenerator
from app.utils.barcode_generator import BarcodeGenerator
from app.utils.text_formatter import TextFormatter

logger = logging.getLogger(__name__)


class EmissionEngine:
    """
    Motor principal para procesamiento masivo de emisiones
    """
    
    def __init__(self, db: Session, proyecto_id: int, plantilla_id: int, 
                 usuario_id: int, documento: str, pmo: str, fecha_emision: datetime):
        """
        Inicializar motor de emisión
        
        Args:
            db: Sesión de base de datos
            proyecto_id: ID del proyecto
            plantilla_id: ID de la plantilla
            usuario_id: ID del usuario que genera
            documento: Tipo de documento (N, A, E, CI)
            pmo: PMO para la emisión (ej: "PMO 1")
            fecha_emision: Fecha de emisión
        """
        self.db = db
        self.proyecto_id = proyecto_id
        self.plantilla_id = plantilla_id
        self.usuario_id = usuario_id
        self.documento = documento
        self.pmo = pmo
        self.fecha_emision = fecha_emision
        self.sesion_id = uuid.uuid4()
        
        # Obtener proyecto y plantilla
        self.proyecto = db.query(Proyecto).filter(Proyecto.id == proyecto_id).first()
        self.plantilla = db.query(Plantilla).filter(Plantilla.id == plantilla_id).first()
        
        if not self.proyecto:
            raise ValueError(f"Proyecto no encontrado: {proyecto_id}")
        if not self.plantilla:
            raise ValueError(f"Plantilla no encontrada: {plantilla_id}")
        
        # Inicializar componentes
        self.pdf_generator = PDFGenerator()
        self.barcode_generator = BarcodeGenerator()
        self.text_formatter = TextFormatter()
        
        # Configuración
        self.output_base = Path(settings.OUTPUT_FOLDER)
        self.max_workers = os.cpu_count() or 4
        
        logger.info(f"Motor de emisión inicializado: proyecto={self.proyecto.nombre}, "
                   f"plantilla={self.plantilla.nombre}, sesion={self.sesion_id}")
    
    def load_emission_csv(self, csv_path: Path) -> Tuple[List[Dict], List[str]]:
        """
        Cargar y validar CSV de emisión
        
        Args:
            csv_path: Ruta al archivo CSV
            
        Returns:
            Tuple (registros, cuentas_no_encontradas)
        """
        registros = []
        cuentas = set()
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                # Validar columnas requeridas
                required_columns = ['cuenta', 'orden_impresion']
                for col in required_columns:
                    if col not in reader.fieldnames:
                        raise ValueError(f"Columna requerida no encontrada: {col}")
                
                # Leer registros
                for i, row in enumerate(reader, 1):
                    try:
                        cuenta = row['cuenta'].strip()
                        orden_impresion = int(row['orden_impresion'])
                        
                        # Validar orden único
                        if any(r['orden_impresion'] == orden_impresion for r in registros):
                            raise ValueError(f"Orden de impresión duplicado: {orden_impresion}")
                        
                        # Extraer datos adicionales
                        datos_adicionales = {}
                        for key, value in row.items():
                            if key not in required_columns and value.strip():
                                datos_adicionales[key] = value.strip()
                        
                        registros.append({
                            'cuenta': cuenta,
                            'orden_impresion': orden_impresion,
                            'datos_adicionales': datos_adicionales,
                            'linea_csv': i
                        })
                        cuentas.add(cuenta)
                        
                    except (ValueError, KeyError) as e:
                        logger.error(f"Error en línea {i}: {str(e)}")
                        raise
            
            if not registros:
                raise ValueError("El CSV está vacío o no contiene registros válidos")
            
            logger.info(f"CSV cargado: {len(registros)} registros, {len(cuentas)} cuentas únicas")
            
        except Exception as e:
            logger.error(f"Error cargando CSV: {str(e)}")
            raise
        
        return registros, list(cuentas)
    
    def match_with_padron(self, cuentas: List[str]) -> Tuple[List[Dict], List[str]]:
        """
        Realizar JOIN con tabla de padrón
        
        Args:
            cuentas: Lista de cuentas a buscar
            
        Returns:
            Tuple (datos_encontrados, cuentas_no_encontradas)
        """
        if not cuentas:
            return [], []
        
        try:
            # Construir consulta dinámica
            table_name = self.proyecto.nombre_tabla_padron
            placeholders = ', '.join([f':c{i}' for i in range(len(cuentas))])
            
            sql = f"""
            SELECT * FROM {table_name}
            WHERE cuenta IN ({placeholders})
            AND is_deleted = false
            """
            
            params = {f'c{i}': cuenta for i, cuenta in enumerate(cuentas)}
            
            # Ejecutar consulta
            result = self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            # Convertir a diccionarios
            datos_encontrados = []
            for row in rows:
                datos = dict(row._mapping)
                datos_encontrados.append(datos)
            
            # Encontrar cuentas no encontradas
            cuentas_encontradas = {d['cuenta'] for d in datos_encontrados}
            cuentas_no_encontradas = [c for c in cuentas if c not in cuentas_encontradas]
            
            logger.info(f"Matching completado: {len(datos_encontrados)} encontradas, "
                       f"{len(cuentas_no_encontradas)} no encontradas")
            
            return datos_encontrados, cuentas_no_encontradas
            
        except Exception as e:
            logger.error(f"Error en matching con padrón: {str(e)}")
            raise
    
    def calculate_automatic_fields(self, cuenta: str, datos_padron: Dict) -> Dict[str, Any]:
        """
        Calcular campos automáticos
        
        Args:
            cuenta: Número de cuenta
            datos_padron: Datos del padrón
            
        Returns:
            Diccionario con campos calculados
        """
        try:
            # Calcular PMO
            pmo_numero = self._calculate_pmo()
            
            # Calcular Visita
            visita = self._calculate_visita(cuenta)
            
            # Calcular código de barras
            codigo_barras = self._generate_barcode(cuenta, visita)
            
            # Aplicar formatos a los datos
            datos_formateados = self._apply_formats(datos_padron)
            
            return {
                'pmo': f"PMO {pmo_numero}",
                'visita': visita,
                'codigo_barras': codigo_barras,
                'documento': self.documento,
                'fecha_emision': self.fecha_emision,
                **datos_formateados
            }
            
        except Exception as e:
            logger.error(f"Error calculando campos para cuenta {cuenta}: {str(e)}")
            raise
    
    def _calculate_pmo(self) -> int:
        """
        Buscar último PMO y sumar 1
        """
        try:
            sql = """
            SELECT pmo FROM emisiones_acumuladas
            WHERE proyecto_id = :proyecto_id
            ORDER BY created_at DESC
            LIMIT 1
            """
            
            result = self.db.execute(
                text(sql), 
                {"proyecto_id": self.proyecto_id}
            ).fetchone()
            
            if result:
                last_pmo = result[0]
                # Extraer número del PMO
                if isinstance(last_pmo, str) and last_pmo.startswith("PMO "):
                    try:
                        last_num = int(last_pmo[4:])
                        return last_num + 1
                    except ValueError:
                        pass
            
            # Si no hay PMO previo, empezar en 1
            return 1
            
        except Exception as e:
            logger.error(f"Error calculando PMO: {str(e)}")
            return 1
    
    def _calculate_visita(self, cuenta: str) -> str:
        """
        Calcular número de visita basado en último documento
        """
        try:
            # Obtener último documento para esta cuenta
            sql = """
            SELECT documento, visita FROM emisiones_acumuladas
            WHERE proyecto_id = :proyecto_id
            AND cuenta = :cuenta
            ORDER BY fecha_emision DESC
            LIMIT 1
            """
            
            result = self.db.execute(
                text(sql),
                {"proyecto_id": self.proyecto_id, "cuenta": cuenta}
            ).fetchone()
            
            if result:
                last_documento = result[0]
                last_visita = result[1]
                
                # Si el documento es del mismo tipo, incrementar visita
                if last_documento == self.documento:
                    # Extraer número de visita
                    if last_visita.startswith(self.documento):
                        try:
                            last_num = int(last_visita[1:])  # Ej: "N2" -> 2
                            return f"{self.documento}{last_num + 1}"
                        except ValueError:
                            pass
                # Si es diferente documento, empezar desde 1
                return f"{self.documento}1"
            
            # Primera visita para esta cuenta
            return f"{self.documento}1"
            
        except Exception as e:
            logger.error(f"Error calculando visita para cuenta {cuenta}: {str(e)}")
            return f"{self.documento}1"
    
    def _generate_barcode(self, cuenta: str, visita: str) -> str:
        """
        Generar string para código de barras
        """
        fecha_str = self.fecha_emision.strftime("%Y%m%d")
        return f"*{cuenta}*{fecha_str}*{visita}*"
    
    def _apply_formats(self, datos: Dict) -> Dict:
        """
        Aplicar formatos automáticos a los datos
        """
        formatted = {}
        
        for key, value in datos.items():
            if value is None:
                formatted[key] = ""
            elif isinstance(value, date):
                formatted[key] = value.strftime("%d/%m/%Y")
            elif isinstance(value, (int, float)):
                # Verificar si parece ser un monto monetario
                if any(money_key in key.lower() for money_key in ['monto', 'importe', 'valor', 'total']):
                    formatted[key] = f"${value:,.2f}"
                else:
                    formatted[key] = str(value)
            else:
                formatted[key] = str(value)
        
        return formatted
    
    def process_batch(self, registros: List[Dict]) -> Dict[str, Any]:
        """
        Procesar un lote de registros
        
        Args:
            registros: Lista de registros a procesar
            
        Returns:
            Diccionario con resultados del procesamiento
        """
        resultados = {
            'total': len(registros),
            'exitosos': 0,
            'fallidos': 0,
            'errores': [],
            'archivos_generados': []
        }
        
        for registro in registros:
            try:
                # 1. Obtener datos del padrón
                cuenta = registro['cuenta']
                datos_padron = registro.get('datos_padron', {})
                
                if not datos_padron:
                    raise ValueError(f"No hay datos de padrón para cuenta {cuenta}")
                
                # 2. Calcular campos automáticos
                campos_calculados = self.calculate_automatic_fields(cuenta, datos_padron)
                
                # 3. Preparar datos para PDF
                datos_completos = {**datos_padron, **campos_calculados}
                
                # 4. Generar PDF
                pdf_path = self.generate_single_pdf(
                    cuenta=cuenta,
                    datos=datos_completos,
                    orden_impresion=registro['orden_impresion']
                )
                
                # 5. Registrar en base de datos
                self.record_emission(
                    cuenta=cuenta,
                    datos_json=datos_completos,
                    pdf_path=pdf_path,
                    orden_impresion=registro['orden_impresion']
                )
                
                resultados['exitosos'] += 1
                resultados['archivos_generados'].append(pdf_path)
                
            except Exception as e:
                resultados['fallidos'] += 1
                resultados['errores'].append({
                    'cuenta': registro.get('cuenta', 'Desconocida'),
                    'error': str(e),
                    'linea': registro.get('linea_csv')
                })
                logger.error(f"Error procesando cuenta {registro.get('cuenta')}: {str(e)}")
        
        return resultados
    
    def generate_single_pdf(self, cuenta: str, datos: Dict, orden_impresion: int) -> Path:
        """
        Generar PDF individual
        
        Args:
            cuenta: Número de cuenta
            datos: Datos completos para el PDF
            orden_impresion: Orden de impresión
            
        Returns:
            Ruta al PDF generado
        """
        try:
            # Crear estructura de carpetas
            fecha_str = self.fecha_emision.strftime("%Y%m%d")
            output_dir = self.output_base / str(self.proyecto_id) / fecha_str
            output_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_path = output_dir / f"{cuenta}.pdf"
            
            # Generar código de barras si está en los datos
            barcode_image = None
            if 'codigo_barras' in datos:
                barcode_image = self.barcode_generator.generate(
                    datos['codigo_barras'],
                    output_format='PNG'
                )
            
            # Generar PDF
            self.pdf_generator.generate_from_template(
                template_path=Path(self.plantilla.archivo_docx),
                template_config=self.plantilla.configuracion,
                output_path=pdf_path,
                data=datos,
                barcode_image=barcode_image,
                page_size=self.plantilla.tamaño_pagina
            )
            
            logger.info(f"PDF generado: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Error generando PDF para cuenta {cuenta}: {str(e)}")
            raise
    
    def record_emission(self, cuenta: str, datos_json: Dict, pdf_path: Path, orden_impresion: int):
        """
        Registrar emisión en base de datos
        
        Args:
            cuenta: Número de cuenta
            datos_json: Datos completos en JSON
            pdf_path: Ruta al PDF generado
            orden_impresion: Orden de impresión
        """
        try:
            # Obtener tamaño del archivo
            file_size = pdf_path.stat().st_size if pdf_path.exists() else 0
            
            # Calcular hash del archivo
            import hashlib
            file_hash = ""
            if pdf_path.exists():
                with open(pdf_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Crear registro en emisiones_final
            emision_final = EmisionFinal(
                sesion_id=self.sesion_id,
                proyecto_id=self.proyecto_id,
                plantilla_id=self.plantilla_id,
                cuenta=cuenta,
                orden_impresion=orden_impresion,
                datos_json=datos_json,
                documento=self.documento,
                pmo=self.pmo,
                fecha_emision=self.fecha_emision,
                visita=datos_json.get('visita', ''),
                codigo_barras=datos_json.get('codigo_barras', ''),
                is_generado=True
            )
            
            # Crear registro histórico
            emision_acumulada = EmisionAcumulada(
                sesion_id=self.sesion_id,
                proyecto_id=self.proyecto_id,
                plantilla_id=self.plantilla_id,
                usuario_id=self.usuario_id,
                cuenta=cuenta,
                orden_impresion=orden_impresion,
                datos_json=datos_json,
                documento=self.documento,
                pmo=self.pmo,
                fecha_emision=self.fecha_emision,
                visita=datos_json.get('visita', ''),
                codigo_barras=datos_json.get('codigo_barras', ''),
                ruta_archivo_pdf=str(pdf_path),
                tamaño_archivo=file_size,
                hash_archivo=file_hash,
                usuario_id_generacion=self.usuario_id
            )
            
            self.db.add(emision_final)
            self.db.add(emision_acumulada)
            self.db.commit()
            
            logger.debug(f"Emisión registrada para cuenta {cuenta}")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error registrando emisión para cuenta {cuenta}: {str(e)}")
            raise
    
    def process_complete_emission(self, csv_path: Path) -> Dict[str, Any]:
        """
        Procesar emisión completa desde CSV
        
        Args:
            csv_path: Ruta al archivo CSV
            
        Returns:
            Diccionario con resultados del procesamiento
        """
        logger.info(f"Iniciando procesamiento de emisión desde: {csv_path}")
        
        resultados = {
            'sesion_id': str(self.sesion_id),
            'proyecto_id': self.proyecto_id,
            'plantilla_id': self.plantilla_id,
            'documento': self.documento,
            'pmo': self.pmo,
            'fecha_emision': self.fecha_emision.isoformat(),
            'total_registros': 0,
            'registros_procesados': 0,
            'cuentas_no_encontradas': [],
            'pdfs_generados': 0,
            'errores': [],
            'tiempo_procesamiento': 0,
            'ruta_salida': ''
        }
        
        start_time = datetime.now()
        
        try:
            # 1. Cargar CSV
            registros_csv, cuentas_csv = self.load_emission_csv(csv_path)
            resultados['total_registros'] = len(registros_csv)
            
            # 2. Matching con padrón
            datos_padron, cuentas_no_encontradas = self.match_with_padron(cuentas_csv)
            resultados['cuentas_no_encontradas'] = cuentas_no_encontradas
            
            if cuentas_no_encontradas:
                logger.warning(f"Cuentas no encontradas: {len(cuentas_no_encontradas)}")
                # Podríamos decidir continuar o no
            
            # 3. Combinar datos
            registros_combinados = []
            datos_padron_dict = {d['cuenta']: d for d in datos_padron}
            
            for registro in registros_csv:
                cuenta = registro['cuenta']
                if cuenta in datos_padron_dict:
                    registro['datos_padron'] = datos_padron_dict[cuenta]
                    registros_combinados.append(registro)
                else:
                    logger.warning(f"Cuenta {cuenta} no encontrada en padrón, omitiendo")
            
            # 4. Procesar en paralelo
            batch_size = 100
            batches = [registros_combinados[i:i + batch_size] 
                      for i in range(0, len(registros_combinados), batch_size)]
            
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for batch in batches:
                    future = executor.submit(self.process_batch, batch)
                    futures.append(future)
                
                for future in as_completed(futures):
                    batch_result = future.result()
                    resultados['pdfs_generados'] += batch_result['exitosos']
                    resultados['errores'].extend(batch_result['errores'])
            
            resultados['registros_procesados'] = len(registros_combinados)
            
            # 5. Calcular métricas
            end_time = datetime.now()
            elapsed = end_time - start_time
            resultados['tiempo_procesamiento'] = elapsed.total_seconds()
            
            if registros_combinados:
                pdfs_per_second = resultados['pdfs_generados'] / elapsed.total_seconds()
                resultados['pdfs_por_segundo'] = round(pdfs_per_second, 2)
            
            # 6. Definir ruta de salida
            fecha_str = self.fecha_emision.strftime("%Y%m%d")
            resultados['ruta_salida'] = str(self.output_base / str(self.proyecto_id) / fecha_str)
            
            logger.info(f"Procesamiento completado: {resultados['pdfs_generados']} PDFs generados "
                       f"en {elapsed.total_seconds():.2f} segundos")
            
            return resultados
            
        except Exception as e:
            logger.error(f"Error en procesamiento de emisión: {str(e)}")
            resultados['error_global'] = str(e)
            raise
    
    def generate_missing_accounts_report(self, cuentas_no_encontradas: List[str], 
                                        output_dir: Path) -> Path:
        """
        Generar reporte de cuentas no encontradas
        
        Args:
            cuentas_no_encontradas: Lista de cuentas no encontradas
            output_dir: Directorio de salida
            
        Returns:
            Ruta al reporte generado
        """
        if not cuentas_no_encontradas:
            return None
        
        report_path = output_dir / f"cuentas_no_encontradas_{self.sesion_id}.csv"
        
        try:
            with open(report_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Cuenta', 'Fecha_Reporte'])
                writer.writerow(['', datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow([])  # Línea en blanco
                writer.writerow(['Lista de Cuentas no Encontradas'])
                
                for cuenta in cuentas_no_encontradas:
                    writer.writerow([cuenta])
            
            logger.info(f"Reporte de cuentas no encontradas generado: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error generando reporte: {str(e)}")
            return None