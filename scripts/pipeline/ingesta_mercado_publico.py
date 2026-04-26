"""
ingesta_mercado_publico.py — Pipeline: Órdenes de Compra de Mercado Público
Descarga ZIPs mensuales desde Azure Blob Storage (público, sin ticket),
filtra solo OCs de empresas vinculadas a candidatos CIAP, y las carga a PostgreSQL.

Uso directo: python scripts/pipeline/ingesta_mercado_publico.py
Via pipeline:  python pipeline_maestro.py --pasos mercado_publico
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Ajustar path para importar desde extractores/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.extractores.mercado_publico_oc import (
    descargar_y_filtrar, meses_disponibles, normalizar_rut, url_disponible
)

load_dotenv()

PROGRESO_FILE = "data/progreso_mercado_publico.json"
AÑO_INICIO = 2022
BATCH_SIZE = 500


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
        CREATE TABLE IF NOT EXISTS orden_compra (
            id SERIAL PRIMARY KEY,
            codigo VARCHAR(50),
            nombre TEXT,
            estado VARCHAR(100),
            fecha_creacion DATE,
            monto_pesos BIGINT,
            rut_organismo VARCHAR(15),
            nombre_organismo TEXT,
            rut_proveedor VARCHAR(15),
            nombre_proveedor TEXT,
            codigo_licitacion VARCHAR(50),
            link TEXT,
            anio SMALLINT,
            mes SMALLINT,
            candidato_id INTEGER REFERENCES candidato(id),
            UNIQUE(codigo, anio, mes)
        );
        CREATE INDEX IF NOT EXISTS idx_oc_candidato ON orden_compra(candidato_id);
        CREATE INDEX IF NOT EXISTS idx_oc_rut_proveedor ON orden_compra(rut_proveedor);
        CREATE INDEX IF NOT EXISTS idx_oc_fecha ON orden_compra(fecha_creacion);
    """)


def cargar_ruts_candidatos(cur):
    """Carga dict {rut_normalizado: candidato_id} desde participacion_societaria."""
    cur.execute("""
        SELECT DISTINCT empresa_rut, candidato_id
        FROM participacion_societaria
        WHERE empresa_rut IS NOT NULL AND empresa_rut != ''
    """)
    rows = cur.fetchall()
    ruts = {}
    for empresa_rut, candidato_id in rows:
        rut_norm = normalizar_rut(empresa_rut)
        if rut_norm:
            ruts[rut_norm] = candidato_id
    return ruts


def insertar_batch(cur, batch):
    if not batch:
        return 0
    cols = ['codigo', 'nombre', 'estado', 'fecha_creacion', 'monto_pesos',
            'rut_organismo', 'nombre_organismo', 'rut_proveedor', 'nombre_proveedor',
            'codigo_licitacion', 'link', 'anio', 'mes', 'candidato_id']
    valores = [tuple(fila.get(c) for c in cols) for fila in batch]
    execute_values(cur, f"""
        INSERT INTO orden_compra ({', '.join(cols)})
        VALUES %s
        ON CONFLICT (codigo, anio, mes) DO NOTHING
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
    print("=" * 60)
    print("INGESTA — Órdenes de Compra Mercado Público")
    print("=" * 60)

    conn = get_conn()
    cur = conn.cursor()

    # Crear tabla si no existe
    crear_tabla(cur)
    conn.commit()

    # Cargar RUTs de empresas de candidatos
    ruts_candidatos = cargar_ruts_candidatos(cur)
    print(f"  RUTs de empresas a buscar: {len(ruts_candidatos):,}")

    if not ruts_candidatos:
        print("  ADVERTENCIA: No hay participaciones societarias en DB.")
        print("  Ejecutar primero: python pipeline_maestro.py --pasos participaciones")
        cur.close(); conn.close()
        return

    # Cargar progreso
    progreso = cargar_progreso()
    completados = set(progreso.get("meses_completados", []))

    # Determinar meses a procesar
    todos = meses_disponibles(AÑO_INICIO)
    pendientes = [(a, m) for a, m in todos if f"{a}-{m}" not in completados]

    print(f"  Meses totales: {len(todos)}")
    print(f"  Ya completados: {len(completados)}")
    print(f"  A procesar: {len(pendientes)}")
    print()

    total_insertadas = 0

    for anio, mes in pendientes:
        clave = f"{anio}-{mes}"
        print(f"Procesando {clave}...")

        # Verificar disponibilidad antes de intentar descargar
        if not url_disponible(anio, mes):
            print(f"  No disponible en blob — omitiendo")
            completados.add(clave)
            progreso["meses_completados"] = sorted(completados)
            guardar_progreso(progreso)
            continue

        batch = []
        mes_insertadas = 0

        try:
            for fila in descargar_y_filtrar(anio, mes, ruts_candidatos, verbose=True):
                batch.append(fila)
                if len(batch) >= BATCH_SIZE:
                    mes_insertadas += insertar_batch(cur, batch)
                    conn.commit()
                    batch = []

            # Insertar resto
            if batch:
                mes_insertadas += insertar_batch(cur, batch)
                conn.commit()

            total_insertadas += mes_insertadas
            print(f"  Insertadas: {mes_insertadas} OCs relevantes")

            completados.add(clave)
            progreso["meses_completados"] = sorted(completados)
            guardar_progreso(progreso)

        except Exception as e:
            print(f"  ERROR en {clave}: {e}")
            conn.rollback()

    # Resumen
    cur.execute("SELECT COUNT(*), COALESCE(SUM(monto_pesos), 0) FROM orden_compra")
    total_db, monto_total = cur.fetchone()

    print()
    print("=" * 60)
    print(f"RESUMEN")
    print(f"  OCs en DB: {total_db:,}")
    print(f"  Monto total: ${monto_total:,.0f} CLP")
    print(f"  Insertadas esta ejecución: {total_insertadas:,}")
    print("=" * 60)

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
