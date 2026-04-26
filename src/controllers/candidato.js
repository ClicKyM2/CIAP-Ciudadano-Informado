const db = require('../config/database');

// GET /api/candidatos?q=nombre&cargo=DIPUTADO&page=1&limit=20
const searchCandidatos = async (req, res) => {
    const { q = '', cargo = '', page = 1, limit = 20 } = req.query;
    const parsedPage  = parseInt(page, 10);
    const parsedLimit = parseInt(limit, 10);
    const offset = (parsedPage - 1) * parsedLimit;
    const param = `%${q}%`;
    const cargoFiltro = cargo.trim().toUpperCase();

    try {
        const whereExtra = cargoFiltro ? `AND UPPER(car.nombre) = $4` : '';
        const params = cargoFiltro
            ? [param, parsedLimit, offset, cargoFiltro]
            : [param, parsedLimit, offset];

        const countParams = cargoFiltro ? [param, cargoFiltro] : [param];
        const countWhere  = cargoFiltro ? `AND UPPER(car.nombre) = $2` : '';

        const countRes = await db.query(
            `SELECT COUNT(*)
             FROM candidato c
             LEFT JOIN cargo car ON c.cargo_id = car.id
             WHERE (c.nombres ILIKE $1 OR c.nombre_limpio ILIKE $1 OR c.rut ILIKE $1)
             ${countWhere}`,
            countParams
        );
        const total = parseInt(countRes.rows[0].count, 10);

        const { rows } = await db.query(
            `SELECT c.id, c.rut, c.nombres, c.nombre_limpio, c.comuna,
                    c.score_transparencia,
                    car.nombre AS cargo
             FROM candidato c
             LEFT JOIN cargo car ON c.cargo_id = car.id
             WHERE (c.nombres ILIKE $1 OR c.nombre_limpio ILIKE $1 OR c.rut ILIKE $1)
             ${whereExtra}
             ORDER BY c.nombres ASC
             LIMIT $2 OFFSET $3`,
            params
        );

        res.json({
            meta: {
                total,
                page:         parsedPage,
                limit:        parsedLimit,
                totalPages:   Math.ceil(total / parsedLimit),
                filtro_cargo: cargoFiltro || null
            },
            data: rows
        });
    } catch (err) {
        console.error('Error en búsqueda de candidatos:', err);
        res.status(500).json({ error: 'Error interno del servidor.' });
    }
};

// GET /api/candidatos/:id — perfil completo
const getCandidatoProfile = async (req, res) => {
    const { id } = req.params;
    const numId = parseInt(id, 10);
    if (isNaN(numId)) return res.status(400).json({ error: 'ID inválido.' });

    try {
        // apellidos siempre vacío — nombres contiene nombre completo; partido_id siempre NULL
        const { rows: basicos } = await db.query(
            `SELECT c.id, c.rut, c.nombres, c.nombre_limpio, c.comuna, c.fuente_url,
                    c.score_transparencia,
                    car.nombre AS cargo
             FROM candidato c
             LEFT JOIN cargo car ON c.cargo_id = car.id
             WHERE c.id = $1`,
            [numId]
        );
        if (basicos.length === 0) {
            return res.status(404).json({ error: 'Candidato no encontrado.' });
        }
        const perfil = basicos[0];

        // Cadena lobby: match_candidato_lobby -> temp_asistencia_pasivo -> temp_audiencia
        //               + temp_representaciones (entidad privada que hizo lobby)
        const [{ rows: empresas }, { rows: lobby }, { rows: alertas }] = await Promise.all([
            db.query(
                `SELECT empresa_rut, empresa_nombre, porcentaje_propiedad
                 FROM participacion_societaria
                 WHERE candidato_id = $1
                 ORDER BY empresa_nombre ASC`,
                [numId]
            ),
            db.query(
                `SELECT DISTINCT
                    ta.fechaevento  AS fecha,
                    ta.organismo    AS institucion_lobby,
                    tr.representado AS empresa_lobbied,
                    tr.giro,
                    ta.uriaudiencia AS url
                 FROM match_candidato_lobby m
                 JOIN candidato c             ON c.rut = m.rut AND c.id = $1
                 JOIN temp_asistencia_pasivo tap ON tap.codigopasivo = m.codigo_pasivo
                 JOIN temp_audiencia ta        ON ta.codigouri = tap.codigoaudiencia
                 LEFT JOIN temp_representaciones tr ON tr.codigo_audiencia = tap.codigoaudiencia
                 ORDER BY ta.fechaevento DESC
                 LIMIT 10`,
                [numId]
            ),
            db.query(
                `SELECT tipo, gravedad, match_tipo, detalle, fecha_deteccion, fuente_url
                 FROM alerta_probidad
                 WHERE candidato_id = $1
                 ORDER BY fecha_deteccion DESC`,
                [numId]
            ),
        ]);
        perfil.empresas = empresas;
        perfil.lobby    = lobby;
        perfil.alertas  = alertas;

        res.json(perfil);
    } catch (err) {
        console.error('Error obteniendo perfil:', err);
        res.status(500).json({ error: 'Error interno del servidor.' });
    }
};

