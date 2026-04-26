---
tags: [api, contexto]
---

# Plan Definitivo — CIAP: Ciudadano Informado

## Contexto

Plataforma civic tech chilena que cruza datos de lobby (InfoLobby), participación societaria (CPLT/InfoProbidad) y datos electorales (Servel) para detectar conflictos de interés en funcionarios públicos.

**Estado actual verificado:**
- DB PostgreSQL 18 (`ciudadano_db`): 6.521 candidatos, 3.060 participaciones societarias, 503K matches lobby
- IA Fiscalizadora: 1 alerta producida (AUTOLOBBY, siempre gravedad ALTA)
- API Node.js: funcionando en puerto 3000 con 2 endpoints
- Frontend HTML: tabs Resumen/Empresas/Lobby/Alertas conectados a API; Partidos/Historial/Fisco hardcodeados

**Problema central:** El sistema detecta conflictos pero los clasifica todos como ALTA gravedad (sin matiz), no tiene score de transparencia visible, y la UI tiene secciones clave hardcodeadas.

---

## Sprint 1 — IA + Score (implementable hoy con datos existentes)

### 1. Mejorar clasificación de gravedad en `ia_fiscalizadora.py`

**Archivo:** `ia_fiscalizadora.py` (144 líneas)

La query ya distingue `RUT_EXACTO` vs `SIMILITUD_NOMBRE` en `match_tipo`, pero `gravedad` siempre es `'ALTA'`. Cambiar a:

```python
# Lógica de gravedad por match_tipo
if row['tipo_match'] == 'RUT_EXACTO':
    gravedad = 'ALTA'
elif row['tipo_match'] == 'SIMILITUD_NOMBRE':
    gravedad = 'MEDIA'
```

Además agregar un tercer patrón: candidato con participación societaria que **no** hizo lobby → insertar alerta con gravedad `'BAJA'` y tipo `'PARTICIPACION_SIN_LOBBY'`. Esto amplía el dataset de alertas significativamente.

**Cambios en `ia_fiscalizadora.py`:**
- Línea donde se hace `INSERT INTO alerta_probidad`: cambiar `gravedad = 'ALTA'` por lógica condicional
- Agregar segunda query para detectar participaciones societarias sin match lobby

### 2. Score de transparencia — nuevo campo en DB + API + UI

**Problema:** `score_transparencia` está en `schema.sql` pero **NO existe en la DB real** (`candidato` real no tiene esa columna).

**Pasos:**
1. Ejecutar en PostgreSQL:
   ```sql
   ALTER TABLE candidato ADD COLUMN IF NOT EXISTS score_transparencia INTEGER DEFAULT 0;
   ```
2. Calcular score con esta fórmula (0–100):
   - +25 si tiene RUT real (no empieza con `CPLT-` ni `SERVEL-`)
   - +25 si tiene `fuente_url` (declaración CPLT registrada)
   - +25 si tiene al menos 1 registro en `participacion_societaria`
   - +25 si tiene al menos 1 match en `match_candidato_lobby`
3. Crear script `calcular_scores.py` que actualice la columna en batch con un solo UPDATE por componente
4. Retornar `score_transparencia` en `GET /api/candidatos/:id` y `GET /api/candidatos` (listado)
5. Mostrar en frontend: badge de color en la card del candidato (verde ≥75, amarillo 50-74, rojo <50)

**Archivo a modificar:** `src/controllers/candidato.js` — añadir `score_transparencia` a los SELECT de ambas queries

---

## Sprint 2 — Tab Patrimonio + Partidos (datos ya disponibles)

### 3. Tab Patrimonio desde `csvdeclaraciones.csv`

**Datos disponibles:** `data/csvdeclaraciones.csv` (113.806 registros)

**Pasos:**
1. Crear tabla en PostgreSQL:
   ```sql
   CREATE TABLE IF NOT EXISTS declaracion_patrimonio (
     id SERIAL PRIMARY KEY,
     candidato_id INTEGER REFERENCES candidato(id),
     tipo_bien VARCHAR(100),    -- BienRaiz, Vehiculo, CuentaBancaria, etc.
     descripcion TEXT,
     valor DECIMAL(18,2),
     fecha_declaracion DATE
   );
   ```
2. Crear `importar_patrimonio.py` que lea el CSV, cruce con `candidato` por `uri_declarante` (que ya existe en tabla `candidato`), e inserte en la nueva tabla
3. Añadir endpoint `GET /api/candidatos/:id/patrimonio` en `candidato.js`
4. Añadir tab **Patrimonio** al HTML entre Empresas y Lobby

### 4. Poblar tabla `partido` y conectar en API/UI

**Partidos a cargar:** PS, RN, UDI, PPD, DC, FA, Chile Vamos, Apruebo Dignidad, Republicanos, PDG, etc.

