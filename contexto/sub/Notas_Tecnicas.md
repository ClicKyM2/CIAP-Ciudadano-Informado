---
tags: [contexto, enlazada, pipeline]
---

## Notas técnicas importantes

1. **`.env` NUNCA debe subirse a GitHub** — está en `.gitignore`
2. **`cloudscraper` obligatorio** para cualquier request a `datos.cplt.cl` (Cloudflare)
3. **HTTP no HTTPS** para URLs de CPLT (`http://datos.cplt.cl/...`)
4. **`apellidos` siempre vacío** — usar `nombres` o `nombre_limpio` para mostrar nombre completo
5. **`partido_id` = NULL** para todos los candidatos reales — no mostrar partido
6. **`schema.sql` no refleja la DB real** — la tabla `candidato` real NO tiene `institucion_id`. `score_transparencia` se agrega al correr `calcular_scores.py`
7. **Windows cp1252**: no usar emojis en scripts Python que se corran en terminal Windows — usar ASCII
8. **PostgreSQL 18** instalado en `C:\Program Files\PostgreSQL\18\bin\psql.exe`
13. **Terminal del usuario: Windows PowerShell** — usar `.venv\Scripts\python.exe` (con backslash). Nunca `&` al final. Sin `Start-Job`. Los scripts corren en primer plano directamente.
9. **El cruce lobby** NO se hace por `reunion_lobby.empresa_rut` (siempre NULL) — se hace via `temp_representaciones`
10. **`MAESTRO_EXPANDIDO.csv`** tiene RUTs todos NaN — unir siempre por campo `link_declaracion`
11. **`representaciones.csv`** tiene encoding UTF-16 — abrir con `encoding='utf-16'`
14. **URL de descarga CPLT cambió** — `csvacciones.csv` ahora se llama `csvaccionDerecho` en `https://datos.cplt.cl/catalogos/infoprobidad/csvaccionDerecho`. Ver `contexto/fuentes_descarga.md` para todas las URLs actualizadas.
15. **Gobierno Kast (asumió marzo 2026)** — plazo legal ~mayo 2026. Al 18-04-2026 algunos ministros ya publicaron (Mas, Alvarado, Parot, De Grange, Arzola). Re-descargar `csvdeclaraciones.csv` en mayo 2026 y correr `--pasos declaraciones,completar,scores`.
16. **Monto licitaciones: cap 500B CLP** — en `mercado_publico_licitaciones.py`, montos > $500.000.000.000 CLP se guardan como NULL (datos corruptos en fuente OCDS). Un contrato individual mayor a eso excede el PIB anual en un solo proveedor.
17. **LOBBY_DIR configurable** — todos los scripts que leen/escriben archivos lobby (`limpiar_audiencias_final.py`, `limpiar_asistencias.py`, `arreglar_columnas.py`, `importar_lobby.py`) usan `os.getenv("LOBBY_DIR", r"C:\Users\Public")`. Agregar al `.env` si los archivos están en otra ruta.
18. **Backup automático** — `pipeline_maestro.py --backup` crea `data/backups/YYYY-MM-DD_HHMM/` con CSVs clave + `pg_dump`. Requiere `PG_DUMP` en `.env` con ruta a `pg_dump.exe`. Sin el flag, el pipeline corre sin backup.
19. **Detección automática de declaraciones** — pipeline_maestro.py compara filas de `data/csvdeclaraciones.csv` con `COUNT(*)` de `declaracion_cplt`. Si CSV > DB*0.99, marca el paso como pendiente automáticamente (no requiere --forzar).
20. **BCN SPARQL rate limiting** — `datos.bcn.cl/sparql` bloquea con HTTP 429 tras pocas queries rápidas. Estrategia: descargar el mapa DIPID→BCN_ID en UNA sola query bulk (`ingesta_bcn.py --descargar-mapa`) y guardarlo en `data/mapa_dipid_bcn.json`. Durante la ingesta normal NO se hace ninguna query SPARQL.
21. **BCN — qué funciona y qué no** (investigado sesión 12):
    - `facetas-buscador-avanzado` (Solr interno): ÚNICA fuente válida de mociones. Retorna `boletin` como campo directo.
    - SPARQL para mociones: 0 resultados (grafo de mociones vacío o no indexado).
    - `opendata.camara.cl`: MUERTO (404 HTML en todos los endpoints).
    - Endpoint XLS Labor Parlamentaria: BLOQUEADO por CloudFront (401).
22. **BCN mapa_dipid_bcn.json** — 827 entradas históricas. 319/335 diputados actuales tienen match. 16 sin match son los más recientes (2024-2025) no registrados aún en la ontología BCN. Regenerar periódicamente con `--descargar-mapa`.
12. **pg_trgm** debe estar instalada en PostgreSQL para que funcione `similarity()` en la IA:
    ```sql
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    ```

---

---
*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*
