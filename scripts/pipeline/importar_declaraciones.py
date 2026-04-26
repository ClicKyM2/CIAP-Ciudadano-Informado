"""
importar_declaraciones.py - Importa csvdeclaraciones.csv a PostgreSQL
Crea la tabla declaracion_cplt y la vincula a candidato via uri_declarante.

Ejecutar desde la raiz del proyecto:
    python scripts/pipeline/importar_declaraciones.py

El CSV tiene 113K filas (una por declaracion). Las columnas usadas:
  UriDeclaracion  — URL unica de la declaracion (PK)
  UriDeclarante   — URL del declarante (FK a candidato.uri_declarante)
  Tipo            — "INGRESO A LA FUNCION", "ACTUALIZACION PERIODICA", etc.
  Asuncion        — Fecha asuncion al cargo (YYYY-MM-DD)
  Declaracion     — Fecha de la declaracion (YYYY-MM-DD)
  Institucion     — Nombre de la institucion
  Cargo           — Cargo declarado
  RegimenPat      — Regimen patrimonial (SEPARACION TOTAL, SOCIEDAD CONYUGAL, etc.)
"""

import os
import sys
import pandas as pd
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

load_dotenv()

CSV_PATH = "data/csvdeclaraciones.csv"

DDL = """
CREATE TABLE IF NOT EXISTS declaracion_cplt (
    uri_declaracion  VARCHAR(200) PRIMARY KEY,
    uri_declarante   VARCHAR(200) NOT NULL,
    tipo             VARCHAR(100),
    institucion      VARCHAR(255),
    cargo            VARCHAR(255),
    regimen_pat      VARCHAR(100),
    fecha_asuncion   DATE,
    fecha_declaracion DATE
);
CREATE INDEX IF NOT EXISTS idx_declaracion_cplt_declarante
    ON declaracion_cplt(uri_declarante);
"""


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


def parsear_fecha(val):
    """Convierte valor del CSV a date o None."""
    if not val or str(val).strip() in ("", "nan", "NaT"):
        return None
    try:
        return str(pd.to_datetime(val).date())
    except Exception:
        return None


def main():
    log("Conectando a PostgreSQL...")
    conn = get_conn()
    cur = conn.cursor()

    log("Creando tabla declaracion_cplt si no existe...")
    cur.execute(DDL)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM declaracion_cplt")
    ya_existentes = cur.fetchone()[0]
    log(f"Registros ya en tabla: {ya_existentes:,} (se insertaran solo los nuevos via ON CONFLICT DO NOTHING)")

    log(f"Leyendo {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    log(f"Filas en CSV: {len(df)}")

    # Columnas requeridas
    col_uri_dec  = "UriDeclaracion"
    col_uri_decl = "UriDeclarante"
    col_tipo     = "Tipo"
    col_inst     = "Institucion"
    col_cargo    = "Cargo"
    col_regimen  = "RegimenPat"
    col_asuncion = "Asuncion"
    col_decl     = "Declaracion"

    for col in [col_uri_dec, col_uri_decl]:
        if col not in df.columns:
            log(f"ERROR: columna '{col}' no encontrada en CSV.")
            return

    insertados = 0
    errores    = 0
    batch      = []
    BATCH_SIZE = 2000

    def flush_batch(b):
        nonlocal insertados
        cur.executemany("""
            INSERT INTO declaracion_cplt
                (uri_declaracion, uri_declarante, tipo, institucion, cargo,
                 regimen_pat, fecha_asuncion, fecha_declaracion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (uri_declaracion) DO NOTHING
        """, b)
        conn.commit()
        insertados += len(b)

    for _, row in df.iterrows():
        uri_dec  = str(row.get(col_uri_dec,  "") or "").strip()
        uri_decl = str(row.get(col_uri_decl, "") or "").strip()

        if not uri_dec or not uri_decl or uri_dec == "nan" or uri_decl == "nan":
            errores += 1
            continue

        tipo     = str(row.get(col_tipo,     "") or "").strip() or None
        inst     = str(row.get(col_inst,     "") or "").strip() or None
        cargo    = str(row.get(col_cargo,    "") or "").strip() or None
        regimen  = str(row.get(col_regimen,  "") or "").strip() or None
        f_asun   = parsear_fecha(row.get(col_asuncion))
        f_decl   = parsear_fecha(row.get(col_decl))

        batch.append((uri_dec, uri_decl, tipo, inst, cargo, regimen, f_asun, f_decl))

        if len(batch) >= BATCH_SIZE:
            flush_batch(batch)
            batch = []
            log(f"  Progreso: {insertados:,} insertados...")

    if batch:
        flush_batch(batch)

    log(f"Importacion completada: {insertados:,} declaraciones insertadas, {errores} filas saltadas")

    # Verificar vinculacion con candidatos
    cur.execute("""
        SELECT COUNT(DISTINCT d.uri_declarante)
        FROM declaracion_cplt d
        JOIN candidato c ON c.uri_declarante = d.uri_declarante
    """)
    vinculados = cur.fetchone()[0]
    log(f"Declarantes vinculados a candidatos en DB: {vinculados:,}")

    cur.close()
    conn.close()
    log("Listo.")


if __name__ == "__main__":
    main()
