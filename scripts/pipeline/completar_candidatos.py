"""
completar_candidatos.py - Agrega candidatos faltantes desde dos fuentes:
  1. CPLT (csvdeclaraciones.csv) — 73 politicos nuevos del gobierno actual
  2. diputado_camara — 91 ex-diputados historicos sin fila en candidato

Ejecutar desde la raiz: python scripts/pipeline/completar_candidatos.py
"""

import os
import unicodedata
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

CARGOS_POLITICOS = [
    'ALCALDE','CONCEJAL','DIPUTADO/DA','SENADOR/A','SENADOR','DIPUTADO',
    'MINISTRO','MINISTRA','SUBSECRETARIO','SUBSECRETARIA',
    'GOBERNADOR REGIONAL','GOBERNADORA REGIONAL',
    'SECRETARIO REGIONAL MINISTERIAL','SEREMI',
    'CONSEJERO REGIONAL','CONSEJERA REGIONAL',
    'CANDIDATO A DIPUTADO 2025','CANDIDATO A DIPUTADO 2021',
    'CANDIDATA A DIPUTADA 2025','CANDIDATA A DIPUTADA 2021',
    'CANDIDATO A CONCEJAL 2024','CANDIDATO A CONCEJAL 2021',
    'CANDIDATO A SENADOR 2025','CANDIDATA A SENADORA 2025',
    'CANDIDATO A ALCALDE 2024','CANDIDATA A ALCALDESA 2024',
    'INTENDENTE','DELEGADO PRESIDENCIAL REGIONAL',
    'DELEGADO PRESIDENCIAL PROVINCIAL','JEFE DE GABINETE',
]

# Mapeo de cargos CPLT -> nombre normalizado para tabla cargo
MAPA_CARGO = {
    'DIPUTADO/DA': 'DIPUTADO',
    'SENADOR/A': 'SENADOR',
    'MINISTRA': 'MINISTRO',
    'SUBSECRETARIA': 'SUBSECRETARIO',
    'GOBERNADORA REGIONAL': 'GOBERNADOR REGIONAL',
    'CONSEJERA REGIONAL': 'CONSEJERO REGIONAL',
    'CANDIDATA A DIPUTADA 2025': 'CANDIDATO A DIPUTADO 2025',
    'CANDIDATA A DIPUTADA 2021': 'CANDIDATO A DIPUTADO 2021',
    'CANDIDATA A SENADORA 2025': 'CANDIDATO A SENADOR 2025',
    'CANDIDATA A ALCALDESA 2024': 'CANDIDATO A ALCALDE 2024',
}


def normalizar(texto):
    """Quita tildes, convierte a uppercase y colapsa espacios. Permite comparar
    nombres con encoding roto (DB) contra nombres correctos (CPLT CSV)."""
    if not texto:
        return ""
    txt = unicodedata.normalize("NFD", str(texto).upper())
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    return " ".join(txt.split())


def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "ciudadano_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
        client_encoding="UTF8"
    )


def upsert_cargo(cursor, nombre):
    if not nombre:
        return None
    nombre = MAPA_CARGO.get(nombre.upper(), nombre.upper())
    cursor.execute("SELECT id FROM cargo WHERE nombre = %s", (nombre,))
    r = cursor.fetchone()
    if r:
        return r[0]
    cursor.execute("INSERT INTO cargo (nombre) VALUES (%s) RETURNING id", (nombre,))
    return cursor.fetchone()[0]


def nombres_en_db(cursor):
    cursor.execute("SELECT upper(trim(nombre_limpio)) FROM candidato WHERE nombre_limpio IS NOT NULL")
    s = set(r[0] for r in cursor.fetchall())
    cursor.execute("SELECT upper(trim(nombres)) FROM candidato")
    s2 = set(r[0] for r in cursor.fetchall())
    return s | s2


# ---------------------------------------------------------------------------
# Paso 1: Nuevos desde CPLT
# ---------------------------------------------------------------------------

