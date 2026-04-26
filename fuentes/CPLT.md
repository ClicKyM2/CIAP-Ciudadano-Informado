---
tags: [enlazada]
---

# Fuente: CPLT — InfoProbidad

**URL base:** `http://datos.cplt.cl` (HTTP, no HTTPS)
**Metodo:** CSV bulk + scraping individual por candidato

Ver [[fuentes/Lobby]] · [[db/Tabla_Empresas]] · [[scripts/Extractores]] · [[Mapa_Proyecto]]

---

## Datasets descargados

| Dataset | Archivo | Filas | Columnas clave |
|---------|---------|-------|----------------|
| Acciones (empresas) | `data/csvacciones.csv` | 48.681 | UriDeclarante, RutJuridica, EntidadAccion, Giro |
| Declaraciones | `data/csvdeclaraciones.csv` | 118.458 | UriDeclaracion, UriDeclarante |
| Actividades | `data/csvactividades.csv` | variable | verificar con limit:3 |

## Gotchas tecnicos

- **Obligatorio `cloudscraper`** — Cloudflare bloquea `requests` normal
- **HTTP no HTTPS** — las URLs de CPLT usan `http://`
- JSON embebido en HTML: `re.search(r'jsonCargado">\s*(\{.*?\})\s*</span>', texto, re.DOTALL)`
- Aplicar `html.unescape()` ANTES del regex
- El RUT esta en: `datos["Datos_del_Declarante"]["RUN"]`
- `MAESTRO_EXPANDIDO.csv` tiene RUTs todos NaN — unir por `link_declaracion`, no por RUT

## URL de descarga actualizada (sesion 12)

`csvacciones.csv` ahora se llama `csvaccionDerecho` en:
`https://datos.cplt.cl/catalogos/infoprobidad/csvaccionDerecho`

Ver [[contexto/fuentes_descarga]] para todas las URLs actualizadas.

## Tablas que alimenta

- [[db/Tabla_Empresas]] — participacion_societaria + empresa_enriquecida
- `declaracion_cplt` (118.760 filas)
- Columna `uri_declarante` en [[db/Tabla_Candidato]]

## Script extractor

`scripts/extractores/cplt.py`
