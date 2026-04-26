---
tags: [contexto, fuentes-datos, pipeline]
---

# Fuentes de datos — CIAP: Guía completa de descarga y reprocesamiento

Cada sección documenta **qué es el dato, de dónde viene, cómo descargarlo, qué script lo procesa y qué tabla llena**.
Si en el futuro necesitas re-descargar o extender una fuente, esta es la referencia.

---

## Índice

| # | Fuente | Método | Estado |
|---|--------|--------|--------|
| 1 | [InfoProbidad (CPLT)](#1-infoprobidad-cplt) | CSV bulk vía navegador | Completo |
| 2 | [Ley de Lobby (InfoLobby)](#2-ley-de-lobby-infolobby) | CSV bulk vía navegador | Completo |
| 3 | [SERVEL — Candidatos y financiamiento](#3-servel--candidatos-y-financiamiento) | Excel descargado + script automático | Completo |
| 4 | [Mercado Público — Licitaciones OCDS](#4-mercado-público--licitaciones-ocds) | Bulk ZIP Azure + API OCDS pública | En curso |
| 5 | [Mercado Público — Órdenes de Compra](#5-mercado-público--órdenes-de-compra) | Bulk ZIP Azure (script automático) | Completo |
| 6 | [Congreso (Cámara de Diputadas)](#6-congreso-cámara-de-diputadas) | API REST pública opendata.congreso.cl | Completo |
| 7 | [CMF — Directorio de empresas](#7-cmf--directorio-de-empresas) | Scraping portal CMF | Completo |
| 8 | [SII — Giro y razón social](#8-sii--giro-y-razón-social) | CSV local (CAPTCHA bloqueó scraping) | Completo |
| 9 | [Fuentes descartadas o futuras](#9-fuentes-descartadas-o-futuras) | — | Ver detalle |

---

## 1. InfoProbidad (CPLT)

**Qué es:** Declaraciones de patrimonio e intereses de ~120K funcionarios públicos chilenos.
También incluye participaciones societarias (empresas declaradas) y actividades.

**Portal:** https://www.infoprobidad.cl/DatosAbiertos/Catalogos

### Por qué usamos CSV bulk y no scraping individual

La opción natural sería scrapear cada declaración individual desde `datos.cplt.cl`. El problema:
- Cloudflare bloquea `requests` de Python → hay que usar `cloudscraper`
- Con `cloudscraper` funciona, pero es lento (~1-2s/candidato) y solo para los ~6.800 nuestros
- Los CSV bulk contienen TODO el universo de funcionarios (118K declaraciones, 48K acciones)
- **Decisión:** usar CSV bulk para la masa de datos, `cloudscraper` solo para datos puntuales (ej: rescatar RUTs individuales)

### Archivos disponibles

| Archivo local | URL de descarga | Tamaño | Tabla destino |
|---------------|-----------------|--------|---------------|
| `data/csvdeclaraciones.csv` | https://datos.cplt.cl/catalogos/infoprobidad/csvdeclaraciones | ~400MB | `declaracion_cplt` |
| `data/csvacciones.csv` | https://datos.cplt.cl/catalogos/infoprobidad/csvaccionDerecho | ~50MB | `participacion_societaria`, `empresa_enriquecida` |
| `data/csvactividades.csv` | https://datos.cplt.cl/catalogos/infoprobidad/csvactividades | ~30MB | Sin tabla propia aún |

**IMPORTANTE:** La URL cambió. El archivo de acciones ahora se llama `csvaccionDerecho` en la URL (antes era `csvacciones`). Al descargar, renombrar a `data/csvacciones.csv`.

### Cómo descargar (obligatorio vía navegador)

1. Abrir Chrome o Firefox
2. Pegar cada URL de la tabla de arriba
3. El archivo empieza a bajar directamente (no hay formulario)
4. Mover el archivo descargado a `data/` con el nombre correcto

**No intentar bajar con Python/curl** — Cloudflare bloquea sin excepción. Solo funciona el navegador.

### Cuándo volver a descargar

- **csvdeclaraciones.csv:** Cada vez que el gobierno cambia o hay plazo de actualización masiva.
  - Gobierno Kast asumió marzo 2026. Plazo legal ~60 días → descargar en **mayo 2026**.
  - Al 23-04-2026: ministros Mas, Alvarado, Parot, De Grange, Arzola ya publicaron.
- **csvacciones.csv:** Solo si necesitas más empresas (es histórico, no cambia frecuentemente).

### Scripts que lo procesan

```powershell
# Tras actualizar csvdeclaraciones.csv:
.venv\Scripts\python.exe pipeline_maestro.py --pasos declaraciones,completar,scores

# Tras actualizar csvacciones.csv:
.venv\Scripts\python.exe pipeline_maestro.py --pasos participaciones,enriquecimiento,ia,scores
```

| Script | Entrada | Salida |
|--------|---------|--------|
| `scripts/pipeline/importar_declaraciones.py` | `data/csvdeclaraciones.csv` | tabla `declaracion_cplt` (118.760 filas) |
| `scripts/pipeline/poblar_participaciones.py` | `data/csvacciones.csv` + tabla `candidato` | tabla `participacion_societaria` (6.903 filas) |
| `scripts/pipeline/enriquecer_empresas.py` | `data/csvacciones.csv` | tabla `empresa_enriquecida` (2.782 filas) |

### Gotchas técnicos

- `UriDeclarante` es la clave de unión entre candidatos y declaraciones (no el RUT)
- El RUT del declarante está en la página individual: `http://datos.cplt.cl/datos/infoprobidad/{uri}` — campo `datos["Datos_del_Declarante"]["RUN"]`
- `MAESTRO_EXPANDIDO.csv` tiene RUTs todos NaN — no usar para join por RUT, usar `link_declaracion`
- `csvacciones.csv` columnas clave: `UriDeclarante`, `EntidadAccion`, `RutJuridica`, `Giro`

---

## 2. Ley de Lobby (InfoLobby)

**Qué es:** Registro de reuniones entre funcionarios públicos (pasivos) y privados (activos/representados).
Cubre ~894K audiencias y 1.5M representaciones desde 2014.

**Portal:** https://www.infolobby.cl/datos-abiertos

### Por qué importamos CSV y no usamos la API

InfoLobby tiene API pública, pero:
- Paginación lenta, rate limits
- El CSV bulk contiene exactamente los mismos datos y es una sola descarga
- Los archivos CSV son los datos definitivos en UTF-16 (encoding de Windows)

### Archivos a descargar

| Archivo local | Nombre en portal | Encoding | Tamaño | Tabla destino |
|---------------|-----------------|---------|--------|---------------|
| `$LOBBY_DIR/audiencias.csv` | Audiencias | UTF-16 | ~1.2GB | `temp_audiencia` |
| `$LOBBY_DIR/asistenciasPasivos.csv` | Asistencias de Pasivos | UTF-16 | ~600MB | `temp_asistencia_pasivo` |
| `data/representaciones.csv` | Representaciones | UTF-16 | ~300MB | `temp_representaciones` |

`$LOBBY_DIR` es la variable de entorno en `.env` (default: `C:\Users\Public`).

### Cómo descargar

1. Ir a https://www.infolobby.cl/datos-abiertos
2. Descargar los 3 archivos (son los que tienen más filas)
3. Colocar `audiencias.csv` y `asistenciasPasivos.csv` en `$LOBBY_DIR`
4. Colocar `representaciones.csv` en `data/`

### Por qué la unión no se hace por `reunion_lobby.empresa_rut`

**TRAMPA CRÍTICA:** La tabla `reunion_lobby` (importación antigua) tiene `empresa_rut = NULL` en todas las filas.
La columna `empresa_nombre` contiene la institución del *funcionario*, no la empresa privada que hace lobby.

La unión correcta va por:
```
candidato → match_candidato_lobby → temp_asistencia_pasivo → temp_representaciones → temp_audiencia
```

Los scripts que importan estas tablas hacen esa cadena automáticamente.

### Scripts que lo procesan

```powershell
# Limpiar y luego importar:
.venv\Scripts\python.exe pipeline_maestro.py --pasos limpiar_audiencias,limpiar_asistencias,arreglar_columnas,lobby
```

| Script | Entrada | Salida |
|--------|---------|--------|
| `scripts/limpieza/limpiar_audiencias_final.py` | `$LOBBY_DIR/audiencias.csv` (UTF-16) | `$LOBBY_DIR/audiencia_final.csv` (UTF-8) |
| `scripts/limpieza/limpiar_asistencias.py` | `$LOBBY_DIR/asistenciasPasivos.csv` (UTF-16) | `$LOBBY_DIR/asistencias_limpio.csv` |
| `scripts/herramientas/arreglar_columnas.py` | `$LOBBY_DIR/pasivos_limpio.csv` | `$LOBBY_DIR/pasivos_final.csv` |
| `scripts/pipeline/importar_lobby.py` | archivos limpios | tablas `temp_audiencia`, `temp_asistencia_pasivo`, `match_candidato_lobby` |
| `scripts/pipeline/importar_representaciones.py` | `data/representaciones.csv` (UTF-16) | tabla `temp_representaciones` |

### Cuándo volver a importar

Los datos de lobby son históricos — no se actualizan frecuentemente. Re-importar solo si:
- Se descarga una versión nueva del portal (más audiencias)
- Se agrega un bloque nuevo de candidatos que requieren cruce

Skip automático: si las tablas ya tienen >1M filas, el script las salta.

---

## 3. SERVEL — Candidatos y financiamiento

### 3a. Lista de candidatos (autoridades electas 2024)

**Qué es:** Nómina de alcaldes, concejales, gobernadores, diputados y senadores electos en 2024.

**Cómo obtuvimos los datos:**
- Excel descargado desde servel.cl en sesiones 1-2
- El Excel tiene encabezados en fila 7, datos desde fila 8
- La columna RUT estaba vacía → RUTs se obtuvieron después via InfoProbidad

**Archivo local:** `data/servel_autoridades.csv` (ya limpio)
**Script:** `scripts/pipeline/pipeline_ingesta.py` → tabla `candidato`

Si en una próxima elección (2028) hay que actualizar:
1. Descargar nuevo Excel desde servel.cl
2. Ajustar número de fila de encabezado en `pipeline_ingesta.py` si cambió
3. Correr `pipeline_maestro.py --pasos ingesta,cruce_infoprobidad,completar,ruts`

### 3b. Financiamiento electoral 2024

**Qué es:** Ingresos y gastos de campaña por candidato, con detalle de donantes. ~339K transacciones.

**URL:** El script descarga automáticamente desde servel.cl (Excel ~60MB)
**Archivo local:** `data/Reporte_Ingresos_Gastos_Definitivas2024.xlsx`
- Header en fila 11, datos desde fila 12

**Script:** `scripts/pipeline/ingesta_financiamiento_servel.py`
**Tablas:** `financiamiento_electoral` (15.739 filas), `donante_electoral` (338.911 transacciones)

```powershell
.venv\Scripts\python.exe pipeline_maestro.py --solo financiamiento_servel
```

**Gotcha:** El match de candidatos usa normalización de nombre + CARGO_MAP + territorio (3 niveles de fallback). Si un candidato no matchea, el financiamiento queda sin vincular pero igual se importa.

---

## 4. Mercado Público — Licitaciones OCDS

**Qué es:** Procesos licitatorios donde el Estado compra servicios/bienes. Filtramos solo los que adjudicaron a empresas de candidatos.

### Por qué no usamos la API clásica de Mercado Público

La API en `api.mercadopublico.cl/servicios/v1/publico/licitaciones.json` requiere **ticket gratuito** pero:
- El trámite de obtención es lento
- La API OCDS pública (`api.mercadopublico.cl/APISOCDS/`) **no requiere ticket**
- ChileCompra además publica ZIPs mensuales (bulk) en Azure sin autenticación

**Decisión:** usar OCDS siempre (bulk ZIP si está disponible, API OCDS como fallback).

### Fuentes disponibles

**Modo BULK (preferido):** ZIPs mensuales en Azure, sin ticket
- URL patrón: `https://ocds.blob.core.windows.net/ocds/{yyyymm}.zip`
- Disponible: 2021-01 a 2022-04, y meses de 2023 (verificar con HEAD request)
- Tamaño: ~500MB por mes (contiene un JSON OCDS por licitación)

**Modo API OCDS (fallback automático):** para meses sin bulk
- Lista: `https://api.mercadopublico.cl/APISOCDS/OCDS/listaOCDSAgnoMes/{anio}/{mes}/{desde}/{hasta}`
- Detalle: `https://api.mercadopublico.cl/APISOCDS/OCDS/award/{codigo}`
- Sin ticket. 10 threads concurrentes. PAGE_SIZE=999.

### Estado actual (23-04-2026)

- Completados: 28 meses (2020-01 a 2022-04) → 2.178 licitaciones, 178 candidatos, $312B CLP
- Pendiente: 2022-05 en adelante (~47 meses)
- Checkpoint: `data/progreso_licitaciones.json`

### Cómo correr

```powershell
# Continuar desde donde quedó:
.venv\Scripts\python.exe scripts\pipeline\ingesta_licitaciones.py

# Ver estado sin ejecutar:
.venv\Scripts\python.exe scripts\pipeline\ingesta_licitaciones.py --estado

# Correr desde un año específico:
.venv\Scripts\python.exe scripts\pipeline\ingesta_licitaciones.py --desde-anio 2023
```

### Gotchas

- Montos > $500.000.000.000 CLP se guardan como NULL (datos corruptos en fuente OCDS)
- La tabla tiene UNIQUE(codigo, rut_adjudicatario) → re-correr es seguro (ON CONFLICT DO NOTHING)
- El bulk ZIP puede ser de ~500MB por mes → necesita ~2GB de espacio libre en temp
- El campo `nombre` de la licitación se deja NULL (no está en el formato OCDS que usamos)

---

## 5. Mercado Público — Órdenes de Compra

**Qué es:** Órdenes de compra directas (no licitaciones), donde el Estado compra a proveedores.
Filtramos las donde proveedor = empresa de candidato. ~138K filas relevantes.

**Fuente:** Azure Blob Storage (público, sin ticket)
- URL patrón: `https://transparenciachc.blob.core.windows.net/oc-da/{año}-{mes}.zip`

**Script:** `scripts/pipeline/ingesta_mercado_publico.py`
**Tabla:** `orden_compra`
**Checkpoint:** `data/progreso_mercado_publico.json`

```powershell
.venv\Scripts\python.exe pipeline_maestro.py --solo mercado_publico
```

El script descarga streaming, filtra por `RutSucursal` de `participacion_societaria` y guarda solo las relevantes.

---

## 6. Congreso (Cámara de Diputadas)

**Qué es:** Votaciones, asistencia y datos de diputados, leg. 50-58 (2002-2026).
7.180 votaciones, 947K votos individuales, 376K registros de asistencia.

**API pública:** `https://opendata.congreso.cl/`
- Sin ticket
- Sin rate limit documentado (8 threads funcionaron bien)

### Cómo investigamos los VIDs (IDs de votación)

Los VIDs no son consecutivos ni predecibles. El script escanea rangos de IDs:
- Leg 50-56: VIDs en rango 0-79.999
- Leg 57-58: VIDs en rango 80.000-85.000
- Para nuevas legislaturas (>58): subir `VID_SCAN_HASTA` a 100.000+ en `ingesta_congreso.py`

**Script:** `scripts/pipeline/ingesta_congreso.py`
**Tablas:** `diputado_camara`, `sesion_camara`, `votacion_camara`, `voto_diputado`, `asistencia_sesion`
**Checkpoint:** `data/progreso_congreso.json`

```powershell
.venv\Scripts\python.exe pipeline_maestro.py --solo congreso
```

### Cuándo volver a correr

- Nueva legislatura (cada 4 años, próxima 2026): subir VID_SCAN_HASTA y re-correr
- También re-correr tras elecciones si diputados cambian de partido o si hay nuevos diputados por elecciones parciales

---

## 7. CMF — Directorio de empresas

**Qué es:** Directores de SA abiertas, fondos de inversión y compañías de seguros registradas en CMF.
Detecta si un candidato es director de empresa fiscalizada sin declararlo en CPLT.

**Portal:** https://www.cmfchile.cl/sitio/aplic/serdoc/ver_sgd.php (scraping)

### Por qué scraping y no bulk

CMF no publica CSV ni API pública. Los directorios están en HTML/PDF por empresa.
El extractor navega el listado de empresas y extrae directores de cada una.

**Script:** `scripts/extractores/cmf.py` + invocado desde `enriquecer_empresas.py`
**Tabla:** `directorio_cmf` (5.766 filas)
**Duración:** ~4.5 horas (correr nocturno)

```powershell
.venv\Scripts\python.exe pipeline_maestro.py --solo enriquecimiento
# o solo la parte CMF:
.venv\Scripts\python.exe scripts\pipeline\enriquecer_empresas.py --solo-cmf
```

**Gotcha:** El portal CMF es lento. El script tiene reintentos automáticos. Si falla a mitad, re-correr — tiene checkpoint.

---

## 8. SII — Giro y razón social

**Qué es:** Ramo de actividad económica y nombre oficial de las empresas declaradas por candidatos.
Enriquece la tabla `empresa_enriquecida` con datos SII.

### Por qué CSV local y no scraping

Se intentó scrapear `zeus.sii.cl` pero tiene CAPTCHA que bloqueó completamente el acceso automático.
**Solución alternativa:** El CSV bulk de CPLT (`csvacciones.csv`) ya incluye los campos `Giro` y `RutJuridica`,
que corresponden exactamente a los datos SII. Se extraen directamente del CSV.

- 2.782 empresas únicas → 2.782/2.782 enriquecidas (100%) desde `csvacciones.csv`
- No se requiere ninguna descarga adicional de SII

**Script:** `scripts/pipeline/enriquecer_empresas.py --solo-csv`
**Tabla:** `empresa_enriquecida`

---

## 9. Fuentes descartadas o futuras

### Contraloría General de la República

**Dato deseado:** Sumarios, sanciones y dictámenes por funcionario.

**Por qué descartado:** Investigado en sesión 9.
- `robots.txt` tiene `Disallow:/` (prohíbe scraping explícitamente)
- No existe API pública ni bulk download de sumarios por nombre
- El buscador web es un formulario con anti-bots
- **Decisión:** Descartado indefinidamente. No hay forma limpia de obtener los datos.

---

### Poder Judicial — Causas penales

**Dato deseado:** Causas penales públicas contra funcionarios.

**Estado:** Sin empezar. Muy alta dificultad.
- Sin API pública
- El portal PJ requiere scraping complejo (captcha, sesiones)
- Los datos son nominativos (nombre), no por RUT → alto riesgo de falsos positivos

---

### DIPRES / SIAPER — Sueldos

**Dato deseado:** Sueldo exacto de cada funcionario público.

**Estado:** Sin empezar. Alta dificultad.
- ~350 organismos con portales separados
- Sin bulk download centralizado
- SIAPER (Sistema de Información y Control del Personal) tiene datos pero acceso restringido

---

### Portal Transparencia Activa (Ley 20.285)

**Dato deseado:** Gastos por institución, contratos, viáticos.

**Estado:** Sin empezar. Muy alta dificultad.
- ~350 URLs distintas (una por organismo)
- Formato inconsistente entre organismos
- Algunos en PDF, otros en HTML, algunos en Excel

---

### BCN — Proyectos de ley

**Dato deseado:** Proyectos de ley patrocinados, historial legislativo completo.

**Estado:** Sin empezar. Alta dificultad.
- La API usa SPARQL sobre grafos RDF (no REST/JSON simple)
- Requiere conocer el modelo de datos del grafo BCN
- El Congreso ya cubre votaciones — esto agregaría patrocinio de proyectos

---

## Notas generales

- **Cloudflare bloquea Python** en `datos.cplt.cl` — siempre descargar en navegador
- **UTF-16** en todos los archivos de lobby — abrir con `encoding='utf-16'`
- **Usar siempre `.venv\Scripts\python.exe`** (nunca solo `python`)
- **Scripts corren en primer plano** desde la raíz del proyecto (no `cd scripts/ && python`)
- **El pipeline detecta automáticamente** qué pasos están desactualizados — usar `--estado` para ver
