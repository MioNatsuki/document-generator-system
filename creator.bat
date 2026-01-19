@echo off
REM Script para crear estructura document-generator-system en Windows


REM =========================
REM Backend
REM =========================
mkdir document-generator-system\backend
mkdir document-generator-system\backend\app
mkdir document-generator-system\backend\app\utils
mkdir document-generator-system\backend\app\api
mkdir document-generator-system\backend\app\api\v1
mkdir document-generator-system\backend\app\core

REM Archivos backend/app
type nul > document-generator-system\backend\app\__init__.py
echo # Punto de entrada FastAPI > document-generator-system\backend\app\main.py
echo # Configuración de aplicación > document-generator-system\backend\app\config.py
echo # Configuración de base de datos > document-generator-system\backend\app\database.py
echo # Modelos SQLAlchemy > document-generator-system\backend\app\models.py
echo # Pydantic schemas > document-generator-system\backend\app\schemas.py
echo # Autenticación JWT > document-generator-system\backend\app\auth.py
echo # Dependencias FastAPI > document-generator-system\backend\app\dependencies.py

REM Utils
type nul > document-generator-system\backend\app\utils\__init__.py
echo # Funciones de seguridad > document-generator-system\backend\app\utils\security.py
echo # Manejo de archivos > document-generator-system\backend\app\utils\file_handlers.py
echo # Configuración de logs > document-generator-system\backend\app\utils\logging.py

REM API
type nul > document-generator-system\backend\app\api\__init__.py
type nul > document-generator-system\backend\app\api\deps.py

REM API v1
type nul > document-generator-system\backend\app\api\v1\__init__.py
echo # Endpoints de autenticación > document-generator-system\backend\app\api\v1\auth.py
echo # Endpoints de proyectos > document-generator-system\backend\app\api\v1\projects.py
echo # Endpoints de plantillas > document-generator-system\backend\app\api\v1\templates.py
echo # Endpoints de emisión > document-generator-system\backend\app\api\v1\emissions.py
echo # Endpoints de estadísticas > document-generator-system\backend\app\api\v1\stats.py

REM Core
type nul > document-generator-system\backend\app\core\__init__.py
echo # Lógica de roles y permisos > document-generator-system\backend\app\core\roles.py
echo # Gestión de tablas dinámicas > document-generator-system\backend\app\core\padron_manager.py

REM Archivos backend raíz
type nul > document-generator-system\backend\requirements.txt
type nul > document-generator-system\backend\.env.example
echo # Script creación de tablas > document-generator-system\backend\create_tables.py
echo # Script para iniciar servidor > document-generator-system\backend\run.py

REM =========================
REM Frontend
REM =========================
mkdir document-generator-system\frontend
mkdir document-generator-system\frontend\widgets
mkdir document-generator-system\frontend\utils
mkdir document-generator-system\frontend\views

echo # Aplicación principal PyQt6 > document-generator-system\frontend\main.py
echo # Configuración frontend > document-generator-system\frontend\config.py
echo # Estilos y paleta de colores > document-generator-system\frontend\styles.py

REM Widgets
type nul > document-generator-system\frontend\widgets\__init__.py
echo # Ventana de login > document-generator-system\frontend\widgets\login_window.py
echo # Ventana de dashboard > document-generator-system\frontend\widgets\dashboard_window.py
echo # Ventana de proyecto > document-generator-system\frontend\widgets\project_window.py

REM Utils
type nul > document-generator-system\frontend\utils\__init__.py
echo # Cliente HTTP para backend > document-generator-system\frontend\utils\api_client.py
echo # Diálogos de archivos > document-generator-system\frontend\utils\file_dialogs.py

REM Views
type nul > document-generator-system\frontend\views\__init__.py
echo # Vista de autenticación > document-generator-system\frontend\views\auth_view.py
echo # Vista de proyectos > document-generator-system\frontend\views\projects_view.py
echo # Vista de plantillas > document-generator-system\frontend\views\templates_view.py

REM =========================
REM Docs
REM =========================
mkdir document-generator-system\docs
echo -- Script SQL completo > document-generator-system\docs\database_schema.sql

REM =========================
REM Tests
REM =========================
mkdir document-generator-system\tests
type nul > document-generator-system\tests\__init__.py
echo # Test de autenticación > document-generator-system\tests\test_auth.py
echo # Test de modelos > document-generator-system\tests\test_models.py

REM =========================
REM Archivos raíz
REM =========================
echo # README del proyecto > document-generator-system\README.md

echo Estructura document-generator-system creada exitosamente.
pause
