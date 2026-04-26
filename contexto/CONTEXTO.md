---
tags: [contexto, enlazada, fuente-de-verdad, pipeline]
---

# CONTEXTO DEL PROYECTO — CIUDADANO INFORMADO (CIAP)

> Archivo hub. Las secciones extensas viven en sub-notas enlazadas abajo.

## Sub-notas

- [[sub/API_Endpoints]]
- [[sub/Archivos_Clave]]
- [[sub/Esquema_Candidato]]
- [[sub/Estado_DB]]
- [[sub/Frontend_HTML]]
- [[sub/Fuentes_Datos]]
- [[sub/IA_Fiscalizadora]]
- [[sub/Notas_Tecnicas]]
- [[sub/Pipeline_Scripts]]
- [[sub/Proximos_Pasos]]

---

---


## ÍNDICE DE SECCIONES

| Sección | Qué encontrarás |
|---------|-----------------|
| [INSTRUCCIONES PARA CLAUDE](#instrucciones-para-claude--leer-antes-de-empezar) | Cómo leer el proyecto, qué no leer, regla de CSVs |
| [REGLAS OBLIGATORIAS](#reglas-obligatorias) | Todas las reglas que Claude debe cumplir en este proyecto |
| [¿Qué es este proyecto?](#qué-es-este-proyecto) | Descripción, origen, objetivo |
| [Arquitectura — 4 Capas](#arquitectura--4-capas) | Fuentes de datos, pipeline, API, frontend — lista de scripts |
| [Estado actual de la DB](#estado-actual-de-la-base-de-datos-postgresql-18) | Números reales verificados: candidatos, empresas, alertas, congreso |
| [Esquema real de `candidato`](#esquema-real-de-la-tabla-candidato--crítico) | Columnas reales + gotchas que queman tiempo |
| [La IA Fiscalizadora](#la-ia-fiscalizadora--lógica-real-de-cruce) | Lógica de cruce, cadena de JOINs, parámetros |
| [API Node.js — Endpoints](#api-nodejs--endpoints-activos) | Todos los endpoints con ejemplos de respuesta |
| [Archivos de seguimiento](#archivos-de-seguimiento-del-proyecto) | estado_proyecto_ciap.html y cómo actualizarlo |
| [Frontend HTML](#frontend-html-ciudadano_informado_plataformahtml) | Estructura del frontend, tabs, helpers |
| [Fuentes de datos — Detalles técnicos](#fuentes-de-datos--detalles-técnicos) | CPLT, Lobby, Servel — gotchas de cada fuente |
| [Archivos clave del proyecto](#archivos-clave-del-proyecto) | Árbol de directorios con descripción |
| [Scripts del pipeline](#scripts-del-pipeline--descripción-detallada) | Tabla con entrada/salida/notas de cada uno de los 18 pasos |
| [Orden de ejecución](#orden-de-ejecución-del-pipeline) | Comandos de uso de pipeline_maestro.py |
| [Variables de entorno](#variables-de-entorno-requeridas-env) | .env requerido |
| [Notas técnicas](#notas-técnicas-importantes) | Gotchas globales del proyecto |
| [Próximos pasos](#próximos-pasos-plan-activo) | Completado en sesiones anteriores + sprint actual |

---


## REGLAS OBLIGATORIAS

Estas reglas son **permanentes y no negociables** — aplican en toda sesión de trabajo.

### R1 — Actualizar CONTEXTO.md y estado_proyecto_ciap.html al completar tareas
Cada vez que se complete una tarea significativa (script nuevo, endpoint, mejora a la IA, sprint terminado, cambio relevante), actualizar **antes de cerrar la sesión**:
1. `contexto/CONTEXTO.md` — estado de la DB, parámetros, endpoints, próximos pasos, gotchas nuevos
2. `contexto/estado_proyecto_ciap.html` — porcentajes por capa, mover ítems a completado, ajustar próximos 3 pasos

Si no se actualizan, la próxima sesión empieza con información falsa.

### R2 — Actualizar descripción del script al modificarlo
Cada vez que se modifique un script del pipeline (cualquier archivo en `scripts/`), actualizar su fila correspondiente en la sección **"Scripts del pipeline — descripción detallada"** de este archivo. La tabla debe reflejar siempre el estado real del script: entrada, salida, flags, gotchas y comportamiento actual.

### R3 — pgAdmin4 manda sobre schema.sql y CONTEXTO.md
Si hay discrepancia entre columnas documentadas aquí y lo que se ve en pgAdmin4, **pgAdmin4 manda**. Verificar siempre con:
```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'nombre_tabla' ORDER BY ordinal_position;
```
Luego actualizar este CONTEXTO.md con las columnas reales.

### R4 — Nunca leer archivos innecesarios
- `node_modules/` — nunca
- `data/*.csv` — solo con `limit: 3` para ver headers. Nunca leer completo.
- `__pycache__/` — nunca
- `data/progreso_*.json` y `data/log_*.txt` — solo si se está debuggeando un script específico

### R5 — Ejecutar scripts siempre desde la raíz del proyecto
```bash
# Correcto
python scripts/pipeline/ia_fiscalizadora.py

# Incorrecto
cd scripts/pipeline && python ia_fiscalizadora.py
```

---


## INSTRUCCIONES PARA CLAUDE — LEER ANTES DE EMPEZAR

### Cómo entender el proyecto eficientemente
1. **Leer este archivo completo primero.** Documenta la arquitectura, el estado real de la DB, los gotchas y los endpoints. Evita leer código para contestar preguntas que ya están respondidas aquí.
2. **Leer scripts solo cuando vayas a modificarlos.** Cada script está descrito en la sección "Archivos clave". No leas todos los scripts de entrada — es caro en tokens y redundante.
3. **El estado real de la DB está en la sección "Estado actual de la base de datos".** No asumas nada del `schema.sql` (difiere de la DB real).

### Carpetas y archivos que NUNCA debes leer
| Ruta | Por qué ignorar |
|------|-----------------|
| `node_modules/` | Dependencias npm — miles de archivos, nunca relevantes |
| `scripts/extractores/__pycache__/` | Bytecode compilado Python — irrelevante |
| `scripts/**/__pycache__/` | Idem para cualquier subcarpeta |
| `data/progreso_*.json` | Checkpoints de estado efímero de scripts en curso |
| `data/log_*.txt` | Logs de ejecución — leer solo si debuggeas un script específico |

### Lectura inteligente de CSVs
Los CSVs en `data/` son masivos — nunca los leas completos. Regla: **leer solo con `limit: 3`** (headers + 2 filas de muestra) cuando necesites verificar columnas o estructura.

**CSV más importante — leer con limit:3 si hay duda de columnas:**
- `data/MAESTRO_EXPANDIDO.csv` — 6.514 funcionarios. Fuente de verdad para nombres y link_declaracion. Sus RUTs son NaN — no usar para join por RUT.

**Otros CSVs con columnas frecuentemente consultadas:**
| CSV | Contenido | Columnas clave |
|-----|-----------|----------------|
| `data/csvacciones.csv` | 48.681 participaciones societarias CPLT | UriDeclaracion, UriDeclarante, EntidadAccion, RutJuridica, Giro |
| `data/csvdeclaraciones.csv` | 118.458 declaraciones CPLT (Kast parcial +4.652 vs anterior) | UriDeclaracion, UriDeclarante, Declaracion |
| `data/csvactividades.csv` | Actividades declaradas | verificar con limit:3 |
| `data/funcionarios_rescatados.csv` y variantes | RUTs rescatados por bots | verificar con limit:3 |
| `data/MAESTRO_RUTS_CONSOLIDADOS.csv` | 5.468 RUTs reales con link_declaracion | rut, link_declaracion, nombre |

**CRÍTICO — columnas en data/ vs pgAdmin4 pueden diferir:**
- El CSV puede tener columnas que la tabla PostgreSQL no tiene (o viceversa).
- Nunca asumir que las columnas del CSV coinciden con la tabla. Si vas a escribir un script que une ambos, **verificar columnas reales en pgAdmin4** con:
  ```sql
  SELECT column_name, data_type FROM information_schema.columns
  WHERE table_name = 'nombre_tabla' ORDER BY ordinal_position;
  ```
- Si hay discrepancia entre lo documentado en este CONTEXTO.md y lo que ves en pgAdmin4, **pgAdmin4 manda** — actualizar este archivo con las columnas reales.

---


## ¿Qué es este proyecto?

Ciudadano Informado es una plataforma de Civic Tech (tecnología cívica) para Chile,
inspirada en el sistema de Bruno César en Brasil. Su objetivo es consolidar información
pública de funcionarios y políticos chilenos para detectar conflictos de interés,
facilitar la fiscalización ciudadana y hacer accesible la información del Estado.

El proyecto nace del Manifiesto ECT (Estado Ciudadano Tecnológico) y el "Partido del Dato",
cuyo lema es: "Poder al Dato, Decisión al Ciudadano".

---


## Arquitectura — 4 Capas

### Capa 1 — Fuentes de datos públicas
Datos obtenidos de fuentes oficiales del Estado de Chile:

| Fuente | Datos | Método | Estado |
|--------|-------|--------|--------|
| Servel | Alcaldes, concejales, gobernadores electos 2024 | Excel descargado | Completo |
| InfoProbidad (CPLT) | Declaraciones de patrimonio, empresas declaradas | CSV bulk + scraping HTTP | Completo |
| Ley de Lobby (InfoLobby) | Reuniones entre funcionarios y privados | CSV descargado + importación | Completo |
| Congreso (Camara) | Votaciones, asistencia, diputados leg 50-58 | API REST opendata.congreso.cl | Completo: leg 50-58 cargada. 7.180 votaciones, 947K votos, 376K asistencia. VIDs leg 57/58 estaban en rango 80.000-85.000. |
| BCN Labor Parlamentaria | Proyectos de ley (mociones) de diputados | facetas-buscador-avanzado (Solr interno) + SPARQL bulk para mapa DIPID→BCN_ID | Completo sesión 12. 7.933 proyectos de ley, 251 diputados con mociones. Ver sección Scripts. |
| CMF | Directores en empresas fiscalizadas (SA abiertas, fondos, seguros) | Scraping portal CMF | Extractor listo (scripts/extractores/cmf.py). Proceso corriendo (~4.5h nocturno) |
| SII | Giro y razón social de empresas en participacion_societaria | CSV local csvacciones.csv (CAPTCHA zeus.sii.cl roto) | Completo: 2.782/2.782 empresas enriquecidas via CSV local |
| Mercado Público | Licitaciones adjudicadas a empresas de candidatos | OCDS bulk ZIP (sin ticket) + API OCDS fallback | En ingesta sesión 9. Bulk: ocds.blob.core.windows.net/ocds/yyyymm.zip (19 meses 2021-2023). API OCDS para meses sin bulk. |
| Gobierno Kast (ministros/subsecretarios) | Nómina designada | gob.cl | Sistema listo, CPLT sin publicar declaraciones aún (plazo vence ~abr 2026) |

### Capa 2 — Ingesta, normalización e IA

18 pasos orquestados por `pipeline_maestro.py`. Ver detalle completo en la sección [Scripts del pipeline](#scripts-del-pipeline--descripción-detallada).

- Base de datos: PostgreSQL 18 local (`ciudadano_db`)

### Capa 3 — API REST
- `src/server.js` — Servidor Node.js con Express, puerto 3000. Rate limiting: limiterGeneral 300 req/15min, limiterBusqueda 80 req/15min. Sirve el HTML en `GET /` vía `res.sendFile()`.
- `src/controllers/candidato.js` — Endpoints con datos reales de PostgreSQL
- `src/config/database.js` — Conexión a PostgreSQL via pg Pool (variables desde .env)
- Dependencias: express, pg, dotenv, cors, express-rate-limit

### Capa 4 — Interfaces ciudadanas
- `contexto/ciudadano_informado_plataforma.html` — Frontend conectado a API real en localhost:3000
- Buscador de candidatos con perfil completo
- Comparador entre candidatos
- Visualización de alertas de probidad generadas por la IA
- Historial de reuniones de lobby

---


## Archivos de seguimiento del proyecto

### estado_proyecto_ciap.html
**Archivo:** `contexto/estado_proyecto_ciap.html`

Panel visual de progreso del proyecto con barras de avance por capa (1 a 4) y lista de ítems completados / en progreso / pendientes. Es el "tablero" del proyecto — muestra de un vistazo qué está hecho y qué falta.

Debe actualizarse manualmente cada vez que se complete una tarea significativa. No se genera automáticamente. Ver **R1** en la sección de REGLAS OBLIGATORIAS.

---


## Variables de entorno requeridas (.env)

```
DB_HOST=localhost
DB_NAME=ciudadano_db
DB_USER=postgres
DB_PASSWORD=<contraseña>
DB_PORT=5432
PORT=3000
NODE_ENV=development
LOBBY_DIR=C:\Users\Public          # Carpeta con archivos CSV del lobby. Default: C:\Users\Public
PG_DUMP=C:\Program Files\PostgreSQL\18\bin\pg_dump.exe  # Ruta a pg_dump para --backup
```

**En Railway** estas mismas variables se configuran en el panel Settings → Variables. Railway inyecta automáticamente `DATABASE_URL` cuando se agrega el plugin PostgreSQL — pero el servidor usa variables individuales (`DB_HOST`, etc.), así que hay que agregarlas manualmente o parsear `DATABASE_URL` en `src/config/database.js`.

---

