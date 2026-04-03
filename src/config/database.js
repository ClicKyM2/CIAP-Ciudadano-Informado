const { Pool } = require('pg');

// Lee las credenciales desde las variables de entorno que configuraste en tu terminal
const pool = new Pool({
    user: process.env.DB_USER || 'postgres',
    host: process.env.DB_HOST || 'localhost',
    database: process.env.DB_NAME || 'ciudadano_db',
    password: process.env.DB_PASSWORD || 'root', // Cambia 'root' por tu clave real
    port: process.env.DB_PORT || 5432,
});

pool.on('error', (err) => {
    console.error('❌ Error inesperado en la base de datos', err);
    process.exit(-1);
});

module.exports = {
    query: (text, params) => pool.query(text, params),
};