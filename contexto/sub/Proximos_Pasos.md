---
tags: [api, contexto, enlazada, pipeline, planificacion]
---

## Próximos pasos (plan activo)

Ordenados de más fácil a más difícil. Actualizar estado en `estado_proyecto_ciap.html` al completar cada uno.

| # | Tarea | Dificultad | Estado |
|---|-------|-----------|--------|
| 1 | Gobierno Kast — csvdeclaraciones.csv + pipeline | Muy fácil | Completado sesión 11 — 118.760 declaraciones en DB, +116 candidatos Kast agregados (6.801 total), scores recalculados (promedio 46.5). |
| 2 | Completar RUTs faltantes | Fácil | Completado — 884 restantes tienen RUT oculto en CPLT (no recuperables) |
| 3 | Completar participaciones societarias | Fácil | Completado — 3.461 candidatos sin empresas declaradas (explorados) |
| 4 | Licitaciones Mercado Público — ingesta + endpoint + frontend | Media | Completado sesión 15 — 29 meses bulk (2020-01 a 2022-06), 2.341 licitaciones en DB. Bulk OCDS solo existe hasta 2022-06 (404 para todos los meses posteriores), API sin ticket inviable (13K requests/mes). Cerrado aquí. Endpoint GET /api/candidatos/:id/licitaciones activo. Tab frontend activo. |
| 4b | Frontend UX — fix filtro score persistente al seleccionar candidato | Fácil | Completado sesión 15 — selectCandidate() ya no resetea scoreFilter ni displayedCandidates. |
| 5 | Contraloría General | Media | Descartado — sin datos descargables ni API de sumarios/sanciones por nombre |
| 6 | Autenticación y rate limiting — API producción | Media-baja | Completado sesión 12 — express-rate-limit: 300 req/15min general, 80 req/15min en /api/candidatos. |
| 6b | Frontend UX sesión 13 — filtro score persistente, Alertas IA, Guía Ciudadana, banner, tooltip score, tabs condicionales, endpoint /api/alertados | Fácil | Completado sesión 13 |
| 6c | Infraestructura Obsidian sesión 13 — vault, MCP gemini-search + obsidian, hook logging diario/, vault_tagger.py | Fácil | Completado sesión 13 |
| 6d | Knowledge graph Obsidian sesión 14 — 17 notas nuevas (arquitectura/, scripts/, src/, db/, fuentes/), Mapa_Proyecto hub máximo, CLAUDE.md R2 reforzada, Hook Stop + session_end en obsidian_logger.py, R1 a gemini-search | Fácil | Completado sesión 14 |
| 7 | Deploy Railway + Vercel | Media | Pendiente |
| 8 | Alerta IA: LICITACION_PROVEEDOR — empresa gana licitación en organismo del candidato | Media | Sin empezar (requiere que termine ingesta) |
| 9 | Chatbot IA — Claude API + texto-a-SQL | Media-alta | Sin empezar |
| 9 | DIPRES / SIAPER — sueldos (~350 organismos) | Alta | Sin empezar |
| 10 | BCN — proyectos de ley (API SPARQL/RDF) | Alta | Completado sesión 12 — 7.933 proyectos, 251 diputados. Tab "Proyectos" en frontend. Endpoint GET /api/candidatos/:id/proyectos. Ver sección Scripts (paso `bcn`). |
| 11 | Alertas push / email | Alta | Sin empezar |
| 12 | Portal Transparencia Ley 20.285 — ~350 URLs | Muy alta | Sin empezar |
| 13 | Poder Judicial — causas penales, sin API | Muy alta | Sin empezar |
| 14 | App móvil React Native | Muy alta | Sin empezar |

### Detalle de tareas inmediatas

**1. Gobierno Kast**
CSV ya descargado y reemplazado (`data/csvdeclaraciones.csv` = 118.458 filas, respaldo en `data/csvdeclaraciones_2025-03.csv`). Solo falta correr:
```bash
.venv/Scripts/python.exe pipeline_maestro.py --backup --pasos declaraciones,completar,scores
```
Pipeline detectará automáticamente el diferencial (118K CSV > ~113K DB) y re-importará. El `--backup` guarda la DB antes de sobrescribir.

**6. Autenticación y rate limiting**
Agregar `express-rate-limit` + API key básica en `src/server.js` antes de exponer a producción.

**7. Deploy público**
`railway.toml` y `vercel.json` ya creados. Pasos restantes:
- Crear proyecto en Railway → agregar plugin PostgreSQL → configurar variables (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `PORT`, `NODE_ENV`)
- Migrar DB: `pg_dump ciudadano_db | psql <railway-url>` (tablas grandes: `reunion_lobby` 4.8M, `temp_representaciones` 1.5M)
- Si el nombre Railway no es `api-ciudadana`, actualizar URL en el HTML (`api-ciudadana.up.railway.app`)
- Deploy estático en Vercel apuntando a `contexto/ciudadano_informado_plataforma.html`

**8. Alerta LICITACION_PROVEEDOR**
Detectar si empresa de candidato ganó licitación en el mismo organismo donde el candidato trabaja. Agregar detector en `ia_fiscalizadora.py` y recorrer `ia,scores` tras terminar la ingesta.

**9. Chatbot IA**
Claude API + texto-a-SQL sobre PostgreSQL. Prompt del sistema con el schema real. Costo estimado: ~$0.005/pregunta con prompt caching. Integrar al frontend HTML.

### Fuentes de datos futuras — priorizadas por impacto y facilidad

| Fuente | Dato clave | Impacto | Dificultad | Notas |
|--------|-----------|---------|-----------|-------|
| **Contraloría General** | Sumarios, sanciones, dictámenes | Alto | Inviable | Investigado sesión 9 — sin API ni bulk download de sumarios por nombre. robots.txt Disallow:/. Descartado. |
| **DIPRES / SIAPER** | Sueldo exacto de funcionarios | Medio | Alta | ~350 organismos, sin bulk download centralizado |
| **BCN — proyectos de ley** | Proyectos patrocinados, historial legislativo | Medio | Alta | API SPARQL (grafos RDF, no REST/JSON simple) |
| **Poder Judicial** | Causas penales públicas | Alto | Muy alta | Sin API, scraping complejo del portal PJ |
| **Portal Transparencia (Ley 20.285)** | Gastos por institución | Bajo-medio | Muy alta | ~350 URLs distintas, muy disperso |

---
*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*
