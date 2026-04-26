"""
ingesta_congreso.py - Extrae y carga datos del Congreso (Camara de Diputados)
Fuente: opendata.congreso.cl
Ejecutar desde la raiz del proyecto: python scripts/pipeline/ingesta_congreso.py

Estrategia de scan: getSesionDetalle no embebe IDs de votaciones.
Se scanea el rango completo de IDs de votacion en paralelo (ThreadPoolExecutor).
Los threads solo hacen fetch HTTP; la insercion a DB es siempre en el hilo principal.
"""

import os
import time
import json
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

API_BASE         = "https://opendata.congreso.cl/wscamaradiputados.asmx"
# Legislaturas a cargar (sesiones disponibles en la API):
#   Legislaturas anteriores (carrera completa) se cargan automaticamente
#   al escanear todos los IDs de sesion que la DB tenga registrados.
LEGISLATURAS     = [50, 51, 52, 53, 54, 55, 56, 57, 58]   # 50-56: 2018-2025 | 57: 2025-2026 | 58: desde mar-2026
WORKERS          = 8      # hilos paralelos de fetch HTTP
BATCH_SIZE       = 200    # IDs por lote antes de insertar y hacer checkpoint
VID_SCAN_DESDE   = 1      # inicio: desde el principio para carrera completa
VID_SCAN_HASTA   = 85000  # extendido para capturar votaciones leg 57/58 completas
CHECKPOINT_FILE  = "data/progreso_congreso.json"
NS = {"ns": "http://tempuri.org/"}


# ---------------------------------------------------------------------------
# Conexion
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


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def leer_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"ultimo_vid_escaneado": VID_SCAN_DESDE}

def guardar_checkpoint(data):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Utilidades XML
# ---------------------------------------------------------------------------

def fetch_xml(endpoint, params=None, reintentos=3):
    """Fetch para llamadas seriales (diputados, sesiones). No usar en threads."""
    url = f"{API_BASE}/{endpoint}"
    for intento in range(reintentos):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return ET.fromstring(r.content)
        except Exception as e:
            if intento < reintentos - 1:
                time.sleep(2)
            else:
                raise


def fetch_votacion(vid, reintentos=2):
    """
    Fetch de una votacion individual. Disenado para ser llamado desde threads.
    Retorna (vid, root) o (vid, None) si no hay datos o falla.
    """
    url = f"{API_BASE}/getVotacion_Detalle"
    for intento in range(reintentos):
        try:
            r = requests.get(url, params={"prmVotacionID": vid}, timeout=20)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            if es_nil(root):
                return vid, None
            return vid, root
        except Exception:
            if intento < reintentos - 1:
                time.sleep(1)
    return vid, None

def txt(el, tag):
    child = el.find(f"ns:{tag}", NS)
    if child is not None and child.text:
        return child.text.strip()
    return None

def es_nil(root):
    return root.get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true"

def extraer_sesion_id(root):
    """Extrae el sesion_id de un XML de getVotacion_Detalle."""
    for xpath in ["ns:Sesion/ns:ID", ".//ns:Sesion/ns:ID", "ns:SesionID", ".//ns:SesionID"]:
        el = root.find(xpath, NS)
        if el is not None and el.text and el.text.strip().lstrip("-").isdigit():
            return int(el.text.strip())
    return None


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL = """
CREATE TABLE IF NOT EXISTS diputado_camara (
    dipid            INTEGER PRIMARY KEY,
    nombre           VARCHAR(150),
    apellido_paterno VARCHAR(100),
    apellido_materno VARCHAR(100),
    fecha_nacimiento DATE,
    sexo             VARCHAR(20),
    partido_actual   VARCHAR(150),
    candidato_id     INTEGER REFERENCES candidato(id)
);

CREATE TABLE IF NOT EXISTS sesion_camara (
    id             INTEGER PRIMARY KEY,
    numero         INTEGER,
    fecha          TIMESTAMP,
    fecha_termino  TIMESTAMP,
    tipo           VARCHAR(60),
    legislatura_id INTEGER
);

CREATE TABLE IF NOT EXISTS votacion_camara (
    id                  INTEGER PRIMARY KEY,
    sesion_id           INTEGER REFERENCES sesion_camara(id),
    boletin             VARCHAR(60),
    fecha               TIMESTAMP,
    tipo                VARCHAR(60),
    resultado           VARCHAR(60),
    quorum              VARCHAR(60),
    total_afirmativos   INTEGER DEFAULT 0,
    total_negativos     INTEGER DEFAULT 0,
    total_abstenciones  INTEGER DEFAULT 0,
    total_dispensados   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS voto_diputado (
    votacion_id INTEGER REFERENCES votacion_camara(id),
    dipid       INTEGER REFERENCES diputado_camara(dipid),
    opcion      VARCHAR(30),
    PRIMARY KEY (votacion_id, dipid)
);

CREATE TABLE IF NOT EXISTS asistencia_sesion (
    dipid     INTEGER REFERENCES diputado_camara(dipid),
    sesion_id INTEGER REFERENCES sesion_camara(id),
    presente  BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (dipid, sesion_id)
);
"""

