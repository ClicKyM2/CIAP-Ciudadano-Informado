---
tags: [enlazada, pipeline]
---

# Fuente: InfoLobby — Ley de Lobby

**URL:** `http://datos.infolobby.cl`
**Metodo:** CSV descargado (UTF-16) + importacion masiva

Ver [[fuentes/CPLT]] · [[db/Tabla_Lobby]] · [[contexto/sub/IA_Fiscalizadora]] · [[Mapa_Proyecto]]

---

## Datasets

| Dataset | Filas | Encoding | Gotcha |
|---------|-------|----------|--------|
| `representaciones.csv` | 1.548.503 | **UTF-16** | Abrir con `encoding='utf-16'` |
| `audiencias.csv` | 894.157 | UTF-16 | Limpiar antes con `limpiar_audiencias_final.py` |
| `asistenciasPasivos.csv` | 894.251 | UTF-16 | Limpiar con `limpiar_asistencias.py` |

## Columnas clave de representaciones.csv

`codigoRepresentado`, `representado`, `giroRepresentado`, `codigoAudiencia`, `personalidad`

Formato de `codigoRepresentado`: `699036005r` → RTRIM('r') = RUT empresa

## ALERTA CRITICA

`reunion_lobby.empresa_rut` = NULL en TODAS las filas.
Ver [[db/Tabla_Lobby]] para el JOIN correcto.

## Variables de entorno

```
LOBBY_DIR=C:\Users\Public   # carpeta con los CSVs del lobby
```
Todos los scripts de lobby usan `os.getenv("LOBBY_DIR", r"C:\Users\Public")`.

## Scripts relacionados

- `scripts/limpieza/limpiar_audiencias_final.py`
- `scripts/limpieza/limpiar_asistencias.py`
- `scripts/pipeline/importar_lobby.py`
