---
tags: [enlazada, pipeline]
---

# Tablas: Empresas

Ver [[db/PostgreSQL]] · [[fuentes/CPLT]] · [[db/Tabla_Alertas]] · [[Mapa_Proyecto]]

---

## Flujo de enriquecimiento

```
csvacciones.csv (CPLT, 48.681 filas)
  → participacion_societaria (6.903 filas)
  → empresa_enriquecida (2.782 empresas, 100% enriquecidas)
  → directorio_cmf (5.766 directores en SA abiertas)
```

## Tabla: participacion_societaria

| Campo | Descripcion |
|-------|-------------|
| candidato_id | FK a candidato |
| empresa_rut | RUT de la empresa declarada |
| empresa_nombre | Nombre segun CPLT |
| porcentaje_propiedad | Puede ser 0 (accionista minoritario) |

- 2.556 candidatos con al menos 1 empresa declarada
- Fuente: `data/csvacciones.csv` (columnas: UriDeclarante, RutJuridica, EntidadAccion, Giro)

## Tabla: empresa_enriquecida

Enriquecida con datos SII via `csvacciones.csv` (CAPTCHA de zeus.sii.cl roto — se usa CSV local).
- 2.782 / 2.782 empresas enriquecidas (100%)

## Tabla: directorio_cmf

- 5.766 directores en empresas fiscalizadas por CMF (SA abiertas, fondos, seguros)
- Fuente: scraping portal CMF via `scripts/extractores/cmf.py`
- Genera alertas tipo `DIRECTOR_NO_DECLARADO` en [[db/Tabla_Alertas]]

## Script responsable

`scripts/pipeline/enriquecer_empresas.py` — flags: `--solo-csv`, `--solo-cmf`, `--solo-alertas`, `--estado`
