---
tags: [contexto, enlazada]
---

## Esquema real de la tabla `candidato` — CRÍTICO

Columnas verificadas en PostgreSQL:
```
id, rut, nombres, apellidos, partido_id, cargo_id, comuna, fuente_url, nombre_limpio, uri_declarante
```

**Gotchas que queman tiempo:**
- `apellidos` siempre vacío para los 5.468 candidatos reales — el nombre completo está en `nombres` y `nombre_limpio`
- `partido_id` = NULL para TODOS los candidatos reales (no hay datos de partido en la DB)
- `score_transparencia` — creado por `calcular_scores.py` con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (no estaba en la DB original, el script lo agrega). Fórmula: base 0, +25 declaración CPLT reciente, +20 empresas declaradas, +20 sujeto pasivo en lobby, +15 sin alertas ALTA; penaliza -20 alerta ALTA, -10 alerta MEDIA, -15 declaración antigua. Clamp 0-100.
- NO existe `institucion_id` — está en schema.sql pero no en la DB real
- `fuente_url` apunta a la declaración original en datos.cplt.cl
- Para buscar por nombre usar `nombre_limpio ILIKE` o `nombres ILIKE`, nunca `apellidos`

---

---
*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*
