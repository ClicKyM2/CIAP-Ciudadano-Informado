const express = require('express');
const router = express.Router();
const { getCandidatoProfile, searchCandidatos, getPatrimonio, getCongreso, getOrdenes, getFinanciamiento, getLicitaciones, getProyectos } = require('../controllers/candidato');

// Búsqueda general: GET /api/candidatos?q=Boric&cargo=DIPUTADO&page=1
router.get('/', searchCandidatos);

// Historial de declaraciones CPLT: GET /api/candidatos/5/patrimonio
router.get('/:id/patrimonio', getPatrimonio);

// Votaciones y asistencia en el Congreso: GET /api/candidatos/5/congreso
router.get('/:id/congreso', getCongreso);

// Órdenes de compra donde empresa del candidato es proveedora: GET /api/candidatos/5/ordenes
router.get('/:id/ordenes', getOrdenes);

// Financiamiento electoral SERVEL 2024: GET /api/candidatos/5/financiamiento
router.get('/:id/financiamiento', getFinanciamiento);

// Licitaciones adjudicadas a empresas del candidato: GET /api/candidatos/5/licitaciones
router.get('/:id/licitaciones', getLicitaciones);

// Proyectos de ley (mociones BCN): GET /api/candidatos/5/proyectos
router.get('/:id/proyectos', getProyectos);

// Perfil específico: GET /api/candidatos/5
router.get('/:id', getCandidatoProfile);

module.exports = router;