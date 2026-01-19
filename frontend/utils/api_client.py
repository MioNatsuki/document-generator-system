# Cliente HTTP para backend 
import requests
import json
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urljoin
from datetime import datetime
import logging

from ..config import config


class APIError(Exception):
    """Excepción personalizada para errores de API"""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class APIClient:
    """Cliente para interactuar con la API del backend"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.API_BASE_URL
        self.session = requests.Session()
        self.token = None
        self.refresh_token = None
        self.user_info = None
        self.logger = logging.getLogger(__name__)
        
        # Configurar timeout
        self.session.timeout = config.API_TIMEOUT
        
        # Headers por defecto
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": f"{config.APP_NAME}/{config.APP_VERSION}"
        })
    
    def set_token(self, token: str):
        """Establecer token JWT"""
        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def set_refresh_token(self, refresh_token: str):
        """Establecer refresh token"""
        self.refresh_token = refresh_token
    
    def clear_tokens(self):
        """Limpiar todos los tokens"""
        self.token = None
        self.refresh_token = None
        self.user_info = None
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]
    
    def set_user_info(self, user_info: Dict[str, Any]):
        """Establecer información del usuario"""
        self.user_info = user_info
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Manejar respuesta de la API"""
        try:
            response.raise_for_status()
            
            # Intentar parsear JSON
            if response.content:
                return response.json()
            return {}
            
        except requests.exceptions.HTTPError as e:
            # Manejar errores HTTP específicos
            status_code = response.status_code
            
            try:
                error_data = response.json()
                detail = error_data.get("detail", str(e))
                
                if isinstance(detail, list):
                    detail = "; ".join([str(d) for d in detail])
                elif isinstance(detail, dict):
                    detail = json.dumps(detail)
                    
            except:
                detail = str(e)
            
            # Mapear códigos de error a mensajes amigables
            error_messages = {
                400: "Solicitud incorrecta",
                401: "No autenticado",
                403: "No autorizado",
                404: "Recurso no encontrado",
                422: "Datos inválidos",
                429: "Demasiadas solicitudes",
                500: "Error interno del servidor",
                502: "Servicio no disponible",
                503: "Servicio en mantenimiento",
            }
            
            message = error_messages.get(status_code, f"Error HTTP {status_code}")
            
            raise APIError(
                message=f"{message}: {detail}",
                status_code=status_code,
                details={"response": detail}
            )
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Realizar petición HTTP"""
        url = urljoin(self.base_url, endpoint)
        
        try:
            response = self.session.request(method, url, **kwargs)
            return self._handle_response(response)
            
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout en {method} {endpoint}")
            raise APIError("El servidor no responde. Intenta nuevamente.")
        
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Error de conexión en {method} {endpoint}")
            raise APIError("No se pudo conectar al servidor. Verifica tu conexión.")
        
        except APIError:
            raise  # Re-lanzar APIError
        
        except Exception as e:
            self.logger.error(f"Error inesperado en {method} {endpoint}: {str(e)}")
            raise APIError(f"Error inesperado: {str(e)}")
    
    # Métodos de autenticación
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Iniciar sesión"""
        data = {
            "username": username,
            "password": password
        }
        
        # Usar FormData para login (OAuth2 compatible)
        response = self._request(
            "POST",
            "/api/v1/auth/login",
            data={"username": username, "password": password, "grant_type": "password"}
        )
        
        # Guardar tokens
        self.set_token(response["access_token"])
        self.set_refresh_token(response["refresh_token"])
        
        # Obtener información del usuario
        self.user_info = self.get_current_user()
        
        return response
    
    def refresh_access_token(self) -> Dict[str, Any]:
        """Refrescar token de acceso"""
        if not self.refresh_token:
            raise APIError("No hay refresh token disponible")
        
        response = self._request(
            "POST",
            "/api/v1/auth/refresh",
            json={"refresh_token": self.refresh_token}
        )
        
        self.set_token(response["access_token"])
        self.set_refresh_token(response["refresh_token"])
        
        return response
    
    def logout(self) -> Dict[str, Any]:
        """Cerrar sesión"""
        try:
            response = self._request("POST", "/api/v1/auth/logout")
        finally:
            self.clear_tokens()
        
        return response
    
    def get_current_user(self) -> Dict[str, Any]:
        """Obtener usuario actual"""
        return self._request("GET", "/api/v1/auth/me")
    
    def validate_token(self) -> Dict[str, Any]:
        """Validar token JWT"""
        return self._request("POST", "/api/v1/auth/validate-token")
    
    # Métodos de proyectos
    def crear_proyecto(self, proyecto_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crear nuevo proyecto"""
        return self._request("POST", "/api/v1/projects/", json=proyecto_data)
    
    def crear_proyecto_desde_csv(self, nombre: str, archivo_path: str, 
                                descripcion: Optional[str] = None) -> Dict[str, Any]:
        """Crear proyecto desde CSV (endpoint simplificado)"""
        with open(archivo_path, 'rb') as f:
            files = {'archivo_csv': f}
            data = {'nombre': nombre}
            
            if descripcion:
                data['descripcion'] = descripcion
            
            return self._request(
                "POST", 
                "/api/v1/projects/crear-con-csv", 
                files=files, 
                data=data
            )
    
    def listar_proyectos(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """Listar proyectos"""
        params = {"skip": skip, "limit": limit}
        return self._request("GET", "/api/v1/projects/", params=params)
    
    def obtener_proyecto(self, proyecto_id: int) -> Dict[str, Any]:
        """Obtener proyecto por ID"""
        return self._request("GET", f"/api/v1/projects/{proyecto_id}")
    
    def actualizar_proyecto(self, proyecto_id: int, proyecto_data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualizar proyecto"""
        return self._request("PUT", f"/api/v1/projects/{proyecto_id}", json=proyecto_data)
    
    def eliminar_proyecto(self, proyecto_id: int, confirmacion: bool = True) -> Dict[str, Any]:
        """Eliminar proyecto"""
        data = {"confirmacion": confirmacion}
        return self._request("DELETE", f"/api/v1/projects/{proyecto_id}", data=data)
    
    def cargar_padron(self, proyecto_id: int, archivo_path: str, 
                     merge: bool = True) -> Dict[str, Any]:
        """Cargar padrón desde CSV"""
        with open(archivo_path, 'rb') as f:
            files = {'archivo': f}
            data = {'merge': merge}
            
            return self._request(
                "POST", 
                f"/api/v1/projects/{proyecto_id}/cargar-padron", 
                files=files, 
                data=data
            )
    
    def obtener_estructura_padron(self, proyecto_id: int) -> Dict[str, Any]:
        """Obtener estructura del padrón"""
        return self._request("GET", f"/api/v1/projects/{proyecto_id}/padron/estructura")
    
    def obtener_muestra_padron(self, proyecto_id: int, limit: int = 10) -> Dict[str, Any]:
        """Obtener muestra de datos del padrón"""
        params = {"limit": limit}
        return self._request("GET", f"/api/v1/projects/{proyecto_id}/padron/muestra", params=params)
    
    def asignar_usuario_proyecto(self, proyecto_id: int, usuario_id: int, 
                                rol_en_proyecto: str) -> Dict[str, Any]:
        """Asignar usuario a proyecto"""
        data = {
            "usuario_id": usuario_id,
            "rol_en_proyecto": rol_en_proyecto
        }
        return self._request("POST", f"/api/v1/projects/{proyecto_id}/usuarios", data=data)
    
    def listar_usuarios_proyecto(self, proyecto_id: int) -> Dict[str, Any]:
        """Listar usuarios asignados a un proyecto"""
        return self._request("GET", f"/api/v1/projects/{proyecto_id}/usuarios")
    
    # Métodos de validación
    def validate_csv_structure(self, csv_content: str, expected_columns: List[str]) -> Tuple[bool, List[str]]:
        """
        Validar estructura de CSV (simulado - en producción esto sería en backend)
        
        Args:
            csv_content: Contenido del CSV como string
            expected_columns: Lista de columnas esperadas
            
        Returns:
            (es_valido, mensajes_error)
        """
        errors = []
        
        try:
            # Parsear primeras líneas para obtener headers
            lines = csv_content.strip().split('\n')
            if not lines:
                errors.append("El CSV está vacío")
                return False, errors
            
            headers = lines[0].split(',')
            headers = [h.strip().strip('"').strip("'") for h in headers]
            
            # Verificar columnas obligatorias
            expected_lower = [col.lower() for col in expected_columns]
            headers_lower = [col.lower() for col in headers]
            
            for expected in expected_columns:
                if expected.lower() not in headers_lower:
                    errors.append(f"Falta columna obligatoria: {expected}")
            
            # Verificar duplicados
            if len(headers) != len(set(headers_lower)):
                errors.append("Hay columnas duplicadas en el CSV")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Error parseando CSV: {str(e)}")
            return False, errors
    
    # Métodos de utilidad
    def test_connection(self) -> bool:
        """Probar conexión con el backend"""
        try:
            self._request("GET", "/health", timeout=5)
            return True
        except:
            return False
    
    def get_system_info(self) -> Dict[str, Any]:
        """Obtener información del sistema"""
        return self._request("GET", "/info")


# Instancia global del cliente
api_client = APIClient()