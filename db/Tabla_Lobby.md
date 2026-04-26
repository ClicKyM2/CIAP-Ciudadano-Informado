---
tags: [enlazada, pipeline]
---

# Tablas: Lobby

Ver [[db/PostgreSQL]] · [[fuentes/Lobby]] · [[contexto/sub/IA_Fiscalizadora]] · [[Mapa_Proyecto]]

---

## Estructura

```
temp_audiencia (894.157) ←── codigouri
temp_asistencia_pasivo (894.251) ←── codigoaudiencia
temp_representaciones (1.548.503) ←── codigo_audiencia   ← ENTIDAD PRIVADA
match_candidato_lobby (503.007) ←── rut + codigo_pasivo
reunion_lobby (4.805.778) ← NO USAR para cruce (empresa_rut=NULL)
```

## ALERTA CRITICA

`reunion_lobby.empresa_rut` = **NULL en las 4.8M filas**.
`reunion_lobby.empresa_nombre` contiene la **institucion del funcionario**, NO la empresa privada.

**Nunca cruzar conflictos via `reunion_lobby` directamente.**

## JOIN correcto para detectar conflictos

```sql
candidato
  → match_candidato_lobby      (ON candidato.rut = m.rut)
  → temp_asistencia_pasivo     (ON tap.codigopasivo = m.codigo_pasivo)
  → temp_representaciones      (ON tr.codigo_audiencia = tap.codigoaudiencia)
  → temp_audiencia             (ON ta.codigouri = tap.codigoaudiencia)
```

## Formato de codigo_representado

`693007009r` → RTRIM('r') = RUT de la empresa privada

## Script responsable

`scripts/pipeline/importar_lobby.py` — carga temp_audiencia, temp_asistencia_pasivo, match_candidato_lobby.
Match via `pg_trgm` umbral 0.25 (la IA refina a 0.75).
