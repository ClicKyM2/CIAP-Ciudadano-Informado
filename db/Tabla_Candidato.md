---
tags: [enlazada]
---

# Tabla: candidato

Tabla central del proyecto. Todo join parte o termina aqui.

Ver [[db/PostgreSQL]] · [[contexto/sub/Esquema_Candidato]] · [[Mapa_Proyecto]]

---

## Columnas reales (verificar en pgAdmin4)

```
id, rut, nombres, apellidos, partido_id, cargo_id, comuna,
fuente_url, nombre_limpio, uri_declarante, score_transparencia
```

## Gotchas criticos

| Campo | Comportamiento real |
|-------|---------------------|
| `apellidos` | **Siempre vacio** — usar `nombres` y `nombre_limpio` |
| `partido_id` | **NULL en todos** — no hay datos de partido en la DB |
| `score_transparencia` | No estaba en el schema original. Lo agrega `calcular_scores.py` con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` |
| `institucion_id` | Aparece en `schema.sql` pero **NO existe en la DB real** |
| `uri_declarante` | Link a declaracion CPLT. 6.513 de 6.801 tienen valor. |

## Busqueda correcta

```sql
-- Buscar por nombre (NO por apellidos):
SELECT * FROM candidato WHERE nombre_limpio ILIKE '%fernandez%';

-- Nunca usar:
SELECT * FROM candidato WHERE apellidos ILIKE '%...%'; -- siempre vacio
```

## Relaciones

```
candidato (id)
  → participacion_societaria (candidato_id)  [[db/Tabla_Empresas]]
  → alerta_probidad (candidato_id)           [[db/Tabla_Alertas]]
  → match_candidato_lobby (rut)              [[db/Tabla_Lobby]]
  → declaracion_cplt (uri_declarante)
  → financiamiento_electoral (candidato_id)
  → diputado_camara (candidato_id)           [[db/Tabla_Congreso]]
  → orden_compra (via participacion)
```

## Numeros actuales

- Total: 6.801 (+116 Gobierno Kast, sesion 11)
- Con RUT real: 5.601
- Con uri_declarante: 6.513
- Score promedio: 46.5 / 100
