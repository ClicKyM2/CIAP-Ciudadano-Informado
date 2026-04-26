---
tags: [codigo, enlazada, pipeline]
---

# Pipeline — 18 Pasos

Ver [[Mapa_Proyecto]] · [[arquitectura/Flujo_Pipeline]] · [[scripts/Extractores]] · [[db/PostgreSQL]]

---

## Orquestador

`pipeline_maestro.py` — detecta automáticamente qué pasos necesitan correr.

```bash
# Estado completo sin ejecutar:
.venv/Scripts/python.exe pipeline_maestro.py --estado

# Correr todo con backup:
.venv/Scripts/python.exe pipeline_maestro.py --backup

# Solo pasos específicos:
.venv/Scripts/python.exe pipeline_maestro.py --pasos ia,scores
```

---

## Tabla de pasos

| Paso | Script | Entrada | Salida |
|------|--------|---------|--------|
| `limpiar_audiencias` | `scripts/limpieza/limpiar_audiencias_final.py` | `audiencias.csv` UTF-16 | `$LOBBY_DIR/audiencia_final.csv` |
| `limpiar_asistencias` | `scripts/limpieza/limpiar_asistencias.py` | `asistenciasPasivos.csv` UTF-16 | `$LOBBY_DIR/asistencias_limpio.csv` |
| `arreglar_columnas` | `scripts/herramientas/arreglar_columnas.py` | CSV pasivos | `$LOBBY_DIR/pasivos_final.csv` |
| `ingesta` | `scripts/pipeline/pipeline_ingesta.py` | SERVEL CSV + Excel | tabla `candidato` (6.685 filas) |
| `representaciones` | `scripts/pipeline/importar_representaciones.py` | `representaciones.csv` UTF-16 1.5M | tabla `temp_representaciones` |
| `lobby` | `scripts/pipeline/importar_lobby.py` | CSVs lobby limpios | `temp_audiencia`, `match_candidato_lobby` |
| `congreso` | `scripts/pipeline/ingesta_congreso.py` | API opendata.congreso.cl | `diputado_camara`, `votacion_camara` |
| `declaraciones` | `scripts/pipeline/importar_declaraciones.py` | `csvdeclaraciones.csv` | tabla `declaracion_cplt` |
| `consolidador` | `scripts/herramientas/consolidador_maestro.py` | `funcionarios_rescatados*.csv` | `MAESTRO_RUTS_CONSOLIDADOS.csv` |
| `cruce_infoprobidad` | `scripts/herramientas/cruce_infoprobidad.py` | `csvdeclaraciones.csv` + candidato | columna `uri_declarante` en candidato |
| `completar` | `scripts/pipeline/completar_candidatos.py` | csvdeclaraciones + diputado_camara | nuevas filas en `candidato` |
| `ruts` | `scripts/pipeline/extraer_ruts_infoprobidad.py` | candidato sin RUT | columna `rut` en candidato |
| `participaciones` | `scripts/pipeline/poblar_participaciones.py` | candidato con uri_declarante | tabla `participacion_societaria` |
| `enriquecimiento` | `scripts/pipeline/enriquecer_empresas.py` | csvacciones + CMF | `empresa_enriquecida`, alertas |
| `mercado_publico` | `scripts/pipeline/ingesta_mercado_publico.py` | Azure Blob OCDS | tabla `orden_compra` |
| `licitaciones` | `scripts/pipeline/ingesta_licitaciones.py` | Azure Blob ZIPs | tabla `licitacion` |
| `financiamiento_servel` | `scripts/pipeline/ingesta_financiamiento_servel.py` | Excel SERVEL 60MB | `financiamiento_electoral`, `donante_electoral` |
| `ia` | `scripts/pipeline/ia_fiscalizadora.py` | múltiples tablas | tabla `alerta_probidad` |
| `scores` | `scripts/pipeline/calcular_scores.py` | candidato + alertas | `score_transparencia` en candidato |

**Nota:** `financiamiento_servel` debe correr ANTES de `ia`.

---

Ver detalle completo en [[contexto/sub/Pipeline_Scripts]].

---

*Sub-nota de [[Mapa_Proyecto]] · [[arquitectura/Flujo_Pipeline]]*
