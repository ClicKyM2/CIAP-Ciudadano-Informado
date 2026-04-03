const db = require('../config/database');

// --- ENDPOINT BUSCADOR ---
const searchCandidatos = async (req, res) => {
    const { q = "", page = 1, limit = 20 } = req.query;
    const offset = (page - 1) * limit;
    const searchParam = `%${q}%`;

    try {
        const countQuery = `
            SELECT COUNT(*) 
            FROM candidato 
            WHERE nombres ILIKE $1 OR apellidos ILIKE $1 OR rut ILIKE $1
        `;
        const countRes = await db.query(countQuery, [searchParam]);
        const totalItems = parseInt(countRes.rows[0].count, 10);

        const dataQuery = `
            SELECT c.id, c.rut, c.nombres, c.apellidos, c.score_transparencia, 
                   p.nombre as partido_nombre, car.nombre as cargo_nombre, i.nombre as institucion_nombre
            FROM candidato c
            LEFT JOIN partido p ON c.partido_id = p.id
            LEFT JOIN cargo car ON c.cargo_id = car.id
            LEFT JOIN institucion i ON c.institucion_id = i.id
            WHERE c.nombres ILIKE $1 OR c.apellidos ILIKE $1 OR c.rut ILIKE $1
            ORDER BY c.apellidos ASC
            LIMIT $2 OFFSET $3
        `;
        const { rows } = await db.query(dataQuery, [searchParam, limit, offset]);

        res.json({
            meta: {
                total: totalItems,
                page: parseInt(page, 10),
                limit: parseInt(limit, 10),
                totalPages: Math.ceil(totalItems / limit)
            },
            data: rows
        });

    } catch (error) {
        console.error("❌ Error en búsqueda de candidatos:", error);
        res.status(500).json({ error: "Error interno del servidor al procesar la búsqueda." });
    }
};

// --- ENDPOINT PERFIL INDIVIDUAL ---
const getCandidatoProfile = async (req, res) => {
    const { id } = req.params;
    try {
        // 1. Datos básicos del político
        const queryCandidato = `
            SELECT c.id, c.rut, c.nombres, c.apellidos, c.score_transparencia, 
                   p.nombre as partido, car.nombre as cargo, i.nombre as institucion
            FROM candidato c
            LEFT JOIN partido p ON c.partido_id = p.id
            LEFT JOIN cargo car ON c.cargo_id = car.id
            LEFT JOIN institucion i ON c.institucion_id = i.id
            WHERE c.id = $1
        `;
        const result = await db.query(queryCandidato, [id]);
        
        if (result.rows.length === 0) {
            return res.status(404).json({ error: "Candidato no encontrado" });
        }
        
        const candidato = result.rows[0];

        // 2. Traer las Alertas de Probidad (Generadas por la IA)
        const queryAlertas = `
            SELECT tipo, gravedad, detalle, fecha_deteccion, fuente_url 
            FROM alerta_probidad 
            WHERE candidato_id = $1 
            ORDER BY fecha_deteccion DESC
        `;
        const alertas = await db.query(queryAlertas, [id]);
        candidato.alertas = alertas.rows;

        // 3. Traer las Empresas Vinculadas (CPLT)
        const queryEmpresas = `
            SELECT empresa_rut, empresa_nombre, porcentaje_propiedad 
            FROM participacion_societaria 
            WHERE candidato_id = $1
        `;
        const empresas = await db.query(queryEmpresas, [id]);
        candidato.empresas = empresas.rows;

        res.json(candidato);
    } catch (error) {
        console.error("❌ Error obteniendo perfil:", error);
        res.status(500).json({ error: "Error interno del servidor." });
    }
};

module.exports = { getCandidatoProfile, searchCandidatos };