def agregar_desde_cplt(cursor):
    print("\n[1/3] Cargando politicos nuevos desde csvdeclaraciones.csv...")
    df = pd.read_csv("data/csvdeclaraciones.csv", low_memory=False)
    df_pol = df[df["Cargo"].str.upper().isin([c.upper() for c in CARGOS_POLITICOS])]

    declarantes = df_pol.sort_values("Declaracion", ascending=False).groupby("UriDeclarante").agg(
        nombre=("Nombre", "first"),
        ap_paterno=("ApPaterno", "first"),
        ap_materno=("ApMaterno", "first"),
        cargo=("Cargo", "first"),
        comuna=("ComunaDesempenio", "first"),
        uri_declaracion=("UriDeclaracion", "first"),
        uri_declarante=("UriDeclarante", "first"),
    ).reset_index(drop=True)

    en_db = nombres_en_db(cursor)

    declarantes["nombre_completo"] = (
        declarantes["nombre"] + " " +
        declarantes["ap_paterno"] + " " +
        declarantes["ap_materno"]
    ).str.upper().str.strip()

    faltantes = declarantes[~declarantes["nombre_completo"].isin(en_db)].copy()
    print(f"  -> {len(faltantes)} politicos nuevos para insertar")

    insertados = 0
    for i, row in faltantes.iterrows():
        nombre_limpio = row["nombre_completo"]
        cargo_id = upsert_cargo(cursor, row["cargo"])
        rut_temp = f"CPLT-NEW-{i}"
        cursor.execute("""
            INSERT INTO candidato (rut, nombres, apellidos, cargo_id, comuna, fuente_url, nombre_limpio, uri_declarante)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (rut) DO NOTHING
        """, (
            rut_temp,
            str(row["nombre"]).strip().upper(),
            (str(row["ap_paterno"]).strip() + " " + str(row["ap_materno"]).strip()).strip().upper(),
            cargo_id,
            str(row["comuna"]).strip() if pd.notna(row["comuna"]) else None,
            str(row["uri_declaracion"]).strip(),
            nombre_limpio,
            str(row["uri_declarante"]).strip(),
        ))
        insertados += 1

    print(f"  -> {insertados} candidatos insertados desde CPLT")
    return insertados


# ---------------------------------------------------------------------------
# Paso 2: Actualizar uri_declarante para todos los existentes
# ---------------------------------------------------------------------------

def actualizar_uri_declarante(cursor):
    print("\n[2/3] Actualizando uri_declarante para candidatos existentes...")
    df = pd.read_csv("data/csvdeclaraciones.csv", low_memory=False)
    df_pol = df[df["Cargo"].str.upper().isin([c.upper() for c in CARGOS_POLITICOS])]

    declarantes = df_pol.sort_values("Declaracion", ascending=False).groupby("UriDeclarante").agg(
        nombre=("Nombre", "first"),
        ap_paterno=("ApPaterno", "first"),
        ap_materno=("ApMaterno", "first"),
        uri_declarante=("UriDeclarante", "first"),
        uri_declaracion=("UriDeclaracion", "first"),
    ).reset_index(drop=True)

    declarantes["nombre_norm"] = (
        declarantes["nombre"].fillna("") + " " +
        declarantes["ap_paterno"].fillna("") + " " +
        declarantes["ap_materno"].fillna("")
    ).apply(normalizar)

    # Descartar filas sin nombre valido
    declarantes = declarantes[declarantes["nombre_norm"].str.len() > 3]

    # Cargar candidatos sin uri_declarante desde DB y crear lookup normalizado
    cursor.execute("""
        SELECT id, nombre_limpio
        FROM candidato
        WHERE uri_declarante IS NULL AND nombre_limpio IS NOT NULL
    """)
    sin_uri = cursor.fetchall()
    # { nombre_normalizado: candidato_id }
    db_lookup = {normalizar(nombre): cid for cid, nombre in sin_uri if nombre}

    actualizados = 0
    for _, row in declarantes.iterrows():
        nombre_norm = row["nombre_norm"]
        if not nombre_norm or nombre_norm == "NAN":
            continue
        cid = db_lookup.get(nombre_norm)
        if cid is None:
            continue
        cursor.execute("""
            UPDATE candidato
            SET uri_declarante = %s, fuente_url = COALESCE(fuente_url, %s)
            WHERE id = %s AND uri_declarante IS NULL
        """, (row["uri_declarante"], row["uri_declaracion"], cid))
        if cursor.rowcount:
            actualizados += 1
            # Actualizar lookup para no hacer match doble
            db_lookup.pop(nombre_norm, None)

    print(f"  -> {actualizados} candidatos actualizados con uri_declarante (normalizacion sin tildes)")
    return actualizados


