---
tags: [enlazada]
---

# PostgreSQL — Hub de la Base de Datos CIAP

**Servidor:** PostgreSQL 18 local · Base: `ciudadano_db` · Puerto: 5432

Ver [[Mapa_Proyecto]] · [[arquitectura/Modelo_Datos]] · [[contexto/sub/Estado_DB]]

---

## Tablas nucleares

| Tabla | Registros | Fuente | Nota |
|-------|-----------|--------|------|
| [[db/Tabla_Candidato\|candidato]] | 6.801 | SERVEL + CPLT | Centro del grafo |
| [[db/Tabla_Lobby\|lobby (4 tablas)]] | 4.8M + 503K matches | InfoLobby | empresa_rut=NULL en reunion_lobby |
| [[db/Tabla_Empresas\|empresas (3 tablas)]] | 6.903 + 2.782 enriquecidas | CPLT + CMF | 100% SII enriquecidas |
| [[db/Tabla_Congreso\|congreso (5 tablas)]] | 335 diputados · 947K votos | Camara + BCN | Leg 50-58 completa |
| [[db/Tabla_Alertas\|alerta_probidad]] | ~598 | IA Fiscalizadora | 35 ALTA · 563 MEDIA/BAJA |
| declaracion_cplt | 118.760 | CPLT | Vinculada por uri_declarante |
| financiamiento_electoral | 15.739 | SERVEL | 2.402 vinculados a candidato |
| donante_electoral | 338.911 | SERVEL | 12.255 donantes unicos |
| licitacion | en ingesta | OCDS | hasta 2022-04 completado |
| orden_compra | 138.339 | Mercado Publico | 2022-2026 |

## Tablas de catalogo

`partido`, `cargo`, `institucion` — valores de referencia.

## Anomalias criticas

1. `reunion_lobby.empresa_rut = NULL` en las 4.8M filas — nunca cruzar directamente
2. `institucion_id` aparece en `schema.sql` pero **NO existe en la DB real**
3. `score_transparencia` no estaba en el schema original — lo agrega `calcular_scores.py` con `ALTER TABLE`

## Conexion

```bash
psql -h localhost -U postgres -d ciudadano_db
# o via pgAdmin4 (pgAdmin4 manda sobre schema.sql)
```
