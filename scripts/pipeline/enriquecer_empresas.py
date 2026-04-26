"""
enriquecer_empresas.py - Enriquece datos de empresas y detecta directores CMF
Ejecutar desde la raiz del proyecto: python scripts/pipeline/enriquecer_empresas.py

PASOS:
  1. DDL: Crear tablas empresa_enriquecida y directorio_cmf si no existen
  2. CSV:  Leer csvacciones.csv (CPLT) y poblar empresa_enriquecida con giro/nombre.
           Ya contiene datos de giro para todas las empresas declaradas.
  3. CMF:  Para cada candidato con RUT real, detecta si aparece como director en
           empresas reguladas por la CMF (SA abiertas, fondos, seguros, AFP).
           Usa el portal web de CMF sin autenticacion.
  4. Alertas: Genera alertas DIRECTOR_NO_DECLARADO si hay directorship CMF
              que el funcionario no declaro en su declaracion CPLT.

Opciones:
  --solo-csv      Solo ejecutar paso 2 (carga de CSV local)
  --solo-cmf      Solo ejecutar paso 3 (deteccion CMF) + paso 4 (alertas)
  --solo-alertas  Solo regenerar alertas DIRECTOR_NO_DECLARADO
  --estado        Mostrar conteos actuales sin ejecutar nada

NOTA SII: El CAPTCHA de zeus.sii.cl cambio su mecanismo y no es scripteable sin
          browser headless. Se usa csvacciones.csv como fuente alternativa de giro,
          que contiene la misma informacion para las empresas declaradas en CPLT.

ADVERTENCIA CMF: ~5.468 candidatos x 3 mercados x 1s = ~4.5 horas.
                 El checkpoint permite interrumpir (Ctrl+C) y reanudar.
"""

import os
import sys
import json
import time
import argparse
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from scripts.extractores.sii import cargar_indice_csv, consultar_empresa_local, split_rut
from scripts.extractores.cmf import consultar_directorio_cmf

load_dotenv()

CHECKPOINT_FILE = "data/progreso_enriquecimiento.json"
CSV_ACCIONES    = "data/csvacciones.csv"


# ---------------------------------------------------------------------------
# Conexion y log
# ---------------------------------------------------------------------------

def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "ciudadano_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
        client_encoding="UTF8"
    )

def log(msg=""):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def leer_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"csv_listo": False, "cmf_procesados": []}

def guardar_checkpoint(data: dict):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL_EMPRESA_ENRIQUECIDA = """
CREATE TABLE IF NOT EXISTS empresa_enriquecida (
    empresa_rut       VARCHAR(12) PRIMARY KEY,
    razon_social_sii  VARCHAR(255),
    giro_principal    VARCHAR(255),
    codigo_giro       VARCHAR(20),
    fecha_inicio_act  DATE,
    fecha_consulta    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado_consulta   VARCHAR(20) DEFAULT 'OK'
);
"""

