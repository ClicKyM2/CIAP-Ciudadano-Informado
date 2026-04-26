-- Tablas Base (Catálogos)
CREATE TABLE partido (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE cargo (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    nivel VARCHAR(50) -- EJ: NACIONAL, REGIONAL, LOCAL
);

CREATE TABLE institucion (
    id SERIAL PRIMARY KEY,
    rut VARCHAR(12) UNIQUE,
    nombre VARCHAR(255) NOT NULL
);

-- Tabla Principal: Políticos / Autoridades
CREATE TABLE candidato (
    id SERIAL PRIMARY KEY,
    rut VARCHAR(12) UNIQUE NOT NULL,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    partido_id INTEGER REFERENCES partido(id),
    cargo_id INTEGER REFERENCES cargo(id),
    institucion_id INTEGER REFERENCES institucion(id),
    score_transparencia INTEGER DEFAULT 100,
    uri_declarante VARCHAR(255)
);

-- Tabla: Patrimonio (Empresas del político extraídas del CPLT)
CREATE TABLE participacion_societaria (
    id SERIAL PRIMARY KEY,
    candidato_id INTEGER REFERENCES candidato(id) ON DELETE CASCADE,
    empresa_rut VARCHAR(12) NOT NULL,
    empresa_nombre VARCHAR(255),
    porcentaje_propiedad DECIMAL(5,2),
    UNIQUE(candidato_id, empresa_rut)
);

-- Tabla: Ley de Lobby (Reuniones)
CREATE TABLE reunion_lobby (
    id SERIAL PRIMARY KEY,
    candidato_id INTEGER REFERENCES candidato(id) ON DELETE CASCADE,
    empresa_rut VARCHAR(12),
    empresa_nombre VARCHAR(255),
    fecha DATE NOT NULL,
    materia TEXT,
    url_referencia TEXT,
    UNIQUE(candidato_id, empresa_rut, fecha)
);
CREATE INDEX idx_lobby_candidato_empresa ON reunion_lobby(candidato_id, empresa_rut);

-- Tabla: Alertas de Probidad (Resultados de la IA)
CREATE TABLE alerta_probidad (
    id SERIAL PRIMARY KEY,
    candidato_id INTEGER REFERENCES candidato(id) ON DELETE CASCADE,
    tipo VARCHAR(100) NOT NULL, -- Ej: CONFLICTO_INTERES_LOBBY
    gravedad VARCHAR(50) NOT NULL, -- ALTA, MEDIA, BAJA
    detalle TEXT NOT NULL,
    fecha_deteccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fuente_url TEXT
);
CREATE INDEX idx_alerta_candidato ON alerta_probidad(candidato_id);
CREATE INDEX idx_alerta_gravedad ON alerta_probidad(gravedad);

-- Tabla: Órdenes de Compra de Mercado Público (empresas de candidatos como proveedores)
CREATE TABLE orden_compra (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50),
    nombre TEXT,
    estado VARCHAR(100),
    fecha_creacion DATE,
    monto_pesos BIGINT,
    rut_organismo VARCHAR(15),
    nombre_organismo TEXT,
    rut_proveedor VARCHAR(15),
    nombre_proveedor TEXT,
    codigo_licitacion VARCHAR(50),
    link TEXT,
    anio SMALLINT,
    mes SMALLINT,
    candidato_id INTEGER REFERENCES candidato(id),
    UNIQUE(codigo, anio, mes)
);
CREATE INDEX idx_oc_candidato ON orden_compra(candidato_id);
CREATE INDEX idx_oc_rut_proveedor ON orden_compra(rut_proveedor);
CREATE INDEX idx_oc_fecha ON orden_compra(fecha_creacion);