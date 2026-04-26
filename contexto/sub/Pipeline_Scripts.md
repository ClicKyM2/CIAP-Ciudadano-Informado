---
tags: [contexto, enlazada, pipeline]
---

## Scripts del pipeline — descripción detallada

Cada paso de `pipeline_maestro.py` llama a uno de estos scripts. Se listan en orden de ejecución.

| Paso | Script | Entrada | Salida | Notas |
|------|--------|---------|--------|-------|
| `limpiar_audiencias` | `scripts/limpieza/limpiar_audiencias_final.py` | `audiencias.csv` UTF-16 | `$LOBBY_DIR/audiencia_final.csv` UTF-8 | Conversión de encoding. LOBBY_DIR = env var (default `C:\Users\Public`). Requerida antes de importar lobby |
| `limpiar_asistencias` | `scripts/limpieza/limpiar_asistencias.py` | `asistenciasPasivos.csv` UTF-16 | `$LOBBY_DIR/asistencias_limpio.csv` | Idem. Usa LOBBY_DIR configurable |
| `arreglar_columnas` | `scripts/herramientas/arreglar_columnas.py` | `pasivos_limpio.csv` | `$LOBBY_DIR/pasivos_final.csv` | Ajusta estructura a 10 columnas. Usa LOBBY_DIR configurable |
| `ingesta` | `scripts/pipeline/pipeline_ingesta.py` | `data/servel_autoridades.csv` + Excel Servel | tabla `candidato` en PostgreSQL | ETL principal. Crea o actualiza los 6.685 funcionarios. Normaliza Unicode en nombres. |
| `representaciones` | `scripts/pipeline/importar_representaciones.py` | `data/representaciones.csv` (UTF-16, 1.5M filas) | tabla `temp_representaciones` | Carga masiva. Tarda ~5-10 min. Encoding crítico: `encoding='utf-16'`. **Skip logic**: si `temp_representaciones` ya tiene >1M filas, sale sin re-importar. |
| `lobby` | `scripts/pipeline/importar_lobby.py` | `$LOBBY_DIR/audiencia_final.csv` (UTF-8) + `$LOBBY_DIR/asistenciasPasivos.csv` (UTF-16) | tablas `temp_audiencia`, `temp_asistencia_pasivo`, `match_candidato_lobby` | Usa LOBBY_DIR configurable. `match_candidato_lobby` via `pg_trgm` umbral 0.25 (la IA refina a 0.75). Skips si tablas ya tienen >500K / >100K filas. |
| `congreso` | `scripts/pipeline/ingesta_congreso.py` | API `opendata.congreso.cl` | tablas `sesion_camara`, `votacion_camara`, `voto_diputado`, `asistencia_sesion`, `diputado_camara` | Escanea VIDs con 8 threads. Checkpoint en `data/progreso_congreso.json`. VID_SCAN_HASTA=85000. Leg 57/58 en rango 80K-85K. Para nuevas legs subir a 100K+. |
| `declaraciones` | `scripts/pipeline/importar_declaraciones.py` | `data/csvdeclaraciones.csv` (118K filas, Kast parcial) | tabla `declaracion_cplt` | Vincula por `uri_declarante`. Re-correr cada vez que se descarga el CSV actualizado. pipeline_maestro.py detecta automáticamente si el CSV tiene más filas que la DB y lo marca como pendiente. |
| `consolidador` | `scripts/herramientas/consolidador_maestro.py` | `data/funcionarios_rescatados*.csv` (incluye `_bots.csv` del nuevo bot unificado) | `data/MAESTRO_RUTS_CONSOLIDADOS.csv` | Solo necesita correr si hay archivos de RUTs rescatados pendientes de consolidar |
| `cruce_infoprobidad` | `scripts/herramientas/cruce_infoprobidad.py` | `data/csvdeclaraciones.csv` + tabla `candidato` | columna `uri_declarante` en `candidato` | Match de nombres normalizado (sin tildes, uppercase). Asigna el link CPLT a cada candidato para todos los cruces posteriores. |
| `completar` | `scripts/pipeline/completar_candidatos.py` | `data/csvdeclaraciones.csv` + tabla `diputado_camara` | filas nuevas en `candidato`, `candidato_id` en `diputado_camara` | Agrega políticos que no estaban en Servel (gobierno actual, ex-diputados históricos). Normalización Unicode para match con encoding roto. |
| `ruts` | `scripts/pipeline/extraer_ruts_infoprobidad.py` | tabla `candidato` (candidatos sin RUT real) | columna `rut` en `candidato` | Usa `cloudscraper` para scrapear RUT desde página individual CPLT. Lento: ~1-2s por candidato. 1.017 pendientes. |
| `participaciones` | `scripts/pipeline/poblar_participaciones.py` | tabla `candidato` (con uri_declarante) | tabla `participacion_societaria` | Usa `cloudscraper` para obtener empresas declaradas desde CPLT. Checkpoint en `data/progreso_participaciones.json`. 4.766 pendientes. |
| `enriquecimiento` | `scripts/pipeline/enriquecer_empresas.py` | `data/csvacciones.csv` + portal CMF | tablas `empresa_enriquecida`, `directorio_cmf`, alertas en `alerta_probidad` | Flags: `--solo-csv`, `--solo-cmf`, `--solo-alertas`, `--estado`. Genera alertas DIRECTOR_NO_DECLARADO deduplicadas por (candidato, empresa) via STRING_AGG. |
| `mercado_publico` | `scripts/pipeline/ingesta_mercado_publico.py` | Azure Blob Storage `oc-da` (público, sin ticket) | tabla `orden_compra` | Descarga ZIPs mensuales 2022-presente. Streaming: filtra por `RutSucursal` de `participacion_societaria`. Checkpoint en `data/progreso_mercado_publico.json`. |
| `licitaciones` | `scripts/pipeline/ingesta_licitaciones.py` | OCDS bulk ZIP `ocds.blob.core.windows.net/ocds/yyyymm.zip` (19 meses 2021-2023 disponibles) + API OCDS para el resto | tabla `licitacion` | Modo automático: usa bulk ZIP si disponible, API OCDS con 10 threads si no. Filtra por RUTs de `participacion_societaria`. Checkpoint en `data/progreso_licitaciones.json`. Flags: `--desde-anio YYYY`, `--estado`. |
| `financiamiento_servel` | `scripts/pipeline/ingesta_financiamiento_servel.py` | Excel SERVEL ~60MB (`Reporte_Ingresos_Gastos_Definitivas2024.xlsx`, header fila 11, datos desde fila 12) | tablas `financiamiento_electoral` y `donante_electoral` | **Debe correr antes de `ia`** — `ia_fiscalizadora.py` usa tabla `donante_electoral`. Descarga automática desde servel.cl. Match candidato por normalizar(nombre) + CARGO_MAP + territorio (3 niveles fallback). 338.911 transacciones, 2.402 candidatos vinculados. |
| `ia` | `scripts/pipeline/ia_fiscalizadora.py` | tablas `candidato`, `match_candidato_lobby`, `temp_representaciones`, `participacion_societaria`, `orden_compra`, `donante_electoral` | tabla `alerta_probidad` | Detecta 3 tipos: AUTOLOBBY_DETECTADO (funcionario hace lobby a empresa propia), CONFLICTO_FAMILIAR_POSIBLE (apellidos raros compartidos con lobbistas), DONANTE_PROVEEDOR (donante electoral que además es proveedor del estado). Filtros anti-falsos-positivos: APELLIDOS_COMUNES (100+), NOMBRES_PILA, MAX_CANDIDATOS_POR_APELLIDO=10, APELLIDO_MIN_LEN=6. Gravedad FAMILIAR: MEDIA=persona natural, BAJA=empresa. Requiere `pg_trgm`. |
| `scores` | `scripts/pipeline/calcular_scores.py` | tablas `candidato`, `declaracion_cplt`, `participacion_societaria`, `alerta_probidad`, `match_candidato_lobby` | columna `score_transparencia` en `candidato` | Fórmula: base 0, +25 declaración reciente, +20 empresas declaradas, +20 en lobby pasivo, +15 sin alertas ALTA. Penaliza: -20 ALTA, -10 MEDIA, -15 declaración antigua. Clamp 0-100. |
| `bcn` | `scripts/pipeline/ingesta_bcn.py` | `data/mapa_dipid_bcn.json` + BCN facetas-buscador-avanzado (Solr) | tablas `proyecto_ley` y `autoria_proyecto` | Flags: `--estado`, `--descargar-mapa` (regenera mapa DIPID→BCN via SPARQL bulk). Lee mapa local sin queries SPARQL individuales. 1.0s delay por diputado, 0.5s entre páginas. 319/335 diputados con BCN ID (16 recientes sin mapping). 7.933 proyectos, 251 diputados con mociones. |

