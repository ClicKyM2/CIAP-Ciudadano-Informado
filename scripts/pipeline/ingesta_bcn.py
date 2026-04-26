"""
ingesta_bcn.py — Proyectos de ley BCN → PostgreSQL

Por cada diputado en diputado_camara:
  1. Resuelve su BCN ID desde data/mapa_dipid_bcn.json (generado una vez via SPARQL bulk)
  2. Consulta facetas-buscador-avanzado para sus mociones
  3. Extrae boletin + titulo + co-autores
  4. Inserta en proyecto_ley y autoria_proyecto

Uso:
  .venv/Scripts/python.exe scripts/pipeline/ingesta_bcn.py
  .venv/Scripts/python.exe scripts/pipeline/ingesta_bcn.py --estado
  .venv/Scripts/python.exe scripts/pipeline/ingesta_bcn.py --descargar-mapa  (regenera mapa DIPID->BCN)
"""

import os
import sys
import json
import time
import argparse
import psycopg2
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.extractores.bcn import obtener_mociones

load_dotenv()

PROGRESO_FILE   = "data/progreso_bcn.json"
MAPA_DIPID_FILE = "data/mapa_dipid_bcn.json"
SPARQL_ENDPOINT = "https://datos.bcn.cl/sparql"


def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "ciudadano_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
        client_encoding="UTF8"
    )


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL = """
CREATE TABLE IF NOT EXISTS proyecto_ley (
    id               SERIAL PRIMARY KEY,
    boletin          VARCHAR(25) UNIQUE NOT NULL,
    titulo           TEXT,
    fecha_ingreso    DATE,
    tipo_iniciativa  VARCHAR(50),
    camara_origen    VARCHAR(50),
    legislatura      VARCHAR(10),
    link             TEXT
);
ALTER TABLE proyecto_ley ADD COLUMN IF NOT EXISTS legislatura VARCHAR(10);
CREATE INDEX IF NOT EXISTS idx_proy_boletin ON proyecto_ley(boletin);

CREATE TABLE IF NOT EXISTS autoria_proyecto (
    id           SERIAL PRIMARY KEY,
    proyecto_id  INTEGER NOT NULL REFERENCES proyecto_ley(id) ON DELETE CASCADE,
    candidato_id INTEGER NOT NULL REFERENCES candidato(id),
    autor_nombre TEXT,
    UNIQUE(proyecto_id, candidato_id)
);
CREATE INDEX IF NOT EXISTS idx_autoria_candidato ON autoria_proyecto(candidato_id);
CREATE INDEX IF NOT EXISTS idx_autoria_proyecto  ON autoria_proyecto(proyecto_id);
"""


def crear_tablas(cur):
    cur.execute(DDL)


# ---------------------------------------------------------------------------
# Cargar diputados de la DB
# ---------------------------------------------------------------------------

def cargar_diputados(cur):
    """Retorna lista de {dipid, candidato_id, nombre}"""
    cur.execute("""
        SELECT d.dipid, d.candidato_id,
               COALESCE(c.nombre_limpio, c.nombres) AS nombre
        FROM diputado_camara d
        JOIN candidato c ON c.id = d.candidato_id
        WHERE d.candidato_id IS NOT NULL
        ORDER BY d.dipid
    """)
    return [
        {"dipid": row[0], "candidato_id": row[1], "nombre": row[2]}
        for row in cur.fetchall()
    ]


# ---------------------------------------------------------------------------
# Progreso
# ---------------------------------------------------------------------------

def cargar_progreso():
    if os.path.exists(PROGRESO_FILE):
        with open(PROGRESO_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"procesados": [], "bcn_ids": {}}