def crear_tablas(cursor):
    cursor.execute(DDL)
    print("  -> Tablas listas.")


# ---------------------------------------------------------------------------
# Paso 1: Diputados
# ---------------------------------------------------------------------------

def cargar_diputados(cursor):
    print("\n[1/5] Cargando diputados vigentes...")
    root = fetch_xml("getDiputados_Vigentes")

    diputados = []
    for dip in root.findall("ns:Diputado", NS):
        dipid_raw = txt(dip, "DIPID")
        if not dipid_raw:
            continue
        dipid = int(dipid_raw)

        nombre  = txt(dip, "Nombre") or ""
        nombre2 = txt(dip, "Nombre2") or ""
        nombre_completo = f"{nombre} {nombre2}".strip()
        ap_pat  = txt(dip, "Apellido_Paterno") or ""
        ap_mat  = txt(dip, "Apellido_Materno") or ""

        fecha_nac = None
        fecha_nac_raw = txt(dip, "Fecha_Nacimiento")
        if fecha_nac_raw:
            try:
                fecha_nac = datetime.fromisoformat(fecha_nac_raw.split("T")[0]).date()
            except Exception:
                pass

        sexo_el = dip.find("ns:Sexo", NS)
        sexo = sexo_el.text.strip() if sexo_el is not None and sexo_el.text else None

        partido_actual = None
        for mil in dip.findall(".//ns:Militancia", NS):
            estado = txt(mil, "Estado")
            if estado and "activa" in estado.lower():
                partido_actual = txt(mil, "Nombre") or txt(mil, "Partido")
                break

        diputados.append((dipid, nombre_completo, ap_pat, ap_mat, fecha_nac, sexo, partido_actual))

    execute_values(cursor, """
        INSERT INTO diputado_camara
            (dipid, nombre, apellido_paterno, apellido_materno, fecha_nacimiento, sexo, partido_actual)
        VALUES %s
        ON CONFLICT (dipid) DO UPDATE SET
            nombre           = EXCLUDED.nombre,
            apellido_paterno = EXCLUDED.apellido_paterno,
            apellido_materno = EXCLUDED.apellido_materno,
            partido_actual   = EXCLUDED.partido_actual
    """, diputados)
    print(f"  -> {len(diputados)} diputados cargados.")


# ---------------------------------------------------------------------------
# Paso 2: Sesiones
# ---------------------------------------------------------------------------

def cargar_sesiones_de_legislatura(cursor, legislatura_id):
    root = fetch_xml("getSesiones", {"prmLegislaturaID": legislatura_id})
    sesiones = []
    for ses in root.findall("ns:Sesion", NS):
        sid_raw = txt(ses, "ID")
        if not sid_raw:
            continue
        sid = int(sid_raw)
        numero_raw = txt(ses, "Numero")
        numero = int(numero_raw) if numero_raw and numero_raw.lstrip("-").isdigit() else None
        fecha_raw      = txt(ses, "Fecha")
        fecha_term_raw = txt(ses, "FechaTermino")
        fecha      = datetime.fromisoformat(fecha_raw)      if fecha_raw      else None
        fecha_term = datetime.fromisoformat(fecha_term_raw) if fecha_term_raw else None
        tipo_el = ses.find("ns:Tipo", NS)
        tipo = tipo_el.text.strip() if tipo_el is not None and tipo_el.text else None
        sesiones.append((sid, numero, fecha, fecha_term, tipo, legislatura_id))

    execute_values(cursor, """
        INSERT INTO sesion_camara (id, numero, fecha, fecha_termino, tipo, legislatura_id)
        VALUES %s ON CONFLICT (id) DO NOTHING
    """, sesiones)
    return [s[0] for s in sesiones]