# ---------------------------------------------------------------------------
# Paso 3: Ex-diputados historicos desde diputado_camara
# ---------------------------------------------------------------------------

def agregar_ex_diputados(cursor):
    print("\n[3/3] Agregando ex-diputados historicos sin fila en candidato...")

    cursor.execute("""
        SELECT d.dipid, d.nombre, d.apellido_paterno, d.apellido_materno, d.partido_actual
        FROM diputado_camara d
        WHERE d.candidato_id IS NULL
        ORDER BY d.apellido_paterno
    """)
    sin_match = cursor.fetchall()
    print(f"  -> {len(sin_match)} ex-diputados sin candidato_id")

    en_db = nombres_en_db(cursor)
    cargo_id = upsert_cargo(cursor, "DIPUTADO")

    insertados = 0
    for dipid, nombre, ap_pat, ap_mat, partido in sin_match:
        nombre_completo = f"{nombre} {ap_pat} {ap_mat}".upper().strip()
        if nombre_completo in en_db:
            continue  # ya existe, solo vincular

        rut_temp = f"DIPCAM-{dipid}"
        apellidos = f"{ap_pat or ''} {ap_mat or ''}".strip().upper()

        cursor.execute("""
            INSERT INTO candidato (rut, nombres, apellidos, cargo_id, nombre_limpio)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (rut) DO NOTHING
        """, (rut_temp, nombre.upper() if nombre else "", apellidos, cargo_id, nombre_completo))
        insertados += 1

    # Ahora vincular diputado_camara -> candidato para todos los que se puedan
    cursor.execute("""
        UPDATE diputado_camara d
        SET candidato_id = c.id
        FROM candidato c
        WHERE d.candidato_id IS NULL
          AND upper(c.nombre_limpio) = upper(trim(
              d.nombre || ' ' || d.apellido_paterno || ' ' || d.apellido_materno
          ))
    """)
    vinculados = cursor.rowcount

    print(f"  -> {insertados} ex-diputados insertados en candidato")
    print(f"  -> {vinculados} diputado_camara vinculados a candidato")
    return insertados


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    conn = get_conn()
    cursor = conn.cursor()

    try:
        print("=== COMPLETAR CANDIDATOS ===")

        cursor.execute("SELECT COUNT(*) FROM candidato")
        antes = cursor.fetchone()[0]
        print(f"Candidatos antes: {antes:,}")

        n1 = agregar_desde_cplt(cursor)
        conn.commit()

        n2 = actualizar_uri_declarante(cursor)
        conn.commit()

        n3 = agregar_ex_diputados(cursor)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM candidato")
        despues = cursor.fetchone()[0]
        print(f"\nCandidatos despues: {despues:,} (+{despues - antes})")

        cursor.execute("SELECT COUNT(*) FROM candidato WHERE uri_declarante IS NOT NULL")
        con_uri = cursor.fetchone()[0]
        print(f"Con uri_declarante: {con_uri:,}")

        cursor.execute("SELECT COUNT(*) FROM candidato WHERE rut NOT LIKE 'CPLT-%' AND rut NOT LIKE 'SERVEL-%' AND rut NOT LIKE 'DIPCAM-%'")
        con_rut_real = cursor.fetchone()[0]
        print(f"Con RUT real: {con_rut_real:,}")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
