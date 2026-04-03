const express = require('express');
const router = express.Router();
const { getCandidatoProfile, searchCandidatos } = require('../controllers/candidato');

// Búsqueda general: GET /api/candidatos?q=Boric&page=1
router.get('/', searchCandidatos);

// Perfil específico: GET /api/candidatos/5
router.get('/:id', getCandidatoProfile);

module.exports = router;