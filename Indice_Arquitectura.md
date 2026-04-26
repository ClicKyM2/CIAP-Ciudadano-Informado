---
tags: [arquitectura, enlazada, indice, pipeline]
---

# Índice de Arquitectura — CIAP

Bóveda de Obsidian para el proyecto **Ciudadano Informado / CIAP**.  
Usa el **Graph View** (`Ctrl+G`) para ver las relaciones entre módulos.

---

## Documentos de Arquitectura

| Documento | Descripción |
|-----------|-------------|
| [[Mapa_Proyecto]] | Hub máximo — punto de entrada visual al grafo completo |
| [[Separation_of_Concerns]] | Separación de responsabilidades entre capas del sistema |
| [[contexto/CONTEXTO]] | Estado completo del proyecto, DB, pipeline, API, frontend |
| [[arquitectura/Stack_Tecnologico]] | Tecnologías por capa: Python, PostgreSQL, Node.js, Claude API |
| [[arquitectura/Flujo_Pipeline]] | Diagrama Mermaid de los 18 pasos con entradas/salidas |
| [[arquitectura/Modelo_Datos]] | Relaciones entre tablas núcleo y anomalías críticas |

---

## Capas del Sistema

```
FUENTES EXTERNAS
    ↓  (scripts/extractores/)
PIPELINE DE DATOS  →  data/MAESTRO_EXPANDIDO.csv
    ↓  (scripts/pipeline/)
BASE DE DATOS PostgreSQL
    ↓  (src/)
API Node.js / Express
    ↓
FRONTEND HTML  →  contexto/ciudadano_informado_plataforma.html
```

### 1. Fuentes de datos
- [[fuentes/CPLT]] — Declaraciones de patrimonio e intereses (cplt.cl)
- [[fuentes/Lobby]] — Reuniones lobbistas (lobby.cl)
- [[fuentes/Servel]] — Candidatos + financiamiento de campaña
- [[fuentes/Mercado_Publico]] — Licitaciones con empresas relacionadas
- [[fuentes/Congreso]] — Proyectos de ley y votaciones de diputados

### 2. Pipeline Python
Ver [[scripts/Pipeline_Pasos]] — 18 pasos con entradas/salidas.  
Ver [[scripts/Extractores]] — extractores individuales por fuente.  
Ver [[scripts/Herramientas]] — herramientas del vault y pipeline.

### 3. Base de Datos
Ver [[db/PostgreSQL]] — hub con 18 tablas.  
Tablas núcleo: [[db/Tabla_Candidato]] · [[db/Tabla_Lobby]] · [[db/Tabla_Empresas]] · [[db/Tabla_Congreso]] · [[db/Tabla_Alertas]]

### 4. API Node.js
Ver [[src/API_Node]] — estructura de archivos y controladores.  
Ver [[contexto/sub/API_Endpoints]] — documentación completa de cada endpoint.

### 5. Frontend
Archivo: `contexto/ciudadano_informado_plataforma.html`  
Ver [[contexto/sub/Frontend_HTML]] — vistas y comportamiento.

---

## Decisiones de Diseño

- [[Separation_of_Concerns]] — por qué cada capa existe por separado
- **`displayedCandidates` vs `allCandidates`** — el filtro de score no debe borrar los datos del servidor; se persiste en variable separada

---

## MCP Servers Configurados

| Servidor | Comando | Uso |
|----------|---------|-----|
| tavily | `npx tavily-mcp@0.2.19` | Búsqueda de documentación actualizada |

Configuración en: `~/.claude/mcp.json`  
Para activar: reiniciar Claude Code después de agregar la API key de Tavily.

---

## Stack Técnico

| Capa | Tecnología |
|------|-----------|
| Extracción | Python 3.14 + requests + BeautifulSoup |
| Almacenamiento | PostgreSQL 18 |
| IA Fiscalizadora | Claude API (claude-haiku-4-5) |
| API | Node.js + Express |
| Frontend | HTML/CSS/JS vanilla |
| MCP | Tavily (búsqueda web) |