def cargar_sesiones(cursor, legislaturas):
    print(f"\n[2/5] Cargando sesiones de legislaturas {legislaturas}...")
    todos_ids = []
    for leg in legislaturas:
        ids = cargar_sesiones_de_legislatura(cursor, leg)
        print(f"  Leg {leg}: {len(ids)} sesiones (IDs {min(ids)}-{max(ids)})")
        todos_ids.extend(ids)
    print(f"  -> Total: {len(todos_ids)} sesiones cargadas.")
    return todos_ids


# ---------------------------------------------------------------------------
# Paso 3: Votaciones — scan secuencial de IDs
# ---------------------------------------------------------------------------

def _insertar_votacion(cursor, root, votacion_id, sesion_id):
    """Inserta una votacion y sus votos individuales. Retorna cantidad de votos."""
    boletin   = txt(root, "Boletin")
    fecha_raw = txt(root, "Fecha")
    fecha     = datetime.fromisoformat(fecha_raw) if fecha_raw else None

    tipo_el   = root.find("ns:Tipo", NS)
    tipo      = tipo_el.text.strip() if tipo_el is not None and tipo_el.text else None
    result_el = root.find("ns:Resultado", NS)
    resultado = result_el.text.strip() if result_el is not None and result_el.text else None
    quorum_el = root.find("ns:Quorum", NS)
    quorum    = quorum_el.text.strip() if quorum_el is not None and quorum_el.text else None

    def safe_int(tag):
        val = txt(root, tag)
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    cursor.execute("""
        INSERT INTO votacion_camara
            (id, sesion_id, boletin, fecha, tipo, resultado, quorum,
             total_afirmativos, total_negativos, total_abstenciones, total_dispensados)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO NOTHING
    """, (
        votacion_id, sesion_id, boletin, fecha, tipo, resultado, quorum,
        safe_int("TotalAfirmativos"), safe_int("TotalNegativos"),
        safe_int("TotalAbstenciones"), safe_int("TotalDispensados")
    ))

    # Recopilar votos y datos minimos de diputados historicos
    votos = []
    dipids_nuevos = {}  # dipid -> (nombre, ap_pat, ap_mat)

    for voto in root.findall(".//ns:Voto", NS):
        dip_el = voto.find("ns:Diputado", NS)
        if dip_el is None:
            continue
        dipid_raw = txt(dip_el, "DIPID")
        if not dipid_raw or not dipid_raw.isdigit():
            continue
        dipid = int(dipid_raw)
        opcion_el = voto.find("ns:Opcion", NS)
        opcion = opcion_el.text.strip() if opcion_el is not None and opcion_el.text else "Desconocido"
        votos.append((votacion_id, dipid, opcion))

        if dipid not in dipids_nuevos:
            nombre  = txt(dip_el, "Nombre") or ""
            nombre2 = txt(dip_el, "Nombre2") or ""
            ap_pat  = txt(dip_el, "Apellido_Paterno") or ""
            ap_mat  = txt(dip_el, "Apellido_Materno") or ""
            dipids_nuevos[dipid] = (f"{nombre} {nombre2}".strip(), ap_pat, ap_mat)

    for pareo in root.findall(".//ns:Pareo", NS):
        for dip_el in pareo.findall(".//ns:Diputado", NS):
            dipid_raw = txt(dip_el, "DIPID")
            if dipid_raw and dipid_raw.isdigit():
                dipid = int(dipid_raw)
                votos.append((votacion_id, dipid, "Pareo"))
                if dipid not in dipids_nuevos:
                    nombre  = txt(dip_el, "Nombre") or ""
                    ap_pat  = txt(dip_el, "Apellido_Paterno") or ""
                    ap_mat  = txt(dip_el, "Apellido_Materno") or ""
                    dipids_nuevos[dipid] = (nombre, ap_pat, ap_mat)

    # Insertar diputados historicos que no existan aun (sin candidato_id)
    if dipids_nuevos:
        execute_values(cursor, """
            INSERT INTO diputado_camara (dipid, nombre, apellido_paterno, apellido_materno)
            VALUES %s ON CONFLICT (dipid) DO NOTHING
        """, [(d, v[0], v[1], v[2]) for d, v in dipids_nuevos.items()])

    if votos:
        execute_values(cursor, """
            INSERT INTO voto_diputado (votacion_id, dipid, opcion)
            VALUES %s ON CONFLICT (votacion_id, dipid) DO NOTHING
        """, votos)

    return len(votos)