// GET /api/candidatos/:id/patrimonio — historial de declaraciones CPLT
const getPatrimonio = async (req, res) => {
    const { id } = req.params;
    const numId = parseInt(id, 10);
    if (isNaN(numId)) return res.status(400).json({ error: 'ID inválido.' });

    try {
        const { rows: cand } = await db.query(
            `SELECT id, nombres, uri_declarante FROM candidato WHERE id = $1`,
            [numId]
        );
        if (cand.length === 0) return res.status(404).json({ error: 'Candidato no encontrado.' });

        const { nombres, uri_declarante } = cand[0];

        if (!uri_declarante) {
            return res.json({ candidato_id: numId, nombres, declaraciones: [] });
        }

        const { rows: declaraciones } = await db.query(
            `SELECT uri_declaracion, tipo, institucion, cargo, regimen_pat,
                    fecha_asuncion, fecha_declaracion
             FROM declaracion_cplt
             WHERE uri_declarante = $1
             ORDER BY fecha_declaracion DESC NULLS LAST`,
            [uri_declarante]
        );

        res.json({ candidato_id: numId, nombres, declaraciones });
    } catch (err) {
        console.error('Error obteniendo patrimonio:', err);
        res.status(500).json({ error: 'Error interno del servidor.' });
    }
};

// GET /api/candidatos/:id/congreso — votaciones y asistencia (solo diputados)
const getCongreso = async (req, res) => {
    const { id } = req.params;
    const numId = parseInt(id, 10);
    if (isNaN(numId)) return res.status(400).json({ error: 'ID inválido.' });

    try {
        const { rows: dipRows } = await db.query(
            `SELECT dipid FROM diputado_camara WHERE candidato_id = $1 LIMIT 1`,
            [numId]
        );

        if (dipRows.length === 0) {
            return res.json({ candidato_id: numId, es_diputado: false, asistencia: [], votaciones: [] });
        }

        const dipid = dipRows[0].dipid;

        // Asistencia por legislatura — solo legislaturas con al menos una presencia
        const { rows: asistencia } = await db.query(
            `SELECT sc.legislatura_id,
                    COUNT(*) FILTER (WHERE a.presente = true)  AS presencias,
                    COUNT(*) FILTER (WHERE a.presente = false) AS inasistencias,
                    COUNT(*) AS total_sesiones,
                    ROUND(
                        COUNT(*) FILTER (WHERE a.presente = true)::numeric
                        / NULLIF(COUNT(*), 0) * 100, 1
                    ) AS pct_asistencia
             FROM asistencia_sesion a
             JOIN sesion_camara sc ON sc.id = a.sesion_id
             WHERE a.dipid = $1
             GROUP BY sc.legislatura_id
             HAVING COUNT(*) FILTER (WHERE a.presente = true) > 0
             ORDER BY sc.legislatura_id`,
            [dipid]
        );

        const { rows: votaciones } = await db.query(
            `SELECT v.id, v.boletin, v.fecha, v.tipo, v.resultado, vd.opcion,
                    sc.legislatura_id
             FROM voto_diputado vd
             JOIN votacion_camara v ON v.id = vd.votacion_id
             JOIN sesion_camara sc ON sc.id = v.sesion_id
             WHERE vd.dipid = $1
             ORDER BY v.fecha DESC
             LIMIT 100`,
            [dipid]
        );

        res.json({ candidato_id: numId, es_diputado: true, dipid, asistencia, votaciones });
    } catch (err) {
        console.error('Error obteniendo datos del Congreso:', err);
        res.status(500).json({ error: 'Error interno del servidor.' });
    }
};

