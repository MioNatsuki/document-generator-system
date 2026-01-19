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

### 🚀 Próximas Partes
- Gestión de proyectos con tablas dinámicas
- Upload y validación de CSVs
- Sistema de plantillas con editor visual
- Motor de emisión de PDFs con códigos de barras
- Dashboard y estadísticas por rol
- Optimización de performance

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

## 📁 Estructura del Proyecto
