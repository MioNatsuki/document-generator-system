# Punto de entrada FastAPI 
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time
from loguru import logger

from .config import settings
from .api.v1.auth import router as auth_router
from .utils.logging import setup_logger

# Configurar logger
setup_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manejo del ciclo de vida de la aplicación
    """
    # Startup
    logger.info("🚀 Iniciando aplicación...")
    logger.info(f"📦 Nombre: {settings.APP_NAME}")
    logger.info(f"🌍 Entorno: {settings.ENVIRONMENT}")
    
    yield
    
    # Shutdown
    logger.info("👋 Apagando aplicación...")


# Crear aplicación FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    description="Sistema de Generación Automatizada de Documentos PDF",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Configurar CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware para logging de todas las requests
    """
    start_time = time.time()
    
    # Obtener información de la request
    ip = request.client.host if request.client else "unknown"
    method = request.method
    url = str(request.url)
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Excluir endpoints de health check del logging detallado
    if url.endswith("/health"):
        response = await call_next(request)
        return response
    
    logger.info(f"🌐 Request: {method} {url} | IP: {ip} | UA: {user_agent}")
    
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"❌ Error procesando request: {str(e)}")
        raise
    
    process_time = time.time() - start_time
    logger.info(f"✅ Response: {response.status_code} | Tiempo: {process_time:.3f}s")
    
    # Agregar header de tiempo de procesamiento
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# Manejo de excepciones global
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Manejo de errores de validación
    """
    logger.warning(f"⚠️ Validación fallida: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Manejo de excepciones globales
    """
    logger.error(f"🔥 Error no manejado: {str(exc)}")
    
    if settings.DEBUG:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Error interno del servidor"},
        )


# Routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["autenticación"])


# Endpoints básicos
@app.get("/")
async def root():
    """
    Endpoint raíz
    """
    return {
        "message": "Bienvenido al Sistema de Generación Automatizada de PDFs",
        "version": "1.0.0",
        "docs": "/docs" if settings.DEBUG else None
    }


@app.get("/health")
async def health_check():
    """
    Health check para monitoreo
    """
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": settings.APP_NAME
    }


@app.get("/info")
async def system_info():
    """
    Información del sistema
    """
    import platform
    import sys
    
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "app_name": settings.APP_NAME
    }