"""
importar_lobby.py
Importa las 3 tablas de lobby que no tenian script en el pipeline:

  - temp_audiencia          <- {LOBBY_DIR}/audiencia_final.csv     (894K filas)
  - temp_asistencia_pasivo  <- {LOBBY_DIR}/asistenciasPasivos.csv  (894K filas, 6 cols completas)
  - match_candidato_lobby   <- cruce candidato x pasivo via pg_trgm

NOTA: limpiar_audiencias.py solo convierte encoding. Este script hace la importacion real.
      limpiar_asistencias.py toma solo 2 cols. Este script usa el CSV original de 6 cols.

Configurar la carpeta de los CSVs de lobby via variable de entorno:
    LOBBY_DIR=C:\\Users\\Public  (default)

Ejecutar desde la raiz del proyecto:
    python scripts/pipeline/importar_lobby.py
"""

import os
import csv
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

LOBBY_DIR      = os.getenv("LOBBY_DIR", r"C:\Users\Public")
AUDIENCIA_CSV  = os.path.join(LOBBY_DIR, "audiencia_final.csv")
PASIVOS_CSV    = os.path.join(LOBBY_DIR, "asistenciasPasivos.csv")
SIMILITUD_MIN  = 0.25   # umbral bajo: match inclusivo, la IA refina a 0.75
CHUNK          = 50000


def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "ciudadano_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )


def tabla_count(conn, tabla):
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {tabla}")
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# 1. temp_audiencia
# ---------------------------------------------------------------------------

