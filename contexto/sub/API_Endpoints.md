---
tags: [api, contexto, enlazada]
---

## API Node.js — Endpoints activos

**Servidor:** `node src/server.js` → http://localhost:3000 (también sirve el HTML en `/`)

**IMPORTANTE:** Siempre abrir la plataforma en `http://localhost:3000/` — NO abrir el archivo HTML directamente desde el explorador (file://) porque `window.location.hostname` no detecta localhost y apunta a la URL de producción inexistente.

### GET /api/candidatos?q=texto&cargo=DIPUTADO&page=1&limit=20
Búsqueda por nombre o RUT. Usa `nombre_limpio ILIKE` y `nombres ILIKE`. Filtro opcional `?cargo=` (nombre exacto del cargo, case-insensitive). Respuesta incluye `meta.filtro_cargo`.

Respuesta:
```json
{
  "meta": {"total": 5468, "page": 1, "limit": 20, "totalPages": 274},
  "data": [
    {"id": 6122, "rut": "169646112", "nombres": "LUIS FERNANDO SANCHEZ OSSA",
     "nombre_limpio": "LUIS FERNANDO SANCHEZ OSSA", "comuna": "VIÑA DEL MAR",
     "cargo": "DIPUTADO", "score_transparencia": 40}
  ]
}
```

### GET /api/candidatos/:id
Perfil completo. Respuesta:
```json
{
  "id": 6122, "rut": "169646112", "nombres": "LUIS FERNANDO SANCHEZ OSSA",
  "nombre_limpio": "LUIS FERNANDO SANCHEZ OSSA", "comuna": "VIÑA DEL MAR",
  "cargo": "DIPUTADO", "fuente_url": "http://datos.cplt.cl/datos/infoprobidad/91a4...",
  "score_transparencia": 40,
  "empresas": [{"empresa_rut": "93007000", "empresa_nombre": "SOCIEDAD QUIMICA...", "porcentaje_propiedad": 0}],
  "lobby": [{"fecha": "2016-10-25", "institucion_lobby": "...", "empresa_lobbied": "...", "giro": "...", "url": "..."}],
  "alertas": [{"tipo": "AUTOLOBBY_DETECTADO", "gravedad": "ALTA", "match_tipo": "SIMILITUD_NOMBRE", "detalle": "...", "fecha_deteccion": "...", "fuente_url": "..."}]
}
```

### GET /api/candidatos/:id/licitaciones?page=1&limit=50
Licitaciones adjudicadas a empresas del candidato. Fuente: tabla `licitacion`.
```json
{
  "candidato_id": 6122,
  "resumen": {
    "total_licitaciones": 5,
    "monto_total_pesos": 12354000,
    "organismos_distintos": 3,
    "primera": "2021-03-10",
    "ultima": "2023-05-22"
  },
  "meta": {"page": 1, "limit": 50, "totalPages": 1},
  "data": [
    {"codigo": "1080220-12-L123", "estado": "adjudicada", "fecha_adjudicacion": "2023-05-22",
     "monto_adjudicado": 930000, "nombre_organismo": "...", "nombre_adjudicatario": "...",
     "link": "https://www.mercadopublico.cl/..."}
  ]
}
```

### GET /api/candidatos/:id/financiamiento
Financiamiento electoral SERVEL 2024 del candidato. Devuelve `resumen` (ingresos, gastos, partido, territorio), `donantes` (top 20 aportantes con RUT y monto), `gastos` (top 10 por concepto), `alertas_donante` (DONANTE_PROVEEDOR si existen).

### GET /api/candidatos/:id/ordenes?page=1&limit=50
Órdenes de compra del estado donde empresa del candidato es proveedora. Fuente: tabla `orden_compra` (138K filas). Respuesta incluye `resumen` (total OCs, monto total, organismos distintos, rango fechas) y `data` paginada.

### GET /api/stats
Estadísticas globales del proyecto. Devuelve candidatos (total, con RUT, con CPLT), scores (promedio, verde/amarillo/rojo), alertas por tipo/gravedad, empresas, mercado público (OCs + monto), lobby (matches), distribución por cargo.

### GET /api/candidatos/:id/congreso
Votaciones y asistencia del diputado. Si no es diputado devuelve `es_diputado: false`.
```json
{
  "candidato_id": 6705,
  "es_diputado": true,
  "dipid": 1185,
  "asistencia": [
    {"legislatura_id": 57, "presencias": 39, "inasistencias": 85, "total_sesiones": 124, "pct_asistencia": "31.5"}
  ],
  "votaciones": [
    {"id": 84616, "boletin": "17461-15", "fecha": "2025-09-10T...", "tipo": "General", "resultado": "Aprobado", "opcion": "Afirmativo", "legislatura_id": 57}
  ]
}
```

### GET /api/candidatos/:id/proyectos?page=1&limit=100
Proyectos de ley (mociones) presentados por el diputado. Si no es diputado o no tiene mociones en BCN devuelve `sin_datos: true`.
```json
{
  "candidato_id": 6122,
  "meta": {"total": 174, "page": 1, "limit": 100, "totalPages": 2},
  "data": [
    {"boletin": "18063-07", "titulo": "Modifica la Carta Fundamental...", "fecha_ingreso": "2026-01-20",
     "tipo_iniciativa": "Mocion", "camara_origen": "Cámara de Diputados",
     "legislatura": "373", "link": "https://www.bcn.cl/laborparlamentaria/index_html?prmBusqueda=18063-07"}
  ]
}
```

### GET /api/alertados
Top 300 candidatos con alertas IA, ordenados por gravedad y score. No requiere params.
```json
{"total": 87, "data": [{"id": 123, "nombres": "...", "cargo": "ALCALDE", "score_transparencia": 12, "alertas": [{"tipo": "AUTOLOBBY_DETECTADO", "gravedad": "ALTA", "detalle": "..."}]}]}
```

### GET /api/candidatos/:id/patrimonio
Historial de declaraciones CPLT del candidato. Fuente: tabla `declaracion_cplt` vinculada por `uri_declarante`.
```json
{
  "candidato_id": 6122,
  "nombres": "LUIS FERNANDO SANCHEZ OSSA",
  "declaraciones": [
    {
      "uri_declaracion": "http://datos.cplt.cl/datos/infoprobidad/declaracion_...",
      "tipo": "ACTUALIZACIÓN PERIÓDICA (MARZO)",
      "institucion": "CAMARA DE DIPUTADAS Y DIPUTADOS",
      "cargo": "DIPUTADO",
      "regimen_pat": "SEPARACION TOTAL DE BIENES",
      "fecha_asuncion": "2022-03-11",
      "fecha_declaracion": "2025-03-24"
    }
  ]
}
```

---

---
*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*
