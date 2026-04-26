---
tags: [contexto, enlazada]
---

## Archivos clave del proyecto

```
CIAP/
├── schema.sql                       # Referencia de estructura (ATENCIÓN: difiere de la DB real)
├── contexto/fuentes_descarga.md     # URLs y comandos de descarga de cada fuente de datos (CPLT, Mercado Público, SERVEL, Congreso)
├── requirements.txt                 # Dependencias Python (incluye cloudscraper)
├── .env                             # Variables de entorno (NO subir a git)
├── railway.toml                     # Configuración de deploy Railway (Node.js + healthcheck)
├── vercel.json                      # Configuración de deploy Vercel (HTML estático)
├── scripts/
│   ├── pipeline/                    # Ejecutar desde la raíz del proyecto
│   │   ├── pipeline_ingesta.py      # ETL principal Servel → PostgreSQL
│   │   ├── extraer_ruts_infoprobidad.py  # Obtiene RUTs reales desde CPLT
│   │   ├── poblar_participaciones.py     # Extrae empresas CPLT → participacion_societaria
│   │   ├── importar_representaciones.py  # Importa representaciones.csv → temp_representaciones
│   │   ├── importar_lobby.py             # Importa temp_audiencia, temp_asistencia_pasivo y match_candidato_lobby
│   │   ├── calcular_scores.py            # Calcula score_transparencia para cada candidato
│   │   ├── ia_fiscalizadora.py           # Motor de detección de conflictos (AUTOLOBBY)
│   │   ├── enriquecer_empresas.py        # Enriquece empresa_enriquecida + detecta directores CMF
│   │   └── importar_declaraciones.py     # Importa csvdeclaraciones.csv → declaracion_cplt (113.805 filas)
│   ├── limpieza/                    # Scripts de limpieza y normalización de datos
│   ├── bots/
│   │   └── bot_rescate_ruts.py      # Bot Selenium unificado (fusión ninja+visual). Lee funcionarios_sin_rut.csv, escribe funcionarios_rescatados_bots.csv
│   ├── herramientas/                # Utilidades generales (consolidador, cruce)
│   └── extractores/                 # Módulo Python: CPLT, Lobby, Congreso, Mercado Público
├── src/
│   ├── server.js                    # API REST Node.js/Express (puerto 3000)
│   ├── config/database.js           # Conexión PostgreSQL via pg Pool
│   ├── routes/candidatos.js         # Rutas: GET /, GET /:id, GET /:id/patrimonio, GET /:id/congreso, GET /:id/ordenes, GET /:id/financiamiento
│   └── controllers/candidato.js    # searchCandidatos, getCandidatoProfile, getPatrimonio, getCongreso, getOrdenes, getFinanciamiento, getLicitaciones, getProyectos, getStats. getCandidatoProfile y getFinanciamiento usan Promise.all para queries paralelas.
├── contexto/
│   ├── CONTEXTO.md                  # Este archivo — historial y arquitectura
│   └── ciudadano_informado_plataforma.html  # Frontend conectado a API real
├── diario/                          # Notas automáticas de sesión (hook UserPromptSubmit)
│   └── INDEX.md                     # Índice del diario de sesiones
├── Indice_Arquitectura.md           # Índice Obsidian del proyecto — entrada al Graph View
├── Separation_of_Concerns.md        # ADR-001: separación de capas del sistema
├── CLAUDE.md                        # Reglas del sistema para Claude Code
├── .mcp.json                        # MCP servers: gemini-search, obsidian
├── scripts/herramientas/
│   ├── obsidian_logger.py           # Hook: crea notas diario/ al enviar prompt o editar archivo
│   └── vault_tagger.py             # Etiqueta notas .md con YAML frontmatter para Obsidian
└── data/
    ├── csvacciones.csv              # 48.681 filas — acciones CPLT (fuente principal de empresas)
    ├── csvdeclaraciones.csv         # 118.458 declaraciones CPLT (Kast parcial). Columnas: UriDeclarante, Declaracion
    ├── representaciones.csv         # 1.548.503 filas UTF-16 — entidades que hicieron lobby
    ├── MAESTRO_RUTS_CONSOLIDADOS.csv # 5.468 RUTs reales con link_declaracion
    ├── MAESTRO_EXPANDIDO.csv        # 6.514 funcionarios (RUTs todos NaN — no usar directo)
    ├── progreso_participaciones.json # Checkpoint del poblar_participaciones.py
    ├── mapa_dipid_bcn.json          # 827 entradas DIPID→BCN_ID descargadas via SPARQL bulk. Regenerar con: ingesta_bcn.py --descargar-mapa
    └── progreso_bcn.json            # Checkpoint del ingesta_bcn.py
```

Ver **R5** en REGLAS OBLIGATORIAS para la regla de rutas relativas.

---

---
*Sub-nota de [[CONTEXTO]] · [[Indice_Arquitectura]]*
