---
tags: [enlazada, pipeline]
---

# Stack Tecnológico — CIAP

Ver [[Mapa_Proyecto]] · [[arquitectura/Flujo_Pipeline]] · [[arquitectura/Modelo_Datos]] · [[Indice_Arquitectura]]

---

## Capas y tecnologías

```
[Fuentes externas]
    CPLT · Lobby · SERVEL · Mercado Público · BCN
         ↓
[Extracción / Pipeline]
    Python 3.14 + cloudscraper + psycopg2
    pipeline_maestro.py — 18 pasos
         ↓
[Base de datos]
    PostgreSQL 18 — 18 tablas
         ↓
[API]
    Node.js 20 + Express — localhost:3000
         ↓
[Frontend]
    HTML/CSS/JS vanilla
    ciudadano_informado_plataforma.html
```

---

## Por tecnología

### Python 3.14
- **Rol:** extracción, limpieza, ingesta y análisis de datos
- **Paquetes clave:** `cloudscraper` (Cloudflare bypass), `psycopg2` (PostgreSQL), `openpyxl` (Excel SERVEL), `requests`
- **Entorno:** `.venv/` en raíz del proyecto
- **Invocar:** `.venv/Scripts/python.exe script.py` (nunca `python` sin ruta)

### PostgreSQL 18
- **Rol:** único almacén de verdad
- **DB:** `ciudadano_db` en localhost
- **Extensión requerida:** `pg_trgm` (similitud de texto, requerida por IA Fiscalizadora)
- **Regla:** pgAdmin4 manda sobre schema.sql — no modificar schema.sql sin reflejo en pgAdmin
- Ver [[db/PostgreSQL]]

### Node.js 20 + Express
- **Rol:** API REST entre DB y frontend
- **Puerto:** 3000
- **Archivos:** `src/server.js`, `src/controllers/`, `src/routes/`
- **Sin ORM** — SQL directo con `pg` (node-postgres)
- Ver [[src/API_Node]]

### Claude API (claude-haiku-4-5)
- **Rol:** IA Fiscalizadora — genera alertas de probidad
- **Usado en:** `scripts/pipeline/ia_fiscalizadora.py`
- **No usado para:** búsquedas en tiempo real (eso es Tavily MCP)

### HTML/JS Vanilla
- **Rol:** frontend sin framework
- **Archivo:** `contexto/ciudadano_informado_plataforma.html`
- **Restricción:** abrir SIEMPRE desde `http://localhost:3000/` — nunca directo `file://`
- Ver [[contexto/sub/Frontend_HTML]]

---

## MCP Servers activos

| Servidor | Comando | Uso |
|----------|---------|-----|
| gemini-search | `gemini-search-mcp` | Búsqueda web grounded con Gemini |
| obsidian | `obsidian-mcp` | Lectura/escritura del vault Obsidian |

Config en: `~/.claude/mcp.json`

---

*Nota de arquitectura · [[Mapa_Proyecto]] · [[Indice_Arquitectura]]*
