---
tags: [enlazada]
---

# Modelo de Datos — Tablas Núcleo

Ver [[Mapa_Proyecto]] · [[db/PostgreSQL]] · [[arquitectura/Stack_Tecnologico]]

---

## Diagrama de relaciones (tablas críticas)

```
candidato (6.685 filas)
│  id, rut, nombres, cargo, comuna, uri_declarante, score_transparencia
│
├──→ declaracion_cplt (118.760 filas)
│       uri_declarante FK → candidato.uri_declarante
│
├──→ participacion_societaria (N filas)
│       candidato_id FK → candidato.id
│       empresa_rut → empresa_enriquecida.rut
│
│       empresa_enriquecida → directorio_cmf
│
├──→ match_candidato_lobby (N filas)
│       candidato_id FK → candidato.id
│       ← reunion_lobby (4.8M filas) via pg_trgm
│           ⚠️ empresa_rut = NULL en TODAS las filas de reunion_lobby
│           JOIN correcto: reunion_lobby ← temp_audiencia ← temp_representaciones
│
├──→ orden_compra (138.339 filas)
│       RutSucursal ∈ participacion_societaria.empresa_rut
│
├──→ financiamiento_electoral (15.739 filas)
│       candidato_id FK → candidato.id
│       → donante_electoral (338.911 filas)
│
├──→ alerta_probidad (N filas)
│       candidato_id FK → candidato.id
│       tipos: AUTOLOBBY_DETECTADO, CONFLICTO_FAMILIAR_POSIBLE, DONANTE_PROVEEDOR
│
└──→ diputado_camara (335 filas)
        candidato_id FK → candidato.id
        dipid → sesion_camara / votacion_camara / proyecto_ley
```

---

## Anomalías críticas conocidas

| Tabla | Anomalía | Workaround |
|-------|----------|------------|
| `candidato.apellidos` | Siempre vacío | Usar `nombres` (contiene apellidos también) |
| `candidato.partido_id` | NULL en todos | No usar este campo |
| `reunion_lobby.empresa_rut` | NULL en 4.8M filas | JOIN via temp_audiencia → temp_representaciones |
| `candidato.score_transparencia` | No estaba en schema original | Agregado con ALTER TABLE |
| `diputado_camara.institucion_id` | NULL en muchos | No usar como FK |

---

## Tablas de soporte (no en el diagrama principal)

- `licitacion` — adjudicaciones OCDS
- `temp_representaciones` (1.5M filas) — datos lobby bruto
- `temp_audiencia`, `temp_asistencia_pasivo` — limpieza lobby
- `sesion_camara`, `votacion_camara`, `voto_diputado`, `asistencia_sesion`
- `proyecto_ley`, `autoria_proyecto`

---

*Nota de arquitectura · [[db/PostgreSQL]] · [[db/Tabla_Candidato]] · [[db/Tabla_Lobby]]*