def guardar_progreso(p):
    os.makedirs("data", exist_ok=True)
    with open(PROGRESO_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Insercion
# ---------------------------------------------------------------------------

def upsert_proyecto(cur, mocion):
    boletin = mocion["boletin"]
    link = f"https://www.bcn.cl/laborparlamentaria/index_html?prmBusqueda={boletin}"
    cur.execute("""
        INSERT INTO proyecto_ley
            (boletin, titulo, fecha_ingreso, tipo_iniciativa, camara_origen, legislatura, link)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (boletin) DO UPDATE
            SET titulo        = COALESCE(EXCLUDED.titulo, proyecto_ley.titulo),
                fecha_ingreso = COALESCE(EXCLUDED.fecha_ingreso, proyecto_ley.fecha_ingreso),
                legislatura   = COALESCE(EXCLUDED.legislatura, proyecto_ley.legislatura)
        RETURNING id
    """, (
        boletin,
        mocion.get("titulo"),
        mocion.get("fecha"),
        mocion.get("tipo_iniciativa"),
        mocion.get("camara_origen"),
        mocion.get("legislatura"),
        link,
    ))
    return cur.fetchone()[0]


def insertar_autoria(cur, proyecto_id, candidato_id, nombre):
    cur.execute("""
        INSERT INTO autoria_proyecto (proyecto_id, candidato_id, autor_nombre)
        VALUES (%s, %s, %s)
        ON CONFLICT (proyecto_id, candidato_id) DO NOTHING
    """, (proyecto_id, candidato_id, nombre))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def descargar_mapa_dipid():
    """Descarga el mapa DIPID->BCN_ID via SPARQL bulk y lo guarda en data/mapa_dipid_bcn.json."""
    query = """
PREFIX bcnbio: <http://datos.bcn.cl/ontologies/bcn-biographies#>
SELECT ?persona ?dipid ?nombre WHERE {
  ?persona bcnbio:idCamaraDeDiputados ?dipid .
  ?persona <http://xmlns.com/foaf/0.1/name> ?nombre .
}
"""
    print("  Consultando SPARQL para mapa DIPID->BCN...", flush=True)
    r = requests.get(
        SPARQL_ENDPOINT,
        params={"query": query, "format": "json"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=60,
    )
    r.raise_for_status()
    bindings = r.json()["results"]["bindings"]
    mapa = {}
    for b in bindings:
        dipid  = int(b["dipid"]["value"])
        bcn_id = int(b["persona"]["value"].split("/")[-1])
        nombre = b.get("nombre", {}).get("value", "")
        mapa[str(dipid)] = {"bcn_id": bcn_id, "nombre": nombre}
    os.makedirs("data", exist_ok=True)
    with open(MAPA_DIPID_FILE, "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2)
    print(f"  Guardado: {len(mapa)} entradas en {MAPA_DIPID_FILE}")
    return mapa


def cargar_mapa_dipid():
    if not os.path.exists(MAPA_DIPID_FILE):
        print(f"  Mapa no encontrado — descargando...")
        return descargar_mapa_dipid()
    with open(MAPA_DIPID_FILE, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--estado",          action="store_true")
    parser.add_argument("--descargar-mapa",  action="store_true", help="Regenera mapa DIPID->BCN via SPARQL")
    args = parser.parse_args()

    print("=" * 60)
    print("INGESTA — Proyectos de Ley BCN")
    print("=" * 60)

    if args.descargar_mapa:
        descargar_mapa_dipid()
        return

    conn = get_conn()
    cur  = conn.cursor()
    crear_tablas(cur)
    conn.commit()

    if args.estado:
        cur.execute("SELECT COUNT(*) FROM proyecto_ley")
        n_proy = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM autoria_proyecto")
        n_autor = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT candidato_id) FROM autoria_proyecto")
        n_cands = cur.fetchone()[0]
        print(f"  Proyectos en DB:           {n_proy:,}")
        print(f"  Autorias registradas:      {n_autor:,}")
        print(f"  Diputados con proyectos:   {n_cands:,}")
        cur.close(); conn.close()
        return

    # --- Cargar mapa DIPID -> BCN_ID (local, sin SPARQL por diputado) ---
    mapa_dipid = cargar_mapa_dipid()

    # --- Carga diputados y progreso ---
    diputados  = cargar_diputados(cur)
    progreso   = cargar_progreso()
    procesados = set(str(d) for d in progreso.get("procesados", []))

    print(f"  Mapa DIPID->BCN:           {len(mapa_dipid):,} entradas")
    print(f"  Diputados en DB:           {len(diputados):,}")
    print(f"  Ya procesados:             {len(procesados):,}")
    print(f"  A procesar:                {len(diputados) - len(procesados):,}")
    print()

    total_proyectos = 0
    total_autorias  = 0
    sin_bcn_id      = 0

    for diputado in diputados:
        cid    = str(diputado["candidato_id"])
        dipid  = str(diputado["dipid"])
        nombre = diputado["nombre"]

        if cid in procesados:
            continue

        # Paso 1: resolver BCN ID desde mapa local (sin SPARQL)
        entrada = mapa_dipid.get(dipid)
        if not entrada:
            sin_bcn_id += 1
            procesados.add(cid)
            progreso["procesados"] = list(procesados)
            guardar_progreso(progreso)
            print(f"  {nombre}: sin DIPID en mapa BCN (dipid={dipid})")
            continue
        bcn_id = entrada["bcn_id"]

        # Paso 2: obtener mociones
        mociones = obtener_mociones(bcn_id, verbose=False)

        # Paso 3: insertar
        for mocion in mociones:
            try:
                proyecto_id = upsert_proyecto(cur, mocion)
                insertar_autoria(cur, proyecto_id, int(cid), nombre)
                total_autorias += 1
                total_proyectos += 1
            except Exception as e:
                conn.rollback()
                print(f"    ERROR insertando {mocion['boletin']}: {e}")
                continue

        conn.commit()

        procesados.add(cid)
        progreso["procesados"] = list(procesados)
        guardar_progreso(progreso)

        print(f"  {nombre}: {len(mociones)} mociones")

        time.sleep(1.0)

    # --- Resumen ---
    cur.execute("SELECT COUNT(*) FROM proyecto_ley")
    total_db_proy = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT candidato_id) FROM autoria_proyecto")
    total_db_cands = cur.fetchone()[0]

    print()
    print("=" * 60)
    print("RESUMEN")
    print(f"  Proyectos insertados:      {total_proyectos:,}")
    print(f"  Autorias insertadas:       {total_autorias:,}")
    print(f"  Sin ID BCN:                {sin_bcn_id:,}")
    print(f"  Total proyectos en DB:     {total_db_proy:,}")
    print(f"  Diputados con proyectos:   {total_db_cands:,}")
    print("=" * 60)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
