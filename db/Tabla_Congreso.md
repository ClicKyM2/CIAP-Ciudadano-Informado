---
tags: [api, enlazada]
---

# Tablas: Congreso

Ver [[db/PostgreSQL]] · [[fuentes/Congreso]] · [[contexto/sub/Frontend_HTML]] · [[Mapa_Proyecto]]

---

## Estructura

```
diputado_camara (335) → candidato_id (FK)
  → sesion_camara (1.125) leg 50-58 completa
  → votacion_camara (7.180)
  → voto_diputado (947.256 votos individuales)
  → asistencia_sesion (376.875: 112K presencias + 264K inasistencias)
  → autoria_proyecto → proyecto_ley (7.933 mociones)
```

## Tabla: proyecto_ley

Columnas: `boletin (UNIQUE)`, `titulo`, `fecha_ingreso`, `tipo_iniciativa`, `camara_origen`, `legislatura`, `link`

- 7.933 proyectos de ley
- 251 diputados con mociones
- Fuente: BCN `facetas-buscador-avanzado` (Solr interno) — UNICA fuente valida de mociones

## Tabla: diputado_camara

- 335 / 335 diputados vinculados a `candidato_id`
- 16 diputados recientes sin match en mapa BCN (2024-2025)
- Regenerar mapa: `ingesta_bcn.py --descargar-mapa`

## VIDs por legislatura

- Leg 57/58: rango VID 80.000-85.000
- Para nuevas legislaturas: subir `VID_SCAN_HASTA` en `ingesta_congreso.py`

## Endpoint relacionado

`GET /api/candidatos/:id/congreso` — solo funciona si es diputado. Devuelve `es_diputado: false` para otros cargos.
