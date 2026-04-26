---
tags: [contexto, enlazada]
---

## La IA Fiscalizadora — Lógica real de cruce

### El problema con `reunion_lobby`
`reunion_lobby.empresa_rut` es NULL en las 4.8M filas. La columna `empresa_nombre` contiene
la **institución del funcionario** (ej: "PRESIDENCIA DE LA REPÚBLICA"), NO la empresa privada
que hizo lobby. Esta tabla NO sirve para detectar conflictos de interés por nombre.

### Cadena correcta de JOIN (via temp_representaciones)
```
candidato
  → match_candidato_lobby (ON candidato.rut = m.rut)
  → temp_asistencia_pasivo (ON tap.codigopasivo = m.codigo_pasivo)
  → temp_representaciones (ON tr.codigo_audiencia = tap.codigoaudiencia)  ← entidad privada
  → temp_audiencia (ON ta.codigouri = tap.codigoaudiencia)                ← fecha y URL del acta
```

### Parámetros actuales de ia_fiscalizadora.py
- `SIMILITUD_MIN = 0.75` (pg_trgm `similarity()`, requiere extensión `pg_trgm`)
- `LONGITUD_MIN_NOMBRE = 6` (filtro para evitar matches triviales en AUTOLOBBY)
- `APELLIDO_MIN_LEN = 6` (apellidos más cortos ignorados en CONFLICTO_FAMILIAR)
- `MAX_CANDIDATOS_POR_APELLIDO = 10` (apellido aparece en >10 candidatos → demasiado común, ignorado)
- `APELLIDOS_COMUNES` — set con 100+ apellidos frecuentes en Chile (GONZALEZ, RODRIGUEZ, etc.) excluidos de CONFLICTO_FAMILIAR
- `NOMBRES_PILA` — set con nombres de pila frecuentes para no confundirlos con apellidos
- Columna `match_tipo` en `alerta_probidad`: `RUT_EXACTO`, `SIMILITUD_NOMBRE`, o `APELLIDO_COMPARTIDO`
- Formato de `codigo_representado`: `693007009r` → RTRIM de 'r' = RUT empresa
- Patrón RUT_EXACTO: `RTRIM(tr.codigo_representado, 'r') = ps.empresa_rut`
- Gravedad CONFLICTO_FAMILIAR: MEDIA si lobbista es persona natural, BAJA si es empresa/entidad

### Alerta conocida (producción)
- Candidato: LUIS FERNANDO SANCHEZ OSSA (id=6122, DIPUTADO, Viña del Mar)
- Empresa: SOCIEDAD QUÍMICA Y MINERA DE CHILE S.A. (RUT: 93007000)
- Tipo: AUTOLOBBY_DETECTADO, Gravedad: ALTA, Match: SIMILITUD_NOMBRE
- Fecha lobby: 2016-10-25
- URL acta: http://datos.infolobby.cl/infolobby/registroaudiencia/mu2431131631

### Nota sobre `__main__` del script
El bloque `if __name__ == "__main__"` invoca los 3 detectores en secuencia, cada uno en instancia separada (conexión fresca):
1. `detectar_conflictos_lobby()` — AUTOLOBBY_DETECTADO
2. `detectar_conflictos_familiares()` — CONFLICTO_FAMILIAR_POSIBLE
3. `detectar_donante_proveedor()` — DONANTE_PROVEEDOR

El pipeline maestro corre el script como subproceso, por lo que los 3 se ejecutan al correr el paso `ia`.

---

---
*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*