---


## Orden de ejecución del pipeline

Usar siempre `pipeline_maestro.py` — detecta automáticamente qué necesita correr.

**Flags disponibles:**
- `--estado` — diagnóstico completo sin ejecutar nada (muestra conteos reales de la DB)
- `--lista` — lista los IDs de todos los pasos con su estado [OK/NO EXISTE]
- `--solo PASO` — corre solo ese paso (forzado)
- `--pasos P1,P2,...` — corre lista específica en orden (ej: `--pasos ia,scores,declaraciones`)
- `--desde PASO` — corre desde ese paso en adelante
- `--forzar PASO` — re-corre ese paso y todos los siguientes aunque estén al día
- `--backup` — crea backup timestamped de CSVs clave + pg_dump antes de correr el pipeline

**Orden de pasos (20 en total):**
`limpiar_audiencias` → `limpiar_asistencias` → `arreglar_columnas` → `ingesta` → `representaciones` → `lobby` → `congreso` → `bcn` → `declaraciones` → `consolidador` → `cruce_infoprobidad` → `completar` → `ruts` → `participaciones` → `enriquecimiento` → `mercado_publico` → `licitaciones` → `financiamiento_servel` → `ia` → `scores`

**Fuentes pendientes de extractor (agregar al pipeline cuando estén listos):**
- `dipres_siaper` — sueldos por funcionario (~350 organismos, sin bulk, scraping)
- `poder_judicial` — causas penales públicas (sin API, scraping complejo)
- `portal_transparencia` — gastos ley 20.285 (~350 URLs distintas)

```bash
# Ver estado completo de la DB sin ejecutar nada:
.venv/Scripts/python.exe pipeline_maestro.py --estado

# Listar todos los pasos disponibles:
.venv/Scripts/python.exe pipeline_maestro.py --lista

# Correr todo el pipeline con backup previo (recomendado):
.venv/Scripts/python.exe pipeline_maestro.py --backup

# Correr pasos específicos (ej: tras actualizar csvdeclaraciones.csv):
.venv/Scripts/python.exe pipeline_maestro.py --pasos declaraciones,completar,scores

# Correr con backup antes del pipeline (crea carpeta data/backups/YYYY-MM-DD_HHMM/):
.venv/Scripts/python.exe pipeline_maestro.py --backup --pasos declaraciones,completar,scores

# Forzar re-ejecución de un paso y todos los siguientes:
.venv/Scripts/python.exe pipeline_maestro.py --forzar ia

# Levantar la API:
node src/server.js    # Puerto 3000

# Verificar alertas en PostgreSQL:
# SELECT c.nombres, a.tipo, a.gravedad, a.detalle
# FROM alerta_probidad a JOIN candidato c ON c.id = a.candidato_id
# ORDER BY a.gravedad, a.fecha_deteccion DESC;
```

---

---
*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*
