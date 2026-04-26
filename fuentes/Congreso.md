---
tags: [enlazada, pipeline]
---

# Fuente: Congreso + BCN

**APIs:**
- `opendata.congreso.cl` — votaciones y asistencia
- BCN `facetas-buscador-avanzado` (Solr) — proyectos de ley
- `datos.bcn.cl/sparql` — SPARQL bulk para mapa DIPID→BCN_ID

Ver [[fuentes/CPLT]] · [[db/Tabla_Congreso]] · [[Mapa_Proyecto]]

---

## Datasets y estado

| Fuente | Contenido | Estado |
|--------|-----------|--------|
| opendata.congreso.cl | Votaciones + asistencia leg 50-58 | Completo. 7.180 votaciones, 947K votos |
| BCN Solr (`facetas-buscador-avanzado`) | Mociones de diputados | Completo. 7.933 proyectos, 251 diputados |
| BCN SPARQL | Mapa DIPID→BCN_ID | Guardado en `data/mapa_dipid_bcn.json` (827 entradas) |

## Gotchas tecnicos

- BCN SPARQL: limita con HTTP 429 si se hacen muchas queries. Usar `--descargar-mapa` UNA vez y guardar local.
- 16 diputados recientes (2024-2025) sin match en el mapa DIPID→BCN
- VIDs de leg 57/58 en rango 80.000-85.000. Para nuevas legs subir `VID_SCAN_HASTA`
- `opendata.camara.cl` — MUERTO (404 HTML)
- XLS Labor Parlamentaria — BLOQUEADO por CloudFront (401)

## Scripts responsables

- `scripts/pipeline/ingesta_congreso.py` — 8 threads, checkpoint en `data/progreso_congreso.json`
- `scripts/pipeline/ingesta_bcn.py` — flags: `--estado`, `--descargar-mapa`
