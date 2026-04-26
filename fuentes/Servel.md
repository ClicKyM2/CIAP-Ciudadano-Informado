---
tags: [enlazada, pipeline]
---

# Fuente: SERVEL — Financiamiento Electoral

**URL:** `servel.cl` (descarga automatica en `ingesta_financiamiento_servel.py`)
**Metodo:** Excel definitivo ~60MB, header en fila 11, datos desde fila 12

Ver [[fuentes/CPLT]] · [[db/Tabla_Candidato]] · [[Mapa_Proyecto]]

---

## Datasets

| Dataset | Archivo | Filas | Descripcion |
|---------|---------|-------|-------------|
| Candidatos 2024 | Excel SERVEL | 6.685 | Alcaldes, concejales, gobernadores electos |
| Financiamiento electoral | `Reporte_Ingresos_Gastos_Definitivas2024.xlsx` | 338.911 | Ingresos y gastos por candidato |

## Tablas que alimenta

- [[db/Tabla_Candidato]] — los 6.685 funcionarios base del proyecto
- `financiamiento_electoral` — 15.739 registros (2.402 candidatos vinculados)
- `donante_electoral` — 338.911 transacciones, 12.255 donantes unicos

## Match candidato → financiamiento

Por `normalizar(nombre) + CARGO_MAP + territorio` (3 niveles de fallback).

## Script responsable

`scripts/pipeline/ingesta_financiamiento_servel.py`
Debe correr **antes de `ia`** — `ia_fiscalizadora.py` usa `donante_electoral`.
