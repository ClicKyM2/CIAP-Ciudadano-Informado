"""
calcular_scores.py
Calcula score_transparencia para cada candidato en ciudadano_db.

Formula (base 0, max 100, min 0):
  +25  declaracion CPLT presentada hace <= 12 meses
  +20  tiene empresas en participacion_societaria
  +20  aparece como sujeto pasivo en match_candidato_lobby
  +15  sin alertas de gravedad ALTA
  -20  por cada tipo de alerta ALTA (una sola vez)
  -10  por cada tipo de alerta MEDIA (una sola vez)
  -15  declaracion CPLT con mas de 12 meses de antiguedad

Score final: CLAMP(suma, 0, 100)

Requiere:
  - columna score_transparencia en tabla candidato (se crea si no existe)
  - data/csvdeclaraciones.csv con columnas UriDeclarante, Declaracion
  - variables de entorno DB_* (o defaults de localhost)
"""

import os
import csv
from datetime import date, datetime, timedelta

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "dbname":   os.getenv("DB_NAME", "ciudadano_db"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port":     os.getenv("DB_PORT", "5432"),
}

CSV_DECLARACIONES = os.path.join("data", "csvdeclaraciones.csv")
HOY = date.today()
UMBRAL_RECIENTE = HOY - timedelta(days=365)


def cargar_fechas_declaracion():
    """
    Lee csvdeclaraciones.csv y devuelve un dict:
      { uri_declarante: fecha_declaracion_mas_reciente (date) }
    Usa UriDeclarante y columna Declaracion.
    """
    fechas = {}
    print(f"Leyendo {CSV_DECLARACIONES}...")
    with open(CSV_DECLARACIONES, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uri = (row.get("UriDeclarante") or "").strip()
            fecha_str = (row.get("Declaracion") or "").strip()
            if not uri or not fecha_str:
                continue
            try:
                fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            if uri not in fechas or fecha > fechas[uri]:
                fechas[uri] = fecha
    print(f"  {len(fechas)} declarantes con fecha de declaracion.")
    return fechas


def crear_columna_si_no_existe(cur):
    cur.execute("""
        ALTER TABLE candidato
        ADD COLUMN IF NOT EXISTS score_transparencia INTEGER DEFAULT 0;
    """)


def calcular_y_actualizar(conn, cur, fechas_declaracion):
    # --- Cargar candidatos con uri_declarante ---
    cur.execute("""
        SELECT id, rut, uri_declarante
        FROM candidato
        WHERE rut NOT LIKE 'CPLT-%%' AND rut NOT LIKE 'SERVEL-%%'
    """)
    candidatos = cur.fetchall()
    print(f"Calculando scores para {len(candidatos)} candidatos con RUT real...")

    # --- Pre-calcular sets de IDs con datos en cada tabla ---
    cur.execute("SELECT DISTINCT candidato_id FROM participacion_societaria")
    ids_con_empresas = {r[0] for r in cur.fetchall()}

    cur.execute("SELECT DISTINCT c.id FROM candidato c JOIN match_candidato_lobby m ON m.rut = c.rut")
    ids_con_lobby = {r[0] for r in cur.fetchall()}

    # alertas por candidato: { candidato_id: {'ALTA': n, 'MEDIA': n} }
    cur.execute("""
        SELECT candidato_id, gravedad, COUNT(*)
        FROM alerta_probidad
        GROUP BY candidato_id, gravedad
    """)
    alertas = {}
    for cid, gravedad, cnt in cur.fetchall():
        alertas.setdefault(cid, {})
        alertas[cid][gravedad] = cnt

    # --- Calcular score por candidato y acumular updates ---
    updates = []  # (score, candidato_id)

    for cid, rut, uri_declarante in candidatos:
        score = 0

        # Fecha de declaracion CPLT
        fecha_decl = fechas_declaracion.get(uri_declarante or "")
        if fecha_decl:
            if fecha_decl >= UMBRAL_RECIENTE:
                score += 25   # declaracion reciente
            else:
                score -= 15   # declaracion antigua

        # Tiene empresas declaradas
        if cid in ids_con_empresas:
            score += 20

        # Aparece como sujeto pasivo en lobby
        if cid in ids_con_lobby:
            score += 20

        # Alertas
        alertas_cid = alertas.get(cid, {})
        n_alta  = alertas_cid.get("ALTA", 0)
        n_media = alertas_cid.get("MEDIA", 0)

        if n_alta == 0 and n_media == 0:
            score += 15   # sin alertas
        else:
            if n_alta > 0:
                score -= 20
            if n_media > 0:
                score -= 10

        # Clamp
        score = max(0, min(100, score))
        updates.append((score, cid))

    # --- Batch UPDATE ---
    cur.executemany(
        "UPDATE candidato SET score_transparencia = %s WHERE id = %s",
        updates,
    )
    conn.commit()
    print(f"  {len(updates)} candidatos actualizados.")

    # Resumen de distribucion
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE score_transparencia >= 75) AS verde,
            COUNT(*) FILTER (WHERE score_transparencia BETWEEN 50 AND 74) AS amarillo,
            COUNT(*) FILTER (WHERE score_transparencia < 50)  AS rojo
        FROM candidato
        WHERE rut NOT LIKE 'CPLT-%%' AND rut NOT LIKE 'SERVEL-%%'
    """)
    verde, amarillo, rojo = cur.fetchone()
    print(f"\nDistribucion de scores:")
    print(f"  Verde  (>=75): {verde}")
    print(f"  Amarillo (50-74): {amarillo}")
    print(f"  Rojo   (<50):  {rojo}")


def main():
    fechas_declaracion = cargar_fechas_declaracion()

    print("Conectando a PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("Verificando columna score_transparencia...")
    crear_columna_si_no_existe(cur)
    conn.commit()

    calcular_y_actualizar(conn, cur, fechas_declaracion)

    cur.close()
    conn.close()
    print("\nListo.")


if __name__ == "__main__":
    main()
