const express = require('express');
const cors = require('cors');
const candidatosRoutes = require('./routes/candidatos');

const app = express();
const PORT = process.env.PORT || 3000;

// Middlewares
app.use(cors()); // Permite que tu frontend (ej: React o HTML) se conecte a esta API
app.use(express.json());

// Registro de Rutas
app.use('/api/candidatos', candidatosRoutes);

// Ruta de prueba para ver si el servidor está vivo
app.get('/', (req, res) => {
    res.json({ mensaje: "API Ciudadana funcionando correctamente 🚀" });
});

// Arrancar servidor
app.listen(PORT, () => {
    console.log(`✅ Servidor Node.js corriendo en el puerto ${PORT}`);
    console.log(`📡 Puedes probar el buscador en: http://localhost:${PORT}/api/candidatos`);
});