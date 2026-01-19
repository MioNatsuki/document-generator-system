-- Script SQL completo 
-- ============================================
-- SISTEMA DE GENERACIÓN AUTOMATIZADA DE PDFs
-- ESQUEMA DE BASE DE DATOS COMPLETO
-- ============================================

-- Habilitar extensiones útiles
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- TABLAS PRINCIPALES
-- ============================================

-- Tabla de usuarios
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(255) NOT NULL,
    rol VARCHAR(20) NOT NULL CHECK (rol IN ('SUPERADMIN', 'ANALISTA', 'AUXILIAR')),
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de proyectos
CREATE TABLE proyectos (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    nombre VARCHAR(255) UNIQUE NOT NULL,
    descripcion TEXT,
    logo_url VARCHAR(500),
    nombre_tabla_padron VARCHAR(100) UNIQUE NOT NULL,
    uuid_padron UUID UNIQUE DEFAULT uuid_generate_v4(),
    estructura_padron JSONB NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Relación usuarios-proyectos (muchos a muchos)
CREATE TABLE proyectos_usuarios (
    id SERIAL PRIMARY KEY,
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    rol_en_proyecto VARCHAR(20) NOT NULL CHECK (rol_en_proyecto IN ('SUPERADMIN', 'ANALISTA', 'AUXILIAR')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(proyecto_id, usuario_id)
);

-- Tabla de plantillas
CREATE TABLE plantillas (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id),
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT,
    archivo_docx VARCHAR(500) NOT NULL,
    archivo_pdf_base VARCHAR(500),
    configuracion JSONB NOT NULL,
    tamaño_pagina JSONB NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla temporal para emisiones
CREATE TABLE emisiones_temp (
    id SERIAL PRIMARY KEY,
    sesion_id UUID NOT NULL,
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id),
    cuenta VARCHAR(50) NOT NULL,
    orden_impresion INTEGER NOT NULL,
    datos_raw JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla final para emisiones (procesamiento)
CREATE TABLE emisiones_final (
    id SERIAL PRIMARY KEY,
    sesion_id UUID NOT NULL,
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id),
    plantilla_id INTEGER NOT NULL REFERENCES plantillas(id),
    cuenta VARCHAR(50) NOT NULL,
    orden_impresion INTEGER NOT NULL,
    datos_json JSONB NOT NULL,
    documento VARCHAR(50) NOT NULL,
    pmo VARCHAR(50) NOT NULL,
    fecha_emision TIMESTAMP WITH TIME ZONE NOT NULL,
    visita VARCHAR(50) NOT NULL,
    codigo_barras VARCHAR(500),
    is_generado BOOLEAN DEFAULT FALSE,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla acumulada de emisiones (histórico)
CREATE TABLE emisiones_acumuladas (
    id BIGSERIAL PRIMARY KEY,
    uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    sesion_id UUID NOT NULL,
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id),
    plantilla_id INTEGER NOT NULL REFERENCES plantillas(id),
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    cuenta VARCHAR(50) NOT NULL,
    orden_impresion INTEGER NOT NULL,
    datos_json JSONB NOT NULL,
    documento VARCHAR(50) NOT NULL,
    pmo VARCHAR(50) NOT NULL,
    fecha_emision TIMESTAMP WITH TIME ZONE NOT NULL,
    visita VARCHAR(50) NOT NULL,
    codigo_barras VARCHAR(500),
    ruta_archivo_pdf VARCHAR(500) NOT NULL,
    tamaño_archivo BIGINT,
    hash_archivo VARCHAR(64),
    usuario_id_generacion INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_generacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de bitácora
CREATE TABLE bitacora (
    id BIGSERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    accion VARCHAR(100) NOT NULL,
    entidad VARCHAR(50),
    entidad_id INTEGER,
    detalles JSONB,
    ip VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- ÍNDICES PARA OPTIMIZACIÓN
-- ============================================

-- Índices para usuarios
CREATE INDEX idx_usuarios_username ON usuarios(username);
CREATE INDEX idx_usuarios_email ON usuarios(email);
CREATE INDEX idx_usuarios_rol ON usuarios(rol);
CREATE INDEX idx_usuarios_activos ON usuarios(is_active) WHERE is_active = true;
CREATE INDEX idx_usuarios_search ON usuarios(username, email, nombre_completo) WHERE is_deleted = false;
CREATE INDEX idx_usuarios_created ON usuarios(created_at DESC);

-- Índices para proyectos
CREATE INDEX idx_proyectos_nombre ON proyectos(nombre);
CREATE INDEX idx_proyectos_deleted ON proyectos(is_deleted) WHERE is_deleted = false;
CREATE INDEX idx_proyectos_search ON proyectos(nombre, descripcion) WHERE is_deleted = false;
CREATE INDEX idx_proyectos_created ON proyectos(created_at DESC);

-- Índices para proyectos_usuarios
CREATE INDEX idx_proyecto_usuario_proyecto ON proyectos_usuarios(proyecto_id);
CREATE INDEX idx_proyecto_usuario_usuario ON proyectos_usuarios(usuario_id);
CREATE INDEX idx_proyecto_usuario_rol ON proyectos_usuarios(rol_en_proyecto);

-- Índices para plantillas
CREATE INDEX idx_plantillas_proyecto ON plantillas(proyecto_id);
CREATE INDEX idx_plantillas_deleted ON plantillas(is_deleted) WHERE is_deleted = false;

-- Índices para emisiones_temp
CREATE INDEX idx_emision_temp_sesion ON emisiones_temp(sesion_id);
CREATE INDEX idx_emision_temp_proyecto ON emisiones_temp(proyecto_id);
CREATE INDEX idx_emision_temp_cuenta ON emisiones_temp(cuenta, proyecto_id);

-- Índices para emisiones_final
CREATE INDEX idx_emision_final_sesion ON emisiones_final(sesion_id);
CREATE INDEX idx_emision_final_proyecto ON emisiones_final(proyecto_id);
CREATE INDEX idx_emision_final_cuenta ON emisiones_final(cuenta, proyecto_id);
CREATE INDEX idx_emision_final_orden ON emisiones_final(orden_impresion, sesion_id);
CREATE INDEX idx_emision_final_generado ON emisiones_final(is_generado) WHERE is_generado = false;

-- Índices para emisiones_acumuladas
CREATE INDEX idx_emisiones_acumuladas_cuenta ON emisiones_acumuladas(cuenta);
CREATE INDEX idx_emisiones_acumuladas_fecha_emision ON emisiones_acumuladas(fecha_emision);
CREATE INDEX idx_emisiones_acumuladas_fecha_generacion ON emisiones_acumuladas(fecha_generacion);
CREATE INDEX idx_emisiones_acumuladas_documento ON emisiones_acumuladas(documento);
CREATE INDEX idx_emisiones_acumuladas_usuario ON emisiones_acumuladas(usuario_id);
CREATE INDEX idx_emisiones_acumuladas_proyecto ON emisiones_acumuladas(proyecto_id);
CREATE INDEX idx_emisiones_complete ON emisiones_acumuladas(proyecto_id, cuenta, fecha_emision DESC);
CREATE INDEX idx_emisiones_stats ON emisiones_acumuladas(fecha_generacion, usuario_id, documento);

-- Índices para bitácora
CREATE INDEX idx_bitacora_usuario ON bitacora(usuario_id);
CREATE INDEX idx_bitacora_accion ON bitacora(accion);
CREATE INDEX idx_bitacora_created_at ON bitacora(created_at);
CREATE INDEX idx_bitacora_entidad ON bitacora(entidad, entidad_id);
CREATE INDEX idx_bitacora_complete ON bitacora(usuario_id, accion, created_at DESC);
CREATE INDEX idx_bitacora_date_range ON bitacora(created_at DESC) WHERE created_at >= NOW() - INTERVAL '90 days';

-- ============================================
-- TRIGGERS Y FUNCIONES
-- ============================================

-- Función para actualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para actualizar updated_at
CREATE TRIGGER update_usuarios_updated_at BEFORE UPDATE ON usuarios FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_proyectos_updated_at BEFORE UPDATE ON proyectos FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_plantillas_updated_at BEFORE UPDATE ON plantillas FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Función para registrar en bitácora automáticamente
CREATE OR REPLACE FUNCTION log_usuario_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO bitacora (usuario_id, accion, entidad, entidad_id, detalles)
        VALUES (
            NEW.id,
            'EDITAR_USUARIO',
            'usuario',
            NEW.id,
            jsonb_build_object(
                'cambios', 
                (SELECT jsonb_object_agg(key, value) 
                 FROM jsonb_each(to_jsonb(OLD)) AS old_json 
                 FULL OUTER JOIN jsonb_each(to_jsonb(NEW)) AS new_json 
                 ON old_json.key = new_json.key 
                 WHERE old_json.value IS DISTINCT FROM new_json.value)
            )
        );
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO bitacora (usuario_id, accion, entidad, entidad_id, detalles)
        VALUES (
            NEW.id,
            'CREAR_USUARIO',
            'usuario',
            NEW.id,
            jsonb_build_object('nuevo_usuario', NEW.username)
        );
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO bitacora (usuario_id, accion, entidad, entidad_id, detalles)
        VALUES (
            OLD.id,
            'ELIMINAR_USUARIO',
            'usuario',
            OLD.id,
            jsonb_build_object('usuario_eliminado', OLD.username)
        );
    END IF;
    RETURN NULL;
END;
$$ language 'plpgsql';

-- Trigger para usuarios
CREATE TRIGGER trigger_log_usuario_changes 
AFTER INSERT OR UPDATE OR DELETE ON usuarios 
FOR EACH ROW EXECUTE FUNCTION log_usuario_changes();

-- ============================================
-- VISTAS PARA REPORTES
-- ============================================

-- Vista para estadísticas de usuarios
CREATE VIEW vista_estadisticas_usuarios AS
SELECT 
    u.id,
    u.username,
    u.nombre_completo,
    u.rol,
    COUNT(DISTINCT pu.proyecto_id) as proyectos_asignados,
    COUNT(ea.id) as total_emisiones,
    COUNT(DISTINCT DATE(ea.fecha_generacion)) as dias_activos,
    MIN(ea.fecha_generacion) as primera_emision,
    MAX(ea.fecha_generacion) as ultima_emision
FROM usuarios u
LEFT JOIN proyectos_usuarios pu ON u.id = pu.usuario_id
LEFT JOIN emisiones_acumuladas ea ON u.id = ea.usuario_id
WHERE u.is_deleted = false AND u.is_active = true
GROUP BY u.id, u.username, u.nombre_completo, u.rol;

-- Vista para estadísticas de proyectos
CREATE VIEW vista_estadisticas_proyectos AS
SELECT 
    p.id,
    p.nombre,
    p.descripcion,
    COUNT(DISTINCT pu.usuario_id) as usuarios_asignados,
    COUNT(DISTINCT pl.id) as plantillas_activas,
    COUNT(ea.id) as total_emisiones,
    MIN(ea.fecha_generacion) as primera_emision,
    MAX(ea.fecha_generacion) as ultima_emision,
    SUM(ea.tamaño_archivo) as tamaño_total_pdfs
FROM proyectos p
LEFT JOIN proyectos_usuarios pu ON p.id = pu.proyecto_id
LEFT JOIN plantillas pl ON p.id = pl.proyecto_id AND pl.is_deleted = false
LEFT JOIN emisiones_acumuladas ea ON p.id = ea.proyecto_id
WHERE p.is_deleted = false
GROUP BY p.id, p.nombre, p.descripcion;

-- Vista para dashboard de emisiones
CREATE VIEW vista_dashboard_emisiones AS
SELECT 
    DATE(fecha_generacion) as fecha,
    documento,
    COUNT(*) as total_documentos,
    COUNT(DISTINCT cuenta) as cuentas_unicas,
    COUNT(DISTINCT usuario_id) as usuarios_activos,
    SUM(tamaño_archivo) as tamaño_total
FROM emisiones_acumuladas
WHERE fecha_generacion >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(fecha_generacion), documento;

-- ============================================
-- DATOS INICIALES
-- ============================================

-- Insertar usuario superadmin (cambiar contraseña después!)
INSERT INTO usuarios (username, email, hashed_password, nombre_completo, rol, is_active)
VALUES (
    'superadmin',
    'superadmin@system.com',
    crypt('Admin123!', gen_salt('bf', 12)),
    'Super Administrador',
    'SUPERADMIN',
    true
) ON CONFLICT (username) DO NOTHING;

-- ============================================
-- COMENTARIOS
-- ============================================

COMMENT ON TABLE usuarios IS 'Usuarios del sistema con roles y autenticación';
COMMENT ON TABLE proyectos IS 'Proyectos de generación de PDFs con tablas dinámicas de padrón';
COMMENT ON TABLE proyectos_usuarios IS 'Relación muchos-a-muchos entre usuarios y proyectos';
COMMENT ON TABLE plantillas IS 'Plantillas de documentos PDF con configuración de mapeo';
COMMENT ON TABLE emisiones_temp IS 'Datos temporales para procesamiento de emisiones';
COMMENT ON TABLE emisiones_final IS 'Datos procesados listos para generación de PDFs';
COMMENT ON TABLE emisiones_acumuladas IS 'Histórico completo de todas las emisiones generadas';
COMMENT ON TABLE bitacora IS 'Registro de auditoría de todas las acciones del sistema';

COMMENT ON COLUMN usuarios.hashed_password IS 'Contraseña hasheada con bcrypt (12 rounds)';
COMMENT ON COLUMN proyectos.nombre_tabla_padron IS 'Nombre de la tabla dinámica creada para este proyecto';
COMMENT ON COLUMN proyectos.estructura_padron IS 'Estructura JSON de las columnas del padrón';
COMMENT ON COLUMN plantillas.configuracion IS 'Configuración JSON de mapeo de placeholders';
COMMENT ON COLUMN emisiones_acumuladas.hash_archivo IS 'SHA256 del archivo PDF para verificar integridad';
COMMENT ON COLUMN bitacora.detalles IS 'Detalles específicos de la acción en formato JSON';

-- ============================================
-- FIN DEL SCRIPT
-- ============================================