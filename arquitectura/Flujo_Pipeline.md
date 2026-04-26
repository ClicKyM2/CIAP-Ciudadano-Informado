---
tags: [enlazada, pipeline]
---

# Flujo del Pipeline — 18 Pasos

Ver [[Mapa_Proyecto]] · [[scripts/Pipeline_Pasos]] · [[arquitectura/Stack_Tecnologico]] · [[db/PostgreSQL]]

---

## Diagrama de flujo

```mermaid
graph TD
    A[CSV Lobby UTF-16] --> P1[limpiar_audiencias]
    A2[asistenciasPasivos UTF-16] --> P2[limpiar_asistencias]
    P2 --> P3[arreglar_columnas]

    SERVEL[SERVEL autoridades.csv + Excel] --> P4[ingesta]
    P4 --> candidato[(tabla: candidato)]

    P1 --> P6[lobby]
    P3 --> P6
    P5[representaciones] --> P6
    P6 --> match_lobby[(match_candidato_lobby)]

    API_CONGRESO[opendata.congreso.cl + BCN] --> P7[congreso + bcn]
    P7 --> congreso_db[(diputado_camara, votaciones, proyecto_ley)]

    CSV_CPLT[csvdeclaraciones.csv] --> P8[declaraciones]
    P8 --> declaracion_cplt[(declaracion_cplt)]

    CSV_CPLT --> P10[cruce_infoprobidad]
    P10 --> candidato

    P11[completar] --> candidato

    P12[ruts] --> candidato

    CPLT_WEB[CPLT web scraping] --> P13[participaciones]
    P13 --> participacion[(participacion_societaria)]

    participacion --> P14[enriquecimiento]
    CMF[CMF portal] --> P14
    SII[csvacciones.csv] --> P14
    P14 --> empresa_enriquecida[(empresa_enriquecida)]
    P14 --> alertas[(alerta_probidad)]

    AZURE[Azure Blob OCDS] --> P15[mercado_publico]
    P15 --> orden_compra[(orden_compra)]

    SERVEL_EXCEL[Excel SERVEL 60MB] --> P16[financiamiento_servel]
    P16 --> financiamiento[(financiamiento_electoral, donante_electoral)]

    candidato --> P17[ia_fiscalizadora]
    match_lobby --> P17
    participacion --> P17
    orden_compra --> P17
    financiamiento --> P17
    P17 --> alertas

    candidato --> P18[scores]
    declaracion_cplt --> P18
    participacion --> P18
    alertas --> P18
    P18 --> score[(score_transparencia en candidato)]
```

---

## Resumen de pasos

| # | Paso | Tiempo aprox. | Skipeable |
|---|------|---------------|-----------|
| 1 | `limpiar_audiencias` | ~2 min | Si ya existe CSV limpio |
| 2 | `limpiar_asistencias` | ~2 min | Si ya existe CSV limpio |
| 3 | `arreglar_columnas` | <1 min | Si ya existe CSV final |
| 4 | `ingesta` | ~5 min | Si candidato tiene ≥6.685 filas |
| 5 | `representaciones` | ~10 min | Si temp_representaciones >1M filas |
| 6 | `lobby` | ~3 min | Si tablas >500K/100K filas |
| 7 | `congreso` | ~30 min | Con checkpoint progreso_congreso.json |
| 8 | `declaraciones` | ~2 min | Si csvdeclaraciones no tiene más filas |
| 9 | `consolidador` | <1 min | Si no hay archivos _rescatados pendientes |
| 10 | `cruce_infoprobidad` | ~5 min | Si uri_declarante ya está asignado |
| 11 | `completar` | ~2 min | Idempotente |
| 12 | `ruts` | ~20 min | 1.017 pendientes, ~1-2s/candidato |
| 13 | `participaciones` | ~2h+ | 4.766 pendientes, con checkpoint |
| 14 | `enriquecimiento` | ~10 min | Con flags --solo-csv/--solo-cmf |
| 15 | `mercado_publico` | ~15 min | Con checkpoint, filtra por RUTs |
| 16 | `financiamiento_servel` | ~5 min | Debe correr ANTES de `ia` |
| 17 | `ia` (ia_fiscalizadora) | ~20 min | Regenera todas las alertas |
| 18 | `scores` | ~2 min | Recalcula score_transparencia |

---

## Comandos

```bash
# Ver estado sin ejecutar:
.venv/Scripts/python.exe pipeline_maestro.py --estado

# Correr todo:
.venv/Scripts/python.exe pipeline_maestro.py --backup

# Solo pasos específicos:
.venv/Scripts/python.exe pipeline_maestro.py --pasos ia,scores
```

---

*Nota de arquitectura · [[Mapa_Proyecto]] · [[scripts/Pipeline_Pasos]]*
