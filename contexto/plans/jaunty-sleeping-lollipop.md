---
tags: [api, contexto]
---

# Plan: Actualizar CONTEXTO.md con estado actual del proyecto

## Context

El archivo `contexto/CONTEXTO.md` quedó desactualizado tras múltiples sesiones de trabajo.
Se realizaron cambios significativos en: esquema real de la DB, scripts Python, API Node.js,
y el frontend HTML. Hay que reflejar el estado actual para no perder contexto en próximas sesiones.

---

## Archivo a modificar

`contexto/CONTEXTO.md` — actualización completa en una sola pasada.

---

## Cambios a aplicar sección por sección

### 1. Estado de la DB — reemplazar tabla entera

Valores reales verificados con `\d candidato` y queries directos:

| Tabla | Registros | Estado |
|---|---|---|
| candidato | 6.521 (5.468 RUT real + 1.053 CPLT-N) | Activo |
| participacion_societaria | 3.060 | Poblado desde csvacciones.csv |
| temp_representaciones | 1.548.503 | Importado desde representaciones.csv (UTF-16) |
| match_candidato_lobby | 503.007 | Activo |
| temp_asistencia_pasivo | 894.251 | Activo |
| temp_audiencia | 894.157 | Activo |
| alerta_probidad | 1 | AUTOLOBBY_DETECTADO — LUIS FERNANDO SANCHEZ OSSA |
| reunion_lobby | 4.805.778 | empresa_rut = NULL en todas las filas (no usar para cruce) |

### 2. Esquema real de `candidato` — sección nueva crítica

Columnas reales (verificadas en PostgreSQL 18):
```
id, rut, nombres, apellidos, partido_id, cargo_id, comuna, fuente_url, nombre_limpio, uri_declarante
```

**Gotchas importantes:**
- `apellidos` siempre vacío — el nombre completo está en `nombres` y `nombre_limpio`
- `partido_id` = NULL para los 5.468 candidatos reales
- NO existe `score_transparencia` ni `institucion_id` en la tabla real
- `fuente_url` apunta a la declaración original en datos.cplt.cl

### 3. Capa IA Fiscalizadora — actualizar lógica de cruce

El cruce NO se hace por `reunion_lobby.empresa_rut` (es NULL en el 100% de filas).

Cadena correcta de JOIN:
```
candidato
  → match_candidato_lobby (ON rut)
  → temp_asistencia_pasivo (ON codigo_pasivo)
  → temp_representaciones (ON codigo_audiencia) ← entidad privada que hizo lobby
  → temp_audiencia (ON codigouri)               ← fecha y URL del acta
```

Parámetros actuales de `ia_fiscalizadora.py`:
- `SIMILITUD_MIN = 0.75` (pg_trgm similarity)
- `LONGITUD_MIN_NOMBRE = 6`
- Columna `match_tipo` en `alerta_probidad`: valores `RUT_EXACTO` o `SIMILITUD_NOMBRE`
- `codigo_representado` en formato `693007009r` → RTRIM de 'r' da el RUT empresa

### 4. Capa API Node.js — actualizar endpoints y gotchas

**Servidor:** `node src/server.js` → http://localhost:3000

**Endpoints activos:**
- `GET /api/candidatos?q=texto&page=1&limit=20` — búsqueda por nombre/rut
- `GET /api/candidatos/:id` — perfil completo: datos + empresas + lobby (10) + alertas

**Query de búsqueda** usa `nombre_limpio ILIKE` (no `apellidos` que está vacío).

**Respuesta del perfil:**
```json
{
  "id": 6122, "rut": "169646112", "nombres": "LUIS FERNANDO SANCHEZ OSSA",
  "nombre_limpio": "LUIS FERNANDO SANCHEZ OSSA", "comuna": "VIÑA DEL MAR",
  "cargo": "DIPUTADO", "fuente_url": "http://datos.cplt.cl/...",
  "empresas": [...], "lobby": [...], "alertas": [...]
}
```

**Dependencias Node.js instaladas:** express, pg, dotenv, cors

### 5. Frontend HTML — nueva sección

**Archivo:** `contexto/ciudadano_informado_plataforma.html`

- Se conecta a `http://localhost:3000` (constante `API` al inicio del script)
- Sin hardcode de candidatos — carga via `GET /api/candidatos?limit=50` al abrir
- Búsqueda en tiempo real via `filterCandidates(q)` → fetch async
- Perfil carga via `selectCandidate(id)` → fetch async `GET /api/candidatos/:id`
- Tabs del perfil: **Resumen** / **Empresas** / **Lobby** / **Alertas IA**
- Colores de avatar asignados por cargo (SENADOR/DIPUTADO/ALCALDE/etc.)

### 6. Archivos clave — agregar nuevos

```
data/csvacciones.csv          # 48.681 filas — acciones CPLT (fuente de participacion_societaria)
data/representaciones.csv     # 1.548.503 filas — UTF-16, entidades que hicieron lobby
data/progreso_participaciones.json  # checkpoint del poblar_participaciones.py
importar_representaciones.py  # importa representaciones.csv → temp_representaciones
```

### 7. Notas técnicas — agregar al final

- `cloudscraper` obligatorio para CPLT (Cloudflare bloquea `requests`)
- CPLT URLs: HTTP no HTTPS (`http://datos.cplt.cl/...`)
- JSON embebido en HTML con regex: `jsonCargado">\s*(\{.*?\})\s*</span>`
- Aplicar `html.unescape()` ANTES del regex
- `MAESTRO_EXPANDIDO.csv` tiene RUTs todos NaN — unir por `link_declaracion`
- Windows cp1252: no usar emojis en scripts Python que se corren en terminal Windows
- PostgreSQL 18 instalado en `C:\Program Files\PostgreSQL\18\bin\psql.exe`

### 8. Orden de ejecución — actualizar

```bash
# Estado actual: pasos 1-4 ya completados

# Verificar que el servidor API está corriendo:
node src/server.js    # Puerto 3000

# Para re-poblar participaciones (ya hecho con csvacciones.csv):
python poblar_participaciones.py

# Para re-correr la IA fiscalizadora:
python ia_fiscalizadora.py

# Para importar representaciones (ya hecho):
python importar_representaciones.py
```

---

## Verificación post-edición

Abrir `contexto/ciudadano_informado_plataforma.html` en el navegador con el servidor corriendo en localhost:3000 y verificar que:
1. La lista de candidatos carga al abrir
2. Al buscar "sanchez" aparecen resultados reales
3. Al hacer clic en "LUIS FERNANDO SANCHEZ OSSA" (id=6122) aparece la alerta AUTOLOBBY_DETECTADO en el tab Alertas
