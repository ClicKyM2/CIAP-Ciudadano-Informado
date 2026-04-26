"""
ingesta_licitaciones.py — Pipeline: Licitaciones adjudicadas a empresas de candidatos CIAP
Descarga via API OCDS publica (sin ticket), filtra por RUTs de participacion_societaria.

Uso directo: .venv/Scripts/python.exe scripts/pipeline/ingesta_licitaciones.py
Via pipeline:  .venv/Scripts/python.exe pipeline_maestro.py --pasos licitaciones
Flags:
  --desde-anio YYYY    Anio de inicio (default: 2020)
  --estado             Solo muestra conteo en DB, no ejecuta
"""

import os
import sys
import json
import argparse
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.extractores.mercado_publico_licitaciones import (
    descargar_y_filtrar, meses_disponibles, normalizar_rut
)

load_dotenv()

PROGRESO_FILE = "data/progreso_licitaciones.json"
BATCH_SIZE = 200


# ---------------------------------------------------------------------------
# DB
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


def crear_tabla(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS licitacion (
            id SERIAL PRIMARY KEY,
            codigo VARCHAR(50),
            nombre TEXT,
            estado VARCHAR(50),
            fecha_publicacion DATE,
            fecha_cierre DATE,
            fecha_adjudicacion DATE,
            monto_estimado BIGINT,
            monto_adjudicado BIGINT,
            rut_organismo VARCHAR(15),
            nombre_organismo TEXT,
            rut_adjudicatario VARCHAR(15),
            nombre_adjudicatario TEXT,
            link TEXT,
            anio SMALLINT,
            mes SMALLINT,
            candidato_id INTEGER REFERENCES candidato(id),
            UNIQUE(codigo, rut_adjudicatario)
        );
        CREATE INDEX IF NOT EXISTS idx_lic_candidato ON licitacion(candidato_id);
        CREATE INDEX IF NOT EXISTS idx_lic_rut_adj ON licitacion(rut_adjudicatario);
        CREATE INDEX IF NOT EXISTS idx_lic_fecha ON licitacion(fecha_adjudicacion);
    """)


def cargar_ruts_candidatos(cur):
    """Carga dict {rut_normalizado: candidato_id} desde participacion_societaria."""
    cur.execute("""
        SELECT DISTINCT empresa_rut, candidato_id
        FROM participacion_societaria
        WHERE empresa_rut IS NOT NULL AND empresa_rut != ''
    """)
    ruts = {}
    for empresa_rut, candidato_id in cur.fetchall():
        rut_norm = normalizar_rut(empresa_rut)
        if rut_norm:
            ruts[rut_norm] = candidato_id
    return ruts


def insertar_batch(cur, batch):
    if not batch:
        return 0
    cols = [
        'codigo', 'nombre', 'estado', 'fecha_publicacion', 'fecha_cierre',
        'fecha_adjudicacion', 'monto_estimado', 'monto_adjudicado',
        'rut_organismo', 'nombre_organismo', 'rut_adjudicatario',
        'nombre_adjudicatario', 'link', 'anio', 'mes', 'candidato_id'
    ]
    valores = [tuple(fila.get(c) for c in cols) for fila in batch]
    execute_values(cur, f"""
        INSERT INTO licitacion ({', '.join(cols)})
        VALUES %s
        ON CONFLICT (codigo, rut_adjudicatario) DO NOTHING
    """, valores)
    return len(valores)


# ---------------------------------------------------------------------------
# Progreso
# ---------------------------------------------------------------------------

def cargar_progreso():
    if os.path.exists(PROGRESO_FILE):
        with open(PROGRESO_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {"meses_completados": []}


def guardar_progreso(progreso):
    os.makedirs("data", exist_ok=True)
    with open(PROGRESO_FILE, 'w', encoding='utf-8') as f:
        json.dump(progreso, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--desde-anio', type=int, default=2020)
    parser.add_argument('--estado', action='store_true')
    args = parser.parse_args()

    print("=" * 60)
    print("INGESTA — Licitaciones Mercado Publico (OCDS)")
    print("=" * 60)

    conn = get_conn()
    cur = conn.cursor()
    crear_tabla(cur)
    conn.commit()

    if args.estado:
        cur.execute("SELECT COUNT(*), COALESCE(SUM(monto_adjudicado), 0) FROM licitacion")
        total, monto = cur.fetchone()
        cur.execute("SELECT COUNT(DISTINCT candidato_id) FROM licitacion")
        candidatos = cur.fetchone()[0]
        print(f"  Licitaciones en DB:        {total:,}")
        print(f"  Monto total adjudicado:    ${monto:,.0f} CLP")
        print(f"  Candidatos con licitacion: {candidatos:,}")
        cur.close(); conn.close()
        return

    ruts_candidatos = cargar_ruts_candidatos(cur)
    print(f"  RUTs de empresas a buscar: {len(ruts_candidatos):,}")

    if not ruts_candidatos:
        print("  ADVERTENCIA: No hay participaciones societarias en DB.")
        print("  Ejecutar primero: .venv/Scripts/python.exe pipeline_maestro.py --pasos participaciones")
        cur.close(); conn.close()
        return

    progreso = cargar_progreso()
    completados = set(progreso.get("meses_completados", []))

    todos = meses_disponibles(args.desde_anio)
    pendientes = [(a, m) for a, m in todos if f"{a}-{m:02d}" not in completados]

    print(f"  Meses totales: {len(todos)}")
    print(f"  Ya completados: {len(completados)}")
    print(f"  A procesar: {len(pendientes)}")
    print()

    total_insertadas = 0

    for anio, mes in pendientes:
        clave = f"{anio}-{mes:02d}"
        print(f"Procesando {clave}...")

        batch = []
        mes_insertadas = 0

        try:
            for fila in descargar_y_filtrar(anio, mes, ruts_candidatos, verbose=True):
                batch.append(fila)
                if len(batch) >= BATCH_SIZE:
                    mes_insertadas += insertar_batch(cur, batch)
                    conn.commit()
                    batch = []

            if batch:
                mes_insertadas += insertar_batch(cur, batch)
                conn.commit()

            total_insertadas += mes_insertadas
            print(f"  Insertadas: {mes_insertadas} licitaciones relevantes")

            completados.add(clave)
            progreso["meses_completados"] = sorted(completados)
            guardar_progreso(progreso)

        except PermissionError as e:
            print(f"\n  {e}")
            print("  Solicitar ticket gratuito en: https://api.mercadopublico.cl/")
            cur.close(); conn.close()
            return
        except Exception as e:
            print(f"  ERROR en {clave}: {e}")
            conn.rollback()

    cur.execute("SELECT COUNT(*), COALESCE(SUM(monto_adjudicado), 0) FROM licitacion")
    total_db, monto_total = cur.fetchone()

    print()
    print("=" * 60)
    print("RESUMEN")
    print(f"  Licitaciones en DB:          {total_db:,}")
    print(f"  Monto total adjudicado:      ${monto_total:,.0f} CLP")
    print(f"  Insertadas esta ejecucion:   {total_insertadas:,}")
    print("=" * 60)

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