def importar_audiencias(conn):
    if not os.path.exists(AUDIENCIA_CSV):
        print(f"  SKIP: {AUDIENCIA_CSV} no existe")
        return 0

    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='temp_audiencia'")
        existe = cur.fetchone()
        if existe:
            n = tabla_count(conn, "temp_audiencia")
            if n > 500000:
                print(f"  temp_audiencia ya tiene {n:,} filas - saltando")
                return n

        print("  Recreando temp_audiencia desde audiencia_final.csv...")
        cur.execute("DROP TABLE IF EXISTS temp_audiencia")
        cur.execute("""
            CREATE TABLE temp_audiencia (
                uriaudiencia       TEXT,
                codigouri          TEXT,
                uriorganismo       TEXT,
                organismo          TEXT,
                fechaevento        TEXT,
                fecharegistro      TEXT,
                fechaactualizacion TEXT
            )
        """)
        conn.commit()

    total = 0
    batch = []
    with open(AUDIENCIA_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            batch.append((
                (row.get("uriAudiencia") or "")[:500],
                (row.get("CodigoURI") or "")[:50],
                (row.get("uriOrganismo") or "")[:500],
                (row.get("organismo") or "")[:255],
                (row.get("fechaEvento") or "")[:30],
                (row.get("fechaRegistro") or "")[:40],
                (row.get("fechaActualizacion") or "")[:40],
            ))
            if len(batch) >= CHUNK:
                with conn.cursor() as cur:
                    execute_values(cur, "INSERT INTO temp_audiencia VALUES %s", batch)
                conn.commit()
                total += len(batch)
                batch = []
                print(f"    {total:,}")
    if batch:
        with conn.cursor() as cur:
            execute_values(cur, "INSERT INTO temp_audiencia VALUES %s", batch)
        conn.commit()
        total += len(batch)

    with conn.cursor() as cur:
        cur.execute("CREATE INDEX idx_audiencia_codigo ON temp_audiencia(codigouri)")
    conn.commit()
    print(f"  temp_audiencia: {total:,} filas")
    return total


# ---------------------------------------------------------------------------
# 2. temp_asistencia_pasivo
# ---------------------------------------------------------------------------

def importar_asistencias(conn):
    if not os.path.exists(PASIVOS_CSV):
        print(f"  SKIP: {PASIVOS_CSV} no existe")
        return 0

    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='temp_asistencia_pasivo'")
        existe = cur.fetchone()
        if existe:
            n = tabla_count(conn, "temp_asistencia_pasivo")
            if n > 500000:
                print(f"  temp_asistencia_pasivo ya tiene {n:,} filas - saltando")
                return n

        print("  Recreando temp_asistencia_pasivo desde asistenciasPasivos.csv (6 cols completas)...")
        cur.execute("DROP TABLE IF EXISTS temp_asistencia_pasivo")
        cur.execute("""
            CREATE TABLE temp_asistencia_pasivo (
                codigopasivo    TEXT,
                pasivo          TEXT,
                codigoorganismo TEXT,
                organismo       TEXT,
                cargo           TEXT,
                codigoaudiencia TEXT
            )
        """)
        conn.commit()

    total = 0
    batch = []
    with open(PASIVOS_CSV, encoding="utf-16") as f:
        reader = csv.DictReader(f)
        for row in reader:
            batch.append((
                (row.get("codigoPasivo") or "")[:50],
                (row.get("pasivo") or "")[:255],
                (row.get("codigoOrganismo") or "")[:50],
                (row.get("organismo") or "")[:255],
                (row.get("cargo") or "")[:255],
                (row.get("codigoAudiencia") or "")[:50],
            ))
            if len(batch) >= CHUNK:
                with conn.cursor() as cur:
                    execute_values(cur, "INSERT INTO temp_asistencia_pasivo VALUES %s", batch)
                conn.commit()
                total += len(batch)
                batch = []
                print(f"    {total:,}")
    if batch:
        with conn.cursor() as cur:
            execute_values(cur, "INSERT INTO temp_asistencia_pasivo VALUES %s", batch)
        conn.commit()
        total += len(batch)

    with conn.cursor() as cur:
        cur.execute("CREATE INDEX idx_pasivo_codigo   ON temp_asistencia_pasivo(codigopasivo)")
        cur.execute("CREATE INDEX idx_pasivo_audiencia ON temp_asistencia_pasivo(codigoaudiencia)")
    conn.commit()
    print(f"  temp_asistencia_pasivo: {total:,} filas")
    return total


# ---------------------------------------------------------------------------
# 3. match_candidato_lobby
# ---------------------------------------------------------------------------

def crear_match_lobby(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='match_candidato_lobby'")
        existe = cur.fetchone()
        if existe:
            n = tabla_count(conn, "match_candidato_lobby")
            if n > 100000:
                print(f"  match_candidato_lobby ya tiene {n:,} filas - saltando")
                return n

        print("  Creando match_candidato_lobby via pg_trgm (puede tardar varios minutos)...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

        cur.execute("DROP TABLE IF EXISTS match_candidato_lobby")
        cur.execute("""
            CREATE TABLE match_candidato_lobby (
                rut              VARCHAR(20),
                nombres          VARCHAR(255),
                apellidos        VARCHAR(255),
                nombre_candidato TEXT,
                codigo_pasivo    TEXT,
                similitud        REAL
            )
        """)
        conn.commit()

        # Tabla temporal: pasivos unicos con nombre en mayusculas para comparar
        print("    Construyendo pasivos unicos...")
        cur.execute("DROP TABLE IF EXISTS _tmp_pasivos_match")
        cur.execute("""
            CREATE TEMP TABLE _tmp_pasivos_match AS
            SELECT DISTINCT ON (codigopasivo)
                codigopasivo,
                UPPER(pasivo) AS pasivo_upper
            FROM temp_asistencia_pasivo
            WHERE pasivo IS NOT NULL AND pasivo <> ''
        """)
        cur.execute("CREATE INDEX ON _tmp_pasivos_match USING GIN (pasivo_upper gin_trgm_ops)")
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM _tmp_pasivos_match")
        n_pasivos = cur.fetchone()[0]
        print(f"    Pasivos unicos: {n_pasivos:,}")

        # Ajustar umbral de similitud y cruzar
        cur.execute(f"SELECT set_limit({SIMILITUD_MIN})")
        print(f"    Cruzando candidatos vs pasivos (umbral={SIMILITUD_MIN})...")
        cur.execute("""
            INSERT INTO match_candidato_lobby
                (rut, nombres, apellidos, nombre_candidato, codigo_pasivo, similitud)
            SELECT
                c.rut,
                c.nombres,
                COALESCE(c.apellidos, ''),
                c.nombre_limpio,
                p.codigopasivo,
                similarity(c.nombre_limpio, p.pasivo_upper)
            FROM candidato c
            JOIN _tmp_pasivos_match p ON c.nombre_limpio %% p.pasivo_upper
            WHERE c.rut NOT LIKE 'CPLT-%%'
              AND c.rut NOT LIKE 'SERVEL-%%'
              AND c.rut NOT LIKE 'DIPCAM-%%'
              AND c.nombre_limpio IS NOT NULL
              AND length(c.nombre_limpio) >= 10
        """)
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM match_candidato_lobby")
        n = cur.fetchone()[0]
        cur.execute("CREATE INDEX idx_match_rut    ON match_candidato_lobby(rut)")
        cur.execute("CREATE INDEX idx_match_pasivo ON match_candidato_lobby(codigo_pasivo)")
        conn.commit()

    print(f"  match_candidato_lobby: {n:,} filas")
    return n


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Conectando a PostgreSQL...")
    conn = get_conn()

    print("[1/3] Importando audiencias...")
    importar_audiencias(conn)

    print("[2/3] Importando asistencias de pasivos (6 columnas completas)...")
    importar_asistencias(conn)

    print("[3/3] Creando match candidato-lobby via pg_trgm...")
    crear_match_lobby(conn)

    conn.close()
    print("\nPROCESO COMPLETADO")


if __name__ == "__main__":
    main()
