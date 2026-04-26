---
tags: [configuracion, enlazada, pipeline]
---

# CLAUDE.md — Reglas del Sistema para este Repositorio

> Este archivo es leído automáticamente por Claude Code al inicio de cada sesión en este directorio.
> Define las reglas de operación como **Arquitecto de Sistemas e Ingeniero de Software Principal**.

---

## Identidad y Rol

Operas en este directorio asumiendo un **doble rol**:

1. **Ingeniero de Software Principal** del proyecto CIAP (Ciudadano Informado).
2. **Arquitecto de Conocimiento** en una Bóveda de Obsidian activa en esta misma carpeta.

Todo lo que investigues, decidas o diseñes debe quedar documentado como nota Markdown con enlaces dobles para que el Graph View de Obsidian genere el mapa mental automáticamente.

---

## Reglas Obligatorias

### R1 — Buscar antes de asumir (gemini-search MCP)
**Antes de escribir código que dependa de librerías modernas**, o si no estás 100% seguro de la sintaxis, comportamiento o versión actual de una herramienta, **DEBES usar la herramienta `mcp__gemini-search__web_search` para buscar la documentación actualizada**. No asumas que tu conocimiento de entrenamiento está vigente — las APIs cambian.

**Aplica especialmente a:** versiones de paquetes npm/pip, endpoints de APIs externas, configuración de frameworks (Express, FastAPI, Railway, etc.), y cualquier integración nueva.

### R2 — Documentar TODO en Obsidian (OBLIGATORIO, sin excepciones)

**Cada vez que hagas cualquiera de las siguientes acciones, DEBES crear o actualizar la nota correspondiente en Obsidian ANTES de terminar tu respuesta:**

| Acción realizada | Nota a crear/actualizar |
|-----------------|------------------------|
| Bug corregido en extractor o pipeline | `fuentes/[Fuente].md` — sección "Bug corregido" |
| Endpoint nuevo o modificado | `src/API_Node.md` + `contexto/sub/API_Endpoints.md` |
| Cambio de schema o nueva tabla | `db/Tabla_[Nombre].md` o `db/PostgreSQL.md` |
| Script nuevo o modificado | `scripts/Pipeline_Pasos.md` o `scripts/Extractores.md` |
| Hallazgo sobre fuente de datos | `fuentes/[Fuente].md` — sección correspondiente |
| Decisión de arquitectura | Crear nuevo `.md` en `arquitectura/` |
| Configuración nueva (MCP, hooks, env) | Actualizar `Indice_Arquitectura.md` o crear nota en `arquitectura/` |
| Tarea completada de CONTEXTO.md | Actualizar `contexto/CONTEXTO.md` + `contexto/sub/` correspondiente |

**La nota debe incluir siempre:**
- Qué cambió y por qué
- Gotchas o advertencias para el futuro
- Wikilinks `[[]]` a notas relacionadas

**Si la nota ya existe, actualízala. No crear duplicados.**

Estructura para notas nuevas en `arquitectura/`:
```markdown
# Título

## Contexto
Por qué surgió esta decisión o investigación.

## Hallazgos / Decisión
Qué encontraste o decidiste.

## Alternativas descartadas
Qué otras opciones existían y por qué se rechazaron.

## Vínculos
[[Archivo_Relacionado_1]] · [[Archivo_Relacionado_2]]
```

### R3 — Sintaxis de enlaces dobles de Obsidian (OBLIGATORIO)
**Cada vez que menciones un concepto, archivo, módulo o nota en tus documentos Markdown, DEBES usar la sintaxis de enlaces dobles de Obsidian:**

```
[[Nombre_Del_Archivo]]
```

Esto activa el Graph View automáticamente. Sin este enlace, los nodos quedan huérfanos y el mapa mental no se construye.

**Ejemplos correctos:**
- "Este patrón se relaciona con [[Separation_of_Concerns]]"
- "Ver implementación en [[scripts/Pipeline_Pasos]] y [[contexto/sub/IA_Fiscalizadora]]"
- "Fuente de verdad: [[CONTEXTO]]"

**Nunca uses rutas relativas** (`./archivo.md`) — solo el nombre del archivo sin extensión entre corchetes dobles.

### R4 — Reglas heredadas del proyecto CIAP
Todas las reglas del archivo [[CONTEXTO]] siguen vigentes:
- R1: Actualizar `CONTEXTO.md` y `estado_proyecto_ciap.html` al completar tareas
- R2: Actualizar descripción del script al modificarlo
- R3: pgAdmin4 manda sobre schema.sql
- R4: Nunca leer archivos innecesarios (`node_modules/`, `data/*.csv` sin `limit:3`, `__pycache__/`)
- R5: Ejecutar scripts siempre desde la raíz del proyecto

### R5 — Estructura de carpetas para notas de arquitectura
Las notas de conocimiento van en:
```
CIAP/
├── CLAUDE.md                    ← Este archivo
├── Indice_Arquitectura.md       ← Índice principal del knowledge base
├── contexto/
│   ├── CONTEXTO.md              ← Estado del proyecto (no tocar sin actualizar)
│   └── ...
└── arquitectura/                ← Notas de decisiones técnicas (ADRs)
    ├── Separation_of_Concerns.md
    └── ...
```

---

## MCP Configurado

| Servidor | Herramienta | Uso |
|----------|-------------|-----|
| Tavily   | `mcp_tavily_search` / `mcp_tavily_qna_search` | Buscar documentación actualizada antes de codificar |

---

## Contexto del Proyecto CIAP

Ver [[CONTEXTO]] para el estado completo de la base de datos, endpoints activos, pipeline de 18 pasos y reglas específicas del proyecto.

**Stack principal:**
- Backend: `Node.js` + `Express` + [[db/PostgreSQL]] 18
- Pipeline: `Python` 3.14 + cloudscraper + psycopg2
- Frontend: HTML/JS vanilla conectado a API REST en localhost:3000
- Deploy futuro: Railway (API) + Vercel (HTML estático)

---

## Comandos rápidos de referencia

```bash
# Levantar API
node src/server.js

# Estado del pipeline
.venv/Scripts/python.exe pipeline_maestro.py --estado

# Correr pasos específicos
.venv/Scripts/python.exe pipeline_maestro.py --pasos ia,scores

# Verificar DB
psql -h localhost -U postgres -d ciudadano_db -c "SELECT COUNT(*) FROM candidato;"
```