def cargar_votaciones(cursor, sesion_ids, checkpoint):
    """
    Escanea IDs de votacion en paralelo usando ThreadPoolExecutor.
    - Los threads solo hacen fetch HTTP (thread-safe).
    - La insercion a DB ocurre en el hilo principal (sin races).
    - Checkpoint cada BATCH_SIZE IDs para reanudar si se interrumpe.
    """
    sesion_ids_set = set(sesion_ids)
    total_rango    = VID_SCAN_HASTA - VID_SCAN_DESDE + 1
    estimado_min   = total_rango / WORKERS / (1 / 0.25) / 60  # aprox

    print(f"\n[3/5] Escaneando votaciones (IDs {VID_SCAN_DESDE}-{VID_SCAN_HASTA}) "
          f"con {WORKERS} hilos para {len(sesion_ids)} sesiones...")
    print(f"  Estimado: ~{estimado_min:.0f} minutos")

    vid_inicio = checkpoint.get("ultimo_vid_escaneado", VID_SCAN_DESDE)
    if vid_inicio > VID_SCAN_HASTA:
        print("  Scan ya completado segun checkpoint.")
        return

    print(f"  Reanudando desde ID {vid_inicio}...")

    total_votaciones = 0
    total_votos      = 0
    ids_pendientes   = list(range(vid_inicio, VID_SCAN_HASTA + 1))

    # Procesar en lotes de BATCH_SIZE para hacer checkpoint periodico
    for lote_inicio in range(0, len(ids_pendientes), BATCH_SIZE):
        lote = ids_pendientes[lote_inicio : lote_inicio + BATCH_SIZE]

        resultados = {}
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futuros = {pool.submit(fetch_votacion, vid): vid for vid in lote}
            for futuro in as_completed(futuros):
                vid, root = futuro.result()
                if root is not None:
                    resultados[vid] = root

        # Insertar en orden para consistencia
        for vid in sorted(resultados.keys()):
            root = resultados[vid]
            sid = extraer_sesion_id(root)
            if sid is not None and sid in sesion_ids_set:
                n = _insertar_votacion(cursor, root, vid, sid)
                total_votos      += n
                total_votaciones += 1

        ultimo_vid = lote[-1]
        cursor.connection.commit()
        checkpoint["ultimo_vid_escaneado"] = ultimo_vid
        guardar_checkpoint(checkpoint)

        pct = (ultimo_vid - VID_SCAN_DESDE) / (VID_SCAN_HASTA - VID_SCAN_DESDE) * 100
        print(f"  ID={ultimo_vid} ({pct:.1f}%) — "
              f"{total_votaciones} votaciones, {total_votos} votos acumulados")

    checkpoint["ultimo_vid_escaneado"] = VID_SCAN_HASTA + 1
    guardar_checkpoint(checkpoint)
    print(f"  -> {total_votaciones} votaciones, {total_votos} votos individuales cargados.")


# ---------------------------------------------------------------------------
# Paso 4: Calcular asistencia
# ---------------------------------------------------------------------------