DDL_DIRECTORIO_CMF = """
CREATE TABLE IF NOT EXISTS directorio_cmf (
    id                SERIAL PRIMARY KEY,
    candidato_id      INTEGER REFERENCES candidato(id),
    rut_entidad       VARCHAR(12) NOT NULL,
    nombre_entidad    VARCHAR(255),
    cargo             VARCHAR(100),
    cargo_ejec        VARCHAR(100),
    fecha_nombramiento DATE,
    fecha_cesacion    DATE,
    mercado           VARCHAR(10),
    fecha_consulta    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

DDL_INDEX_CMF = """
CREATE INDEX IF NOT EXISTS idx_directorio_cmf_candidato
    ON directorio_cmf(candidato_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_directorio_cmf_unico
    ON directorio_cmf(candidato_id, rut_entidad, mercado, COALESCE(cargo, 'NONE'));
"""

def crear_tablas(cur):
    log("Creando tablas si no existen...")
    cur.execute(DDL_EMPRESA_ENRIQUECIDA)
    cur.execute(DDL_DIRECTORIO_CMF)
    cur.execute(DDL_INDEX_CMF)
    log("  empresa_enriquecida: OK")
    log("  directorio_cmf: OK")


# ---------------------------------------------------------------------------
# Paso 2: Enriquecimiento desde CSV local (csvacciones.csv)
# ---------------------------------------------------------------------------

def paso_csv(conn):
    log("")
    log("=" * 60)
    log("PASO 2 - Enriquecimiento desde csvacciones.csv (CPLT)")
    log("=" * 60)

    checkpoint = leer_checkpoint()
    if checkpoint.get("csv_listo"):
        log("CSV ya procesado segun checkpoint. Saltar.")
        return

    log(f"Cargando {CSV_ACCIONES} ...")
    indice = cargar_indice_csv(CSV_ACCIONES)
    log(f"  Empresas en indice local: {len(indice)}")

    cur = conn.cursor()

    # Empresas pendientes en participacion_societaria
    cur.execute("""
        SELECT DISTINCT empresa_rut
        FROM participacion_societaria
        WHERE empresa_rut IS NOT NULL AND empresa_rut != ''
    """)
    todos = [row[0] for row in cur.fetchall()]

    cur.execute("SELECT empresa_rut FROM empresa_enriquecida WHERE estado_consulta='OK'")
    ya_ok = {row[0] for row in cur.fetchall()}

    pendientes = [r for r in todos if r not in ya_ok]
    log(f"Empresas totales: {len(todos)} | Ya enriquecidas: {len(ya_ok)} | Pendientes: {len(pendientes)}")

    ok_count  = 0
    no_count  = 0

    for rut_raw in pendientes:
        datos = consultar_empresa_local(rut_raw, indice)

        if datos:
            cur.execute("""
                INSERT INTO empresa_enriquecida
                    (empresa_rut, razon_social_sii, giro_principal, codigo_giro,
                     fecha_consulta, estado_consulta)
                VALUES (%s, %s, %s, %s, NOW(), 'OK')
                ON CONFLICT (empresa_rut) DO UPDATE SET
                    razon_social_sii = EXCLUDED.razon_social_sii,
                    giro_principal   = EXCLUDED.giro_principal,
                    fecha_consulta   = EXCLUDED.fecha_consulta,
                    estado_consulta  = 'OK'
            """, (
                rut_raw,
                datos.get("razon_social"),
                datos.get("giro_principal"),
                datos.get("codigo_giro"),
            ))
            ok_count += 1
        else:
            cur.execute("""
                INSERT INTO empresa_enriquecida
                    (empresa_rut, fecha_consulta, estado_consulta)
                VALUES (%s, NOW(), 'NO_EN_CSV')
                ON CONFLICT (empresa_rut) DO NOTHING
            """, (rut_raw,))
            no_count += 1

    conn.commit()

    checkpoint["csv_listo"] = True
    guardar_checkpoint(checkpoint)

    log(f"CSV completado: {ok_count} encontradas, {no_count} sin datos en CSV")
    cur.close()


# ---------------------------------------------------------------------------
# Paso 3: Deteccion CMF
# ---------------------------------------------------------------------------

def paso_cmf(conn):
    log("")
    log("=" * 60)
    log("PASO 3 - Deteccion de directores en CMF")
    log("=" * 60)
    log("Este paso puede tardar ~4-5 horas para todos los candidatos.")
    log("Puedes interrumpir con Ctrl+C y reanudar — el checkpoint lo recuerda.")
    log("")

    checkpoint = leer_checkpoint()
    ya_procesados = set(str(x) for x in checkpoint.get("cmf_procesados", []))

    cur = conn.cursor()

    # Candidatos con RUT real no procesados aun
    cur.execute("""
        SELECT id, rut, nombres
        FROM candidato
        WHERE rut NOT LIKE 'CPLT-%%'
          AND rut NOT LIKE 'SERVEL-%%'
          AND rut NOT LIKE 'DIPCAM-%%'
          AND rut NOT LIKE 'CPLT-NEW-%%'
          AND id NOT IN (
              SELECT DISTINCT candidato_id
              FROM directorio_cmf
              WHERE rut_entidad != 'NONE'
                 OR rut_entidad IS NULL
          )
        ORDER BY id
    """)
    # Excluir los que ya tienen el sentinel NONE (consultados, sin resultados)
    cur2 = conn.cursor()
    cur2.execute("SELECT DISTINCT candidato_id FROM directorio_cmf WHERE rut_entidad = 'NONE'")
    con_sentinel = {row[0] for row in cur2.fetchall()}
    cur2.close()

    pendientes = [
        (row[0], row[1], row[2])
        for row in cur.fetchall()
        if str(row[0]) not in ya_procesados
        and row[0] not in con_sentinel
    ]

    total = len(pendientes)
    log(f"Candidatos pendientes de consultar en CMF: {total}")

    if total == 0:
        log("Nada que procesar.")
        cur.close()
        return

    encontrados = 0

    try:
        for i, (cid, rut, nombre) in enumerate(pendientes, 1):
            resultados = consultar_directorio_cmf(rut)

            if resultados:
                for r in resultados:
                    _insertar_directorio_cmf(cur, cid, r)
                conn.commit()
                encontrados += len(resultados)
                log(f"  CMF [{i}/{total}] HALLAZGO {nombre[:35]} - "
                    f"{len(resultados)} rol(es)")
            else:
                # Insertar sentinel para no volver a consultar este candidato
                cur.execute("""
                    INSERT INTO directorio_cmf
                        (candidato_id, rut_entidad, nombre_entidad,
                         mercado, fecha_consulta)
                    VALUES (%s, 'NONE', 'SIN_REGISTRO_CMF', 'N', NOW())
                    ON CONFLICT DO NOTHING
                """, (cid,))
                conn.commit()

            ya_procesados.add(str(cid))

            # Checkpoint cada 100 candidatos
            if i % 100 == 0:
                checkpoint["cmf_procesados"] = list(ya_procesados)
                guardar_checkpoint(checkpoint)
                log(f"  Checkpoint CMF [{i}/{total}] - {encontrados} hallazgos acumulados")

    except KeyboardInterrupt:
        log("Interrumpido. Guardando checkpoint...")

    checkpoint["cmf_procesados"] = list(ya_procesados)
    guardar_checkpoint(checkpoint)
    log(f"CMF completado: {encontrados} roles encontrados")
    cur.close()


def _insertar_directorio_cmf(cur, candidato_id: int, r: dict):
    cur.execute("""
        INSERT INTO directorio_cmf
            (candidato_id, rut_entidad, nombre_entidad, cargo, cargo_ejec,
             fecha_nombramiento, fecha_cesacion, mercado, fecha_consulta)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT DO NOTHING
    """, (
        candidato_id,
        r.get("rut_entidad"),
        r.get("nombre_entidad"),
        r.get("cargo"),
        r.get("cargo_ejec"),
        r.get("fecha_nombramiento"),
        r.get("fecha_cesacion"),
        r.get("mercado"),
    ))


# ---------------------------------------------------------------------------
# Paso 4: Alertas DIRECTOR_NO_DECLARADO
# ---------------------------------------------------------------------------

def paso_alertas(conn):
    log("")
    log("=" * 60)
    log("PASO 4 - Alertas DIRECTOR_NO_DECLARADO")
    log("=" * 60)

    cur = conn.cursor()

    # Agrupamos por (candidato_id, rut_entidad) para evitar duplicados por mercado CMF.
    # STRING_AGG consolida los mercados en un solo detalle ("Mercado de Valores, Seguros").
    cur.execute("""
        SELECT
            dc.candidato_id,
            dc.rut_entidad,
            dc.nombre_entidad,
            MAX(dc.cargo) AS cargo,
            STRING_AGG(DISTINCT dc.mercado, ',' ORDER BY dc.mercado) AS mercados,
            c.nombres
        FROM directorio_cmf dc
        JOIN candidato c ON c.id = dc.candidato_id
        WHERE dc.rut_entidad != 'NONE'
          AND dc.fecha_cesacion IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM participacion_societaria ps
              WHERE ps.candidato_id = dc.candidato_id
                AND ps.empresa_rut = dc.rut_entidad
          )
          AND NOT EXISTS (
              SELECT 1 FROM alerta_probidad ap
              WHERE ap.candidato_id = dc.candidato_id
                AND ap.tipo = 'DIRECTOR_NO_DECLARADO'
                AND ap.detalle LIKE '%%' || dc.rut_entidad || '%%'
          )
        GROUP BY dc.candidato_id, dc.rut_entidad, dc.nombre_entidad, c.nombres
    """)
    casos = cur.fetchall()
    log(f"Nuevos casos DIRECTOR_NO_DECLARADO: {len(casos)}")

    mercado_desc = {
        "V": "Mercado de Valores",
        "O": "Otras entidades reguladas CMF",
        "S": "Seguros"
    }

    for cid, rut_entidad, nombre_entidad, cargo, mercados, nombres in casos:
        desc = ", ".join(mercado_desc.get(m, m) for m in mercados.split(","))
        detalle = (
            f"El funcionario {nombres} figura como {cargo or 'Director'} "
            f"en {nombre_entidad} (RUT: {rut_entidad}) segun CMF "
            f"({desc}) pero NO declaro esta empresa en su "
            f"declaracion de patrimonio CPLT."
        )
        cur.execute("""
            INSERT INTO alerta_probidad
                (candidato_id, tipo, gravedad, detalle,
                 fecha_deteccion, fuente_url)
            VALUES (%s, 'DIRECTOR_NO_DECLARADO', 'ALTA', %s, NOW(),
                'https://www.cmfchile.cl/institucional/mercados/reporte_ejecutivos.php')
            ON CONFLICT DO NOTHING
        """, (cid, detalle))

    conn.commit()
    log(f"Alertas insertadas: {len(casos)}")
    cur.close()


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

def mostrar_estado(conn):
    cur = conn.cursor()

    def cnt(tabla, where=""):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tabla} {where}")
            return cur.fetchone()[0]
        except Exception:
            return "N/A"

    w_ok      = "WHERE estado_consulta='OK'"
    w_hall    = "WHERE rut_entidad != 'NONE'"
    w_alerta  = "WHERE tipo='DIRECTOR_NO_DECLARADO'"
    log("Estado actual:")
    log(f"  participacion_societaria      : {cnt('participacion_societaria')}")
    log(f"  empresa_enriquecida (OK)      : {cnt('empresa_enriquecida', w_ok)}")
    log(f"  empresa_enriquecida (total)   : {cnt('empresa_enriquecida')}")
    log(f"  directorio_cmf (total)        : {cnt('directorio_cmf')}")
    log(f"  directorio_cmf (hallazgos)    : {cnt('directorio_cmf', w_hall)}")
    log(f"  alertas DIRECTOR_NO_DECLARADO : {cnt('alerta_probidad', w_alerta)}")
    cur.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Enriquecer empresas y detectar directores CMF")
    parser.add_argument("--solo-csv",     action="store_true", help="Solo paso 2: carga CSV local")
    parser.add_argument("--solo-cmf",     action="store_true", help="Solo pasos 3+4: CMF y alertas")
    parser.add_argument("--solo-alertas", action="store_true", help="Solo paso 4: generar alertas")
    parser.add_argument("--estado",       action="store_true", help="Solo mostrar estado")
    args = parser.parse_args()

    conn = get_conn()

    if args.estado:
        mostrar_estado(conn)
        conn.close()
        return

    cur = conn.cursor()
    crear_tablas(cur)
    conn.commit()
    cur.close()

    if args.solo_alertas:
        paso_alertas(conn)
    elif args.solo_cmf:
        paso_cmf(conn)
        paso_alertas(conn)
    elif args.solo_csv:
        paso_csv(conn)
    else:
        paso_csv(conn)
        paso_cmf(conn)
        paso_alertas(conn)

    mostrar_estado(conn)
    conn.close()
    log("Enriquecimiento completado.")


if __name__ == "__main__":
    main()
