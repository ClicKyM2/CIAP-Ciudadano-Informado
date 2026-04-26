---
tags: [contexto, enlazada]
---

## Fuentes de datos — Detalles técnicos

### InfoProbidad (CPLT)
- CSV bulk de acciones: `data/csvacciones.csv` (48.681 filas) — fuente de `participacion_societaria`
  - Columnas: UriDeclaracion, UriDeclarante, Nombre, ApPaterno, ApMaterno, GravamenAccion,
    EntidadAccion, Cantidad, Controlador, FechaAdquisicion, Giro, Pais, RutJuridica, Valor
- CSV declaraciones: `data/csvdeclaraciones.csv` (113.806 registros)
- JSON embebido en HTML con tag `jsonCargado`:
  ```python
  re.search(r'jsonCargado">\s*(\{.*?\})\s*</span>', texto, re.DOTALL)
  ```
- Aplicar `html.unescape()` ANTES del regex
- URLs usan HTTP no HTTPS: `http://datos.cplt.cl/...`
- Obligatorio usar `cloudscraper` (Cloudflare bloquea `requests`)
- El RUT está en: `datos["Datos_del_Declarante"]["RUN"]`
- `MAESTRO_EXPANDIDO.csv` tiene RUTs todos NaN — unir por campo `link_declaracion`

### Ley de Lobby (InfoLobby)
- `data/representaciones.csv` — 1.548.503 filas, encoding UTF-16
  - Columnas: codigoRepresentado, representado, giroRepresentado, codigoAudiencia, personalidad
  - `codigoRepresentado` formato: `699036005r` (RUT + 'r') o hash hex
- Columna de unión: `codigoaudiencia` conecta `temp_asistencia_pasivo` con `temp_audiencia.codigouri`
- `reunion_lobby.empresa_rut` = NULL en todas las filas — no sirve para cruce

### Servel
- Excel en `data/` con encabezados en fila 7
- La columna RUT está vacía en los Excel — RUTs obtenidos desde InfoProbidad
- Consolidado en `MAESTRO_RUTS_CONSOLIDADOS.csv`

---

---

Ver notas detalladas por fuente: [[fuentes/CPLT]] · [[fuentes/Lobby]] · [[fuentes/Servel]] · [[fuentes/Congreso]] · [[fuentes/Mercado_Publico]]

Ver URLs actualizadas de descarga: [[contexto/fuentes_descarga]]

---
*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*