def calcular_asistencia(cursor):
    print("\n[4/5] Calculando asistencia por sesion...")

    # Limpiar tabla antes de recalcular
    cursor.execute("TRUNCATE TABLE asistencia_sesion")

    # Presentes: aparecen en al menos 1 voto de la sesion
    cursor.execute("""
        INSERT INTO asistencia_sesion (dipid, sesion_id, presente)
        SELECT DISTINCT vd.dipid, vc.sesion_id, TRUE
        FROM voto_diputado vd
        JOIN votacion_camara vc ON vc.id = vd.votacion_id
        ON CONFLICT (dipid, sesion_id) DO NOTHING
    """)

    # Ausentes: diputados en la DB sin ningun voto en la sesion
    cursor.execute("""
        INSERT INTO asistencia_sesion (dipid, sesion_id, presente)
        SELECT d.dipid, s.id, FALSE
        FROM diputado_camara d
        CROSS JOIN sesion_camara s
        WHERE NOT EXISTS (
            SELECT 1 FROM asistencia_sesion a
            WHERE a.dipid = d.dipid AND a.sesion_id = s.id
        )
        ON CONFLICT (dipid, sesion_id) DO NOTHING
    """)

    cursor.execute("SELECT COUNT(*) FROM asistencia_sesion WHERE presente = TRUE")
    presentes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM asistencia_sesion WHERE presente = FALSE")
    ausentes = cursor.fetchone()[0]
    print(f"  -> {presentes:,} presencias, {ausentes:,} inasistencias registradas.")


# ---------------------------------------------------------------------------
# Paso 5: Cruzar diputados con tabla candidato
# ---------------------------------------------------------------------------

def cruzar_con_candidatos(cursor):
    print("\n[5/5] Cruzando diputados con tabla candidato por nombre...")

    cursor.execute("""
        UPDATE diputado_camara d
        SET candidato_id = c.id
        FROM candidato c
        WHERE d.candidato_id IS NULL
          AND upper(trim(c.nombre_limpio)) = upper(trim(
              d.nombre || ' ' || d.apellido_paterno || ' ' || d.apellido_materno
          ))
    """)

    cursor.execute("""
        UPDATE diputado_camara d
        SET candidato_id = c.id
        FROM candidato c
        WHERE d.candidato_id IS NULL
          AND upper(c.nombre_limpio) LIKE upper('%' || d.apellido_paterno || '%')
          AND upper(c.nombre_limpio) LIKE upper('%' || d.apellido_materno || '%')
          AND length(d.apellido_paterno) > 3
          AND length(d.apellido_materno) > 3
    """)

    cursor.execute("SELECT COUNT(*) FROM diputado_camara WHERE candidato_id IS NOT NULL")
    matched = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM diputado_camara")
    total = cursor.fetchone()[0]
    print(f"  -> {matched}/{total} diputados vinculados a un candidato existente.")

    if matched < total:
        cursor.execute("""
            SELECT dipid, apellido_paterno, apellido_materno, nombre
            FROM diputado_camara WHERE candidato_id IS NULL
            ORDER BY apellido_paterno
        """)
        sin_match = cursor.fetchall()
        print(f"  Sin match en candidato ({len(sin_match)}):")
        for row in sin_match[:20]:
            print(f"    DIPID={row[0]}  {row[1]} {row[2]} / {row[3]}")
        if len(sin_match) > 20:
            print(f"    ... y {len(sin_match)-20} mas.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    conn       = get_conn()
    cursor     = conn.cursor()
    checkpoint = leer_checkpoint()

    try:
        print("=== INGESTA CONGRESO - CAMARA DE DIPUTADOS ===")
        print(f"Legislaturas objetivo: {LEGISLATURAS}")

        print("\n[0/5] Creando tablas si no existen...")
        crear_tablas(cursor)
        conn.commit()

        cargar_diputados(cursor)
        conn.commit()

        sesion_ids = cargar_sesiones(cursor, LEGISLATURAS)
        conn.commit()

        cargar_votaciones(cursor, sesion_ids, checkpoint)

        calcular_asistencia(cursor)
        conn.commit()

        cruzar_con_candidatos(cursor)
        conn.commit()

        print("\n=== COMPLETADO ===")
        for tabla in ["diputado_camara", "sesion_camara", "votacion_camara", "voto_diputado", "asistencia_sesion"]:
            cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
            print(f"  {tabla}: {cursor.fetchone()[0]:,} filas")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR FATAL: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
