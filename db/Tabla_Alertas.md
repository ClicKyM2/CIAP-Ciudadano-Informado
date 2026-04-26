---
tags: [enlazada, pipeline]
---

# Tabla: alerta_probidad

Output de la IA Fiscalizadora. Se genera al correr el paso `ia` del pipeline.

Ver [[db/PostgreSQL]] · [[contexto/sub/IA_Fiscalizadora]] · [[db/Tabla_Candidato]] · [[Mapa_Proyecto]]

---

## Distribucion actual

| Tipo | Total | Gravedad |
|------|-------|---------|
| AUTOLOBBY_DETECTADO | 30 | ALTA |
| DIRECTOR_NO_DECLARADO | 5 | ALTA |
| CONFLICTO_FAMILIAR_POSIBLE | ~563 | MEDIA / BAJA |
| **TOTAL** | **~598** | 35 ALTA · 563 MEDIA/BAJA |

## Tipos de alerta

**AUTOLOBBY_DETECTADO** — El funcionario hizo lobby activo a favor de una empresa que el mismo declaro como propia. Match via `pg_trgm` similitud ≥ 0.75.

**DIRECTOR_NO_DECLARADO** — El funcionario aparece en `directorio_cmf` pero no declaro esa empresa en CPLT.

**DONANTE_PROVEEDOR** — El donante electoral del candidato es ademas proveedor del estado (cruce donante_electoral × orden_compra).

**CONFLICTO_FAMILIAR_POSIBLE** — Apellido infrecuente compartido entre el candidato y un lobbista. Gravedad MEDIA si persona natural, BAJA si empresa.

## Filtros anti-falsos-positivos

- `APELLIDOS_COMUNES` — 100+ apellidos frecuentes (GONZALEZ, RODRIGUEZ...) excluidos
- `MAX_CANDIDATOS_POR_APELLIDO = 10` — apellido muy extendido se ignora
- `APELLIDO_MIN_LEN = 6` — apellidos cortos ignorados
- `NOMBRES_PILA` — nombres de pila no se confunden con apellidos

## Script responsable

`scripts/pipeline/ia_fiscalizadora.py` — paso `ia` del `pipeline_maestro.py`
Requiere extension PostgreSQL: `CREATE EXTENSION IF NOT EXISTS pg_trgm;`