// GET /api/candidatos/:id/ordenes?page=1&limit=50
// Órdenes de compra del estado donde empresa del candidato es proveedora
const getOrdenes = async (req, res) => {
    const { id } = req.params;
    const { page = 1, limit = 50 } = req.query;
    const numId  = parseInt(id, 10);
    const lim    = Math.min(parseInt(limit, 10), 200);
    const offset = (parseInt(page, 10) - 1) * lim;

    if (isNaN(numId)) return res.status(400).json({ error: 'ID inválido.' });

    try {
        const { rows: resumen } = await db.query(
            `SELECT
                COUNT(*)                          AS total_ocs,
                COALESCE(SUM(monto_pesos), 0)     AS monto_total,
                COUNT(DISTINCT nombre_organismo)  AS organismos_distintos,
                MIN(fecha_creacion)               AS primera_oc,
                MAX(fecha_creacion)               AS ultima_oc
             FROM orden_compra
             WHERE candidato_id = $1`,
            [numId]
        );

        const { rows: ocs } = await db.query(
            `SELECT codigo, nombre, estado, fecha_creacion, monto_pesos,
                    nombre_organismo, rut_organismo, nombre_proveedor, codigo_licitacion
             FROM orden_compra
             WHERE candidato_id = $1
             ORDER BY fecha_creacion DESC NULLS LAST
             LIMIT $2 OFFSET $3`,
            [numId, lim, offset]
        );

        const total = parseInt(resumen[0].total_ocs, 10);

        res.json({
            candidato_id: numId,
            resumen: {
                total_ocs:            total,
                monto_total_pesos:    parseInt(resumen[0].monto_total, 10),
                organismos_distintos: parseInt(resumen[0].organismos_distintos, 10),
                primera_oc:           resumen[0].primera_oc,
                ultima_oc:            resumen[0].ultima_oc
            },
            meta: {
                page:       parseInt(page, 10),
                limit:      lim,
                totalPages: Math.ceil(total / lim)
            },
            data: ocs
        });
    } catch (err) {
        console.error('Error obteniendo órdenes de compra:', err);
        res.status(500).json({ error: 'Error interno del servidor.' });
    }
};

// GET /api/stats — estadísticas globales del proyecto
const getStats = async (req, res) => {
    try {
        const [
            candidatos,
            scores,
            alertas,
            empresas,
            ocs,
            lobby,
            cargos
        ] = await Promise.all([
            db.query(`
                SELECT
                    COUNT(*)                                                         AS total,
                    COUNT(*) FILTER (WHERE rut NOT LIKE 'CPLT-%'
                                       AND rut NOT LIKE 'SERVEL-%'
                                       AND rut NOT LIKE 'DIPCAM-%')                 AS con_rut_real,
                    COUNT(*) FILTER (WHERE uri_declarante IS NOT NULL)               AS con_declaracion_cplt
                FROM candidato
            `),
            db.query(`
                SELECT
                    ROUND(AVG(score_transparencia), 1)                               AS promedio,
                    COUNT(*) FILTER (WHERE score_transparencia >= 75)                AS verde,
                    COUNT(*) FILTER (WHERE score_transparencia >= 50
                                       AND score_transparencia < 75)                 AS amarillo,
                    COUNT(*) FILTER (WHERE score_transparencia < 50)                 AS rojo
                FROM candidato
                WHERE score_transparencia IS NOT NULL
            `),
            db.query(`
                SELECT tipo, gravedad, COUNT(*) AS total
                FROM alerta_probidad
                GROUP BY tipo, gravedad
                ORDER BY total DESC
            `),
            db.query(`
                SELECT
                    COUNT(DISTINCT empresa_rut)   AS empresas_unicas,
                    COUNT(*)                      AS participaciones
                FROM participacion_societaria
            `),
            db.query(`
                SELECT
                    COUNT(*)                    AS total_ocs,
                    COALESCE(SUM(monto_pesos), 0) AS monto_total
                FROM orden_compra
            `),
            db.query(`SELECT COUNT(*) AS total FROM match_candidato_lobby`),
            db.query(`
                SELECT car.nombre AS cargo, COUNT(*) AS total
                FROM candidato c
                JOIN cargo car ON car.id = c.cargo_id
                GROUP BY car.nombre
                ORDER BY total DESC
            `)
        ]);

        res.json({
            candidatos: {
                total:               parseInt(candidatos.rows[0].total, 10),
                con_rut_real:        parseInt(candidatos.rows[0].con_rut_real, 10),
                con_declaracion_cplt: parseInt(candidatos.rows[0].con_declaracion_cplt, 10)
            },
            scores: {
                promedio:  parseFloat(scores.rows[0].promedio),
                verde:     parseInt(scores.rows[0].verde, 10),
                amarillo:  parseInt(scores.rows[0].amarillo, 10),
                rojo:      parseInt(scores.rows[0].rojo, 10)
            },
            alertas: alertas.rows.map(r => ({
                tipo:     r.tipo,
                gravedad: r.gravedad,
                total:    parseInt(r.total, 10)
            })),
            empresas: {
                unicas:         parseInt(empresas.rows[0].empresas_unicas, 10),
                participaciones: parseInt(empresas.rows[0].participaciones, 10)
            },
            mercado_publico: {
                total_ocs:         parseInt(ocs.rows[0].total_ocs, 10),
                monto_total_pesos: parseInt(ocs.rows[0].monto_total, 10)
            },
            lobby: {
                matches_candidato: parseInt(lobby.rows[0].total, 10)
            },
            cargos: cargos.rows.map(r => ({
                cargo: r.cargo,
                total: parseInt(r.total, 10)
            }))
        });
    } catch (err) {
        console.error('Error obteniendo estadísticas:', err);
        res.status(500).json({ error: 'Error interno del servidor.' });
    }
};

