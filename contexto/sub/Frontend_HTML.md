---
tags: [api, contexto, enlazada]
---

## Frontend HTML (ciudadano_informado_plataforma.html)

**Archivo:** `contexto/ciudadano_informado_plataforma.html`

Conectado a la API real. No tiene datos hardcodeados.

- Constante `const API = 'http://localhost:3000'` al inicio del script
- Carga inicial: `GET /api/candidatos?limit=50` al abrir la página
- Búsqueda: `filterCandidates(q)` → fetch async con debounce implícito
- Perfil: `selectCandidate(id)` → fetch async `GET /api/candidatos/:id`
- Función `displayName(c)`: usa `c.nombre_limpio || c.nombres` (apellidos vacío)
- Función `getInitials(c)`: toma primeras letras de las primeras dos palabras de nombre_limpio
- Colores de avatar: asignados por `cargo` (no partido, que siempre es NULL)

**Tabs del perfil:**
1. **Resumen** — RUT, cargo, comuna, score_transparencia con barra de progreso y badge coloreado, link a declaración original
2. **Empresas** — lee `c.empresas[]`: empresa_nombre, empresa_rut, porcentaje_propiedad
3. **Lobby** — lee `c.lobby[]`: fecha, empresa_lobbied, giro, institucion_lobby, url
4. **Alertas IA** — lee `c.alertas[]`: tipo, gravedad, match_tipo, detalle, fecha, fuente_url
5. **Declaraciones** — carga lazy via `GET /api/candidatos/:id/patrimonio`. Muestra: tipo (coloreado por ingreso/egreso/actualización), institución, cargo, régimen patrimonial, fechas, link a declaración original CPLT
6. **Congreso** — carga lazy via `GET /api/candidatos/:id/congreso`. Asistencia por legislatura + últimas 100 votaciones.
7. **Mercado** — carga lazy via `GET /api/candidatos/:id/ordenes`. Resumen (total OCs, monto total, organismos distintos, rango fechas) + listado de OCs.
8. **Licitaciones** — carga lazy via `GET /api/candidatos/:id/licitaciones`. Resumen (total licitaciones, monto adjudicado, organismos, período) + listado con link a Mercado Público.
9. **Campaña** — carga lazy via `GET /api/candidatos/:id/financiamiento`. Ingresos/gastos SERVEL 2024, top 10 aportantes con RUT, gastos por concepto, alertas DONANTE_PROVEEDOR si existen.
10. **Proyectos** — carga lazy via `GET /api/candidatos/:id/proyectos`. Lista de mociones con boletín, título, fecha, legislatura, link a BCN. Solo visible si es diputado con datos en BCN.

**Vistas de la barra de navegación:**
- Candidatos, Partidos, Historial Legislativo, Comparar, Fisco & Presupuesto, **Estadísticas**
- Vista Estadísticas: fetcha `GET /api/stats` y renderiza contadores de candidatos, distribución de scores, alertas por tipo, datos vinculados (OCs, lobby, empresas), distribución por cargo.

**Filtros en el panel izquierdo de candidatos:**
- Select de cargo: poblado dinámicamente desde `GET /api/stats` al cargar la página. Filtra server-side via `?cargo=`.
- Select de score tier: Verde/Amarillo/Rojo. Filtrado client-side sobre los candidatos ya cargados.

**Optimizaciones del frontend (sesión 12):**
- Debounce 350ms en el buscador (`debouncedSearch`) — no envía request en cada tecla
- Filtro de score tier aplicado client-side sin nueva consulta al servidor
- Cache de perfiles: `profileCache[id]` evita re-fetch al volver a un candidato ya visto

**Helpers de score en el frontend:**
- `scoreColor(v)` → verde #1A6B3C (≥75), amarillo #BA7517 (50-74), rojo #A32D2D (<50)
- `scoreBg(v)` → fondo suave según color
- `scoreLabel(v)` → "Transparente" / "Moderado" / "Bajo"
- `scoreBadge(v, size)` → pill coloreada con valor y etiqueta. size='sm' en cards, 'lg' en perfil

---

---
*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*
