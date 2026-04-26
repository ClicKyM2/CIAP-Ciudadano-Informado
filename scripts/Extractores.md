---
tags: [codigo, enlazada]
---

# Extractores — scripts/extractores/

Ver [[Mapa_Proyecto]] · [[scripts/Pipeline_Pasos]] · [[fuentes/CPLT]] · [[fuentes/Lobby]]

---

## Extractores disponibles

| Script | Fuente | Qué hace |
|--------|--------|----------|
| `scripts/extractores/cplt.py` | CPLT InfoProbidad | Scraping individual por candidato. Requiere `cloudscraper`. Extrae RUT desde JSON embebido en HTML. |
| `scripts/extractores/lobby.py` | InfoLobby CSV | Procesamiento CSV UTF-16 de representaciones/audiencias |
| `scripts/extractores/congreso.py` | opendata.congreso.cl | Descarga votaciones y asistencia por VID. 8 threads. |
| `scripts/extractores/mercado_publico.py` | Azure Blob OCDS | Descarga ZIPs mensuales, filtra por RUTs de participacion_societaria |
| `scripts/extractores/gobierno_local.py` | SERVEL Excel | Procesa Excel de candidatos y autoridades |

---

## Extractor CPLT — detalles

```python
# Requiere cloudscraper (no requests normal — Cloudflare bloquea)
import cloudscraper
scraper = cloudscraper.create_scraper()

# HTTP no HTTPS — obligatorio
url = "http://datos.cplt.cl/..."

# JSON embebido en HTML:
datos = re.search(r'jsonCargado">\s*(\{.*?\})\s*</span>', texto, re.DOTALL)
# Aplicar html.unescape() ANTES del regex
rut = datos["Datos_del_Declarante"]["RUN"]
```

Ver [[fuentes/CPLT]] para URLs actualizadas (csvaccionDerecho).

---

## Patrón común

Todos los extractores en pipeline usan:
1. **Checkpoint JSON** en `data/progreso_*.json` — permiten reanudar sin perder trabajo
2. **Skip logic** — si la tabla destino ya tiene el volumen esperado, no re-importa
3. **Variables de entorno** desde `.env` en la raíz

---

*Sub-nota de [[scripts/Pipeline_Pasos]] · [[Mapa_Proyecto]]*
