# README del proyecto 
# Sistema de Generación Automatizada de Documentos PDF

## 📋 Descripción

Sistema completo de gestión y generación automatizada de documentos PDF personalizados a partir de padrones de datos. Incluye sistema de autenticación robusto, gestión de roles, manejo de plantillas configurables y emisión masiva optimizada.

## 🎯 Características Principales

### ✅ Parte 1 Implementada
- **Autenticación JWT** con tokens de acceso y refresh
- **Gestión de Roles**: SUPERADMIN, ANALISTA, AUXILIAR
- **Modelo de Base de Datos** completo con PostgreSQL
- **Esquema SQL** optimizado con índices y triggers
- **Seguridad robusta**: bcrypt, validación de inputs, rate limiting
- **Logging estructurado** con Loguru

## 🎯 Características Implementadas en la Parte 2

### ✅ Gestión de Proyectos con Tablas Dinámicas
- **CRUD completo de proyectos** con wizard de 3 pasos
- **Creación automática de tablas dinámicas** en PostgreSQL para cada proyecto
- **Configuración de estructura del padrón** con tipos de datos personalizados
- **Soft delete** de proyectos manteniendo integridad referencial

### ✅ Upload y Validación de CSVs
- **Carga de archivos CSV** para inicialización y actualización del padrón
- **Validación de estructura** contra definición del proyecto
- **Procesamiento de datos** con opciones de merge o reemplazo
- **Validación de tamaño y formato** de archivos

### ✅ Sistema de Permisos por Proyecto
- **Asignación de usuarios** a proyectos con roles específicos
- **Control de acceso** granular por funcionalidad
- **Interface adaptativa** según rol del usuario

### ✅ Interfaz de Usuario Completa
- **Dashboard principal** con navegación por roles
- **Ventana de proyecto** con pestañas organizadas
- **Wizard intuitivo** para creación de proyectos
- **Paleta de colores Madolche/Yummies** aplicada consistentemente

## 🛠️ Stack Tecnológico

### Backend
- **Python 3.10+**
- **FastAPI** - Framework web async
- **SQLAlchemy 2.0** - ORM para PostgreSQL
- **JWT** - Autenticación con tokens
- **bcrypt** - Hashing de contraseñas
- **Pydantic** - Validación de datos

### Base de Datos
- **PostgreSQL 13+** - Base de datos relacional
- **Índices optimizados** para consultas frecuentes
- **Triggers** para auditoría automática
- **Vistas materializadas** para reportes

### Frontend (Próxima parte)
- **PyQt6** - Interfaz de escritorio
- **Paleta de colores personalizada** - Estilo Madolche/Yummies
- **Widgets customizados** para mejor UX