**Pasos:**
1. Script `poblar_partidos.py` que inserte partidos con nombre, bloque político y color
2. Cruzar candidatos cargados con datos de Servel (que sí tienen partido) para actualizar `partido_id`
3. Añadir `partido` al SELECT de `candidato.js`
4. Reemplazar el hardcode de partidos en el frontend por `GET /api/partidos`

---

## Sprint 3 — Pipeline diario + Familiares (próximas 2 semanas)

### 5. Pipeline diario automático

Script `pipeline_diario.py` que ejecute en orden:
1. Descarga fresh data de fuentes (o verifica si hay actualizaciones)
2. Re-corre `ia_fiscalizadora.py`
3. Recalcula scores con `calcular_scores.py`

Configurar con Task Scheduler de Windows (o cron en Linux si se despliega en VPS).

### 6. Tabla `relacion_familiar` y detección de conflictos familiares

Nueva tabla:
```sql
CREATE TABLE relacion_familiar (
  id SERIAL PRIMARY KEY,
  candidato_a INTEGER REFERENCES candidato(id),
  candidato_b INTEGER REFERENCES candidato(id),
  tipo_parentesco VARCHAR(50)  -- 'hermano', 'conyuge', 'padre', etc.
);
```

Fuente de datos: requiere carga manual o scraping de prensa (El Mercurio, CIPER) — **requiere decisión sobre fuente**.

Nueva detección en IA: si empresa de familiar_A hizo lobby ante familiar_B → alerta tipo `FAMILIAR_CONFLICTO`.

---

## Sprint 4 — Deploy y expansión (cuando sea)

### 7. Mercado Público — licitaciones

Requiere ticket de acceso a API (`api.mercadopublico.cl`). Cuando se obtenga:
- Nueva tabla `licitacion`
- Cruce: empresa del candidato → ganó licitación mientras estaba en cargo
- Nuevo tipo de alerta: `LICITACION_CONFLICTO`

### 8. Deploy público

- PostgreSQL + Node.js → Railway (DB + API)
- HTML → cualquier hosting estático (Vercel, Netlify, GitHub Pages)
- Ajustar `const API` en el HTML para apuntar al dominio real

### 9. Chatbot (Claude API)

- Conectar Claude API a PostgreSQL via herramienta de texto-a-SQL
- "¿Quién tiene más reuniones de lobby con empresas mineras?" → SQL → respuesta

---

## Orden de ejecución recomendado

```
Hoy:
  1. ia_fiscalizadora.py → clasificar gravedad (ALTA/MEDIA/BAJA)
  2. ALTER TABLE + calcular_scores.py → score_transparencia
  3. candidato.js → retornar score en API
  4. ciudadano_informado_plataforma.html → mostrar score visual

Esta semana:
  5. importar_patrimonio.py + tabla + endpoint + tab UI
  6. poblar_partidos.py + conectar en API y UI

Próximas 2 semanas:
  7. pipeline_diario.py
  8. relacion_familiar (si se define fuente)

Cuando sea posible:
  9. Mercado Público (requiere ticket)
  10. Deploy
  11. Chatbot
```

---

## Archivos críticos a modificar por sprint

| Sprint | Archivo | Cambio |
|--------|---------|--------|
| 1 | `ia_fiscalizadora.py` | Lógica de gravedad + nuevo patrón BAJA |
| 1 | `calcular_scores.py` | Nuevo script — calcular score_transparencia |
| 1 | `src/controllers/candidato.js` | Retornar score en ambos endpoints |
| 1 | `contexto/ciudadano_informado_plataforma.html` | Badge de score en cards |
| 2 | `importar_patrimonio.py` | Nuevo script — CSV → tabla DB |
| 2 | `schema.sql` | Documentar tabla declaracion_patrimonio |
| 2 | `src/controllers/candidato.js` | Endpoint /patrimonio |
| 2 | `contexto/ciudadano_informado_plataforma.html` | Tab Patrimonio |
| 2 | `poblar_partidos.py` | Nuevo script — poblar tabla partido |

---

## Verificación por sprint

**Sprint 1:**
```bash
python ia_fiscalizadora.py  # Ver alertas con gravedades mezcladas (ALTA/MEDIA/BAJA)
python calcular_scores.py   # Ver UPDATE N candidatos
node src/server.js
curl http://localhost:3000/api/candidatos/6122  # debe incluir score_transparencia
# Abrir ciudadano_informado_plataforma.html → ver badge de score en candidatos
```

**Sprint 2:**
```bash
python importar_patrimonio.py  # Ver N filas insertadas
curl http://localhost:3000/api/candidatos/6122/patrimonio
# En UI: tab "Patrimonio" visible con datos reales
```
