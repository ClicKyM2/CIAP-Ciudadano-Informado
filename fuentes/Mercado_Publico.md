---
tags: [enlazada, pipeline]
---

# Fuente: Mercado Publico — OCDS

**Metodo:** Azure Blob Storage (ZIPs mensuales, publico sin ticket) + API OCDS fallback

Ver [[fuentes/CPLT]] · [[db/Tabla_Empresas]] · [[Mapa_Proyecto]]

---

## Datasets

| Tipo | URL | Disponibilidad |
|------|-----|----------------|
| Bulk ZIP | `ocds.blob.core.windows.net/ocds/yyyymm.zip` | 19 meses 2021-2023 |
| API OCDS | `api.mercadopublico.cl/ocds/...` | Meses sin ZIP |

## Tablas que alimenta

- `licitacion` — licitaciones adjudicadas a empresas de candidatos
- `orden_compra` — 138.339 OCs (2022-2026)

## Estado actual

- Licitaciones: 28 meses completados hasta 2022-04. Pendiente: continuar desde 2022-05
- OC: 138.339 ordenes de compra cargadas
- Filtro: solo filas donde `RutSucursal` aparece en `participacion_societaria`

## Bug corregido

Montos > $500.000.000.000 CLP se guardan como NULL — dato corrupto en fuente OCDS.

## Scripts responsables

- `scripts/pipeline/ingesta_mercado_publico.py` — OC, streaming Azure Blob
- `scripts/pipeline/ingesta_licitaciones.py` — licitaciones OCDS, checkpoint en `data/progreso_licitaciones.json`