// GET /api/candidatos/:id/financiamiento — financiamiento electoral SERVEL 2024
const getFinanciamiento = async (req, res) => {
    const { id } = req.params;
    const numId = parseInt(id, 10);
    if (isNaN(numId)) return res.status(400).json({ error: 'ID inválido.' });

    try {
        const { rows: totales } = await db.query(
            `SELECT nombre_servel, cargo_servel, territorio, region, partido, pacto,
                    total_ingresos, total_gastos, n_transacciones
             FROM financiamiento_electoral
             WHERE candidato_id = $1`,
            [numId]
        );

        if (!totales.length) {
            return res.json({ candidato_id: numId, sin_datos: true,
                mensaje: 'Sin datos de financiamiento electoral 2024 en SERVEL.' });
        }

        const [{ rows: donantes }, { rows: gastos }, { rows: alertas }] = await Promise.all([
            db.query(
                `SELECT nombre_donante, rut_donante, tipo,
                        SUM(monto) AS monto_total, COUNT(*) AS n_transacciones
                 FROM donante_electoral
                 WHERE candidato_id = $1
                   AND tipo = 'INGRESOS'
                   AND nombre_donante NOT ILIKE 'Formulario%'
                   AND nombre_donante IS NOT NULL
                 GROUP BY nombre_donante, rut_donante, tipo
                 ORDER BY monto_total DESC
                 LIMIT 20`,
                [numId]
            ),
            db.query(
                `SELECT descripcion, SUM(monto) AS monto_total, COUNT(*) AS n
                 FROM donante_electoral
                 WHERE candidato_id = $1
                   AND tipo = 'GASTO'
                   AND descripcion IS NOT NULL
                 GROUP BY descripcion
                 ORDER BY monto_total DESC
                 LIMIT 10`,
                [numId]
            ),
            db.query(
                `SELECT tipo, gravedad, detalle, fecha_deteccion
                 FROM alerta_probidad
                 WHERE candidato_id = $1 AND tipo = 'DONANTE_PROVEEDOR'
                 ORDER BY gravedad DESC`,
                [numId]
            ),
        ]);

        res.json({
            candidato_id: numId,
            resumen:  totales[0],
            donantes,
            gastos,
            alertas_donante: alertas
        });
    } catch (err) {
        console.error('Error obteniendo financiamiento:', err);
        res.status(500).json({ error: 'Error interno del servidor.' });
    }
};

// GET /api/candidatos/:id/licitaciones?page=1&limit=50
const getLicitaciones = async (req, res) => {
    const { id } = req.params;
    const { page = 1, limit = 50 } = req.query;
    const numId  = parseInt(id, 10);
    const lim    = Math.min(parseInt(limit, 10), 200);
    const offset = (parseInt(page, 10) - 1) * lim;

    if (isNaN(numId)) return res.status(400).json({ error: 'ID inválido.' });

    try {
        const { rows: resumen } = await db.query(
            `SELECT
                COUNT(*)                             AS total_licitaciones,
                COALESCE(SUM(monto_adjudicado), 0)  AS monto_total,
                COUNT(DISTINCT nombre_organismo)     AS organismos_distintos,
                MIN(fecha_adjudicacion)              AS primera,
                MAX(fecha_adjudicacion)              AS ultima
             FROM licitacion
             WHERE candidato_id = $1`,
            [numId]
        );

        const { rows: licitaciones } = await db.query(
            `SELECT codigo, estado, fecha_adjudicacion, monto_adjudicado,
                    nombre_organismo, rut_organismo,
                    nombre_adjudicatario, rut_adjudicatario, link
             FROM licitacion
             WHERE candidato_id = $1
             ORDER BY fecha_adjudicacion DESC NULLS LAST
             LIMIT $2 OFFSET $3`,
            [numId, lim, offset]
        );

        const total = parseInt(resumen[0].total_licitaciones, 10);

        res.json({
            candidato_id: numId,
            resumen: {
                total_licitaciones:   total,
                monto_total_pesos:    parseInt(resumen[0].monto_total, 10),
                organismos_distintos: parseInt(resumen[0].organismos_distintos, 10),
                primera:              resumen[0].primera,
                ultima:               resumen[0].ultima
            },
            meta: {
                page:       parseInt(page, 10),
                limit:      lim,
                totalPages: Math.ceil(total / lim)
            },
            data: licitaciones
        });
    } catch (err) {
        console.error('Error obteniendo licitaciones:', err);
        res.status(500).json({ error: 'Error interno del servidor.' });
    }
};

