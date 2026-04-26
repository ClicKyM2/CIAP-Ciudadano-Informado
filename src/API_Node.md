---
tags: [api, codigo, enlazada]
---

# API Node.js — Estructura

Ver [[Mapa_Proyecto]] · [[contexto/sub/API_Endpoints]] · [[arquitectura/Stack_Tecnologico]]

---

## Archivos

```
src/
├── server.js          ← Entry point: Express + rutas + static files
├── config/
│   └── db.js          ← Pool de conexión pg a ciudadano_db
├── controllers/
│   └── candidato.js   ← Lógica SQL para cada endpoint
└── routes/
    └── candidatos.js  ← Definición de rutas Express
```

---

## server.js

- Puerto: `process.env.PORT || 3000`
- Sirve HTML estático desde `contexto/ciudadano_informado_plataforma.html` en `GET /`
- Monta rutas en `/api/candidatos`, `/api/stats`, `/api/alertados`
- Sin autenticación (API pública de lectura)

## config/db.js

- `pg.Pool` con conexión a `ciudadano_db` en localhost
- Variables: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` desde `.env`

## controllers/candidato.js

Funciones exportadas:
- `getCandidatos` — búsqueda paginada con ILIKE
- `getCandidatoById` — perfil completo con empresas, lobby, alertas
- `getLicitaciones` — licitaciones adjudicadas a empresas del candidato
- `getFinanciamiento` — financiamiento SERVEL + donantes + alertas DONANTE_PROVEEDOR
- `getOrdenes` — órdenes de compra
- `getStats` — estadísticas globales
- `getCongreso` — votaciones y asistencia (solo diputados)
- `getProyectos` — mociones BCN (solo diputados)
- `getAlertados` — top 300 candidatos con alertas IA
- `getPatrimonio` — historial declaraciones CPLT

## routes/candidatos.js

```
GET /api/candidatos              → getCandidatos
GET /api/candidatos/:id          → getCandidatoById
GET /api/candidatos/:id/licitaciones  → getLicitaciones
GET /api/candidatos/:id/financiamiento → getFinanciamiento
GET /api/candidatos/:id/ordenes  → getOrdenes
GET /api/candidatos/:id/congreso → getCongreso
GET /api/candidatos/:id/proyectos → getProyectos
GET /api/candidatos/:id/patrimonio → getPatrimonio
GET /api/stats                   → getStats
GET /api/alertados               → getAlertados
```

Ver documentación completa de respuestas JSON en [[contexto/sub/API_Endpoints]].

---

*Nota de arquitectura · [[Mapa_Proyecto]] · [[contexto/sub/API_Endpoints]]*
