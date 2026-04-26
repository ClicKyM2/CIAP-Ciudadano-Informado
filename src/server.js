require('dotenv').config();
const path = require('path');
const express = require('express');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
const candidatosRoutes = require('./routes/candidatos');
const { getStats, getAlertados } = require('./controllers/candidato');

const app = express();
const PORT = process.env.PORT || 3000;

// Rate limiting — ventana de 15 min
const limiterGeneral = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 300,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Demasiadas solicitudes. Intenta nuevamente en 15 minutos.' }
});

// Endpoint de búsqueda recibe más carga — límite más estricto
const limiterBusqueda = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 80,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Demasiadas búsquedas. Intenta nuevamente en 15 minutos.' }
});

// Middlewares
app.use(cors());
app.use(express.json());
app.use(limiterGeneral);

// Registro de Rutas
app.use('/api/candidatos', limiterBusqueda, candidatosRoutes);
app.get('/api/stats', getStats);
app.get('/api/alertados', getAlertados);

// Servir la plataforma HTML desde http://localhost:3000/
const HTML_FILE = path.join(__dirname, '..', 'contexto', 'ciudadano_informado_plataforma.html');
app.get('/', (req, res) => res.sendFile(HTML_FILE));

// Arrancar servidor
app.listen(PORT, () => {
    console.log(`✅ Servidor Node.js corriendo en el puerto ${PORT}`);
    console.log(`🌐 Plataforma:  http://localhost:${PORT}/`);
    console.log(`📡 API:         http://localhost:${PORT}/api/candidatos`);
});