// GET /api/candidatos/:id/proyectos?page=1&limit=50
const getProyectos = async (req, res) => {
    const { id } = req.params;
    const { page = 1, limit = 50 } = req.query;
    const numId  = parseInt(id, 10);
    const lim    = Math.min(parseInt(limit, 10), 200);
    const offset = (parseInt(page, 10) - 1) * lim;

    if (isNaN(numId)) return res.status(400).json({ error: 'ID inválido.' });

    try {
        const { rows: resumen } = await db.query(
            `SELECT COUNT(*) AS total
             FROM autoria_proyecto
             WHERE candidato_id = $1`,
            [numId]
        );
        const total = parseInt(resumen[0].total, 10);

        if (total === 0) {
            return res.json({ candidato_id: numId, sin_datos: true,
                mensaje: 'Sin proyectos de ley registrados (no es diputado o no tiene mociones en BCN).' });
        }

        const { rows: proyectos } = await db.query(
            `SELECT p.boletin, p.titulo, p.fecha_ingreso, p.tipo_iniciativa,
                    p.camara_origen, p.legislatura, p.link,
                    ap.autor_nombre
             FROM autoria_proyecto ap
             JOIN proyecto_ley p ON p.id = ap.proyecto_id
             WHERE ap.candidato_id = $1
             ORDER BY p.fecha_ingreso DESC NULLS LAST
             LIMIT $2 OFFSET $3`,
            [numId, lim, offset]
        );

        res.json({
            candidato_id: numId,
            meta: {
                total,
                page:       parseInt(page, 10),
                limit:      lim,
                totalPages: Math.ceil(total / lim)
            },
            data: proyectos
        });
    } catch (err) {
        console.error('Error obteniendo proyectos de ley:', err);
        res.status(500).json({ error: 'Error interno del servidor.' });
    }
};

// GET /api/alertados — candidatos con alertas de probidad, ordenados por gravedad
const getAlertados = async (req, res) => {
    try {
        const { rows } = await db.query(
            `SELECT c.id, c.nombres, c.nombre_limpio, c.comuna, c.score_transparencia,
                    car.nombre AS cargo,
                    json_agg(
                        json_build_object(
                            'tipo',     a.tipo,
                            'gravedad', a.gravedad,
                            'detalle',  a.detalle,
                            'fuente_url', a.fuente_url
                        ) ORDER BY
                            CASE a.gravedad WHEN 'ALTA' THEN 1 WHEN 'MEDIA' THEN 2 ELSE 3 END
                    ) AS alertas,
                    MAX(CASE a.gravedad WHEN 'ALTA' THEN 1 WHEN 'MEDIA' THEN 2 ELSE 3 END) AS max_gravedad_ord
             FROM candidato c
             JOIN alerta_probidad a ON a.candidato_id = c.id
             LEFT JOIN cargo car ON c.cargo_id = car.id
             GROUP BY c.id, c.nombres, c.nombre_limpio, c.comuna, c.score_transparencia, car.nombre
             ORDER BY max_gravedad_ord ASC, c.score_transparencia ASC NULLS LAST
             LIMIT 300`
        );
        res.json({ total: rows.length, data: rows });
    } catch (err) {
        console.error('Error obteniendo alertados:', err);
        res.status(500).json({ error: 'Error interno del servidor.' });
    }
};

module.exports = { searchCandidatos, getCandidatoProfile, getPatrimonio, getCongreso, getOrdenes, getStats, getFinanciamiento, getLicitaciones, getProyectos, getAlertados };
