"""
pipeline_maestro.py — Orquestador incremental e inteligente del proyecto CIAP
Ejecutar desde la raiz: python pipeline_maestro.py [opciones]

ORDEN DE EJECUCION (automatico, solo corre lo que falta):

  FASE 1 — LIMPIEZA DE ARCHIVOS FUENTE (CSV)
    1a. limpiar_audiencias  — audiencias.csv UTF-16 -> audiencia_final.csv UTF-8
    1b. limpiar_asistencias — asistenciasPasivos.csv -> asistencias_limpio.csv
    1c. arreglar_columnas   — pasivos_limpio.csv -> pasivos_final.csv (10 cols)
    (Excel Servel se lee directamente en el paso 'ingesta')

  FASE 2 — INGESTA A POSTGRESQL
    2a. ingesta            — servel_autoridades.csv + Excel -> tabla candidato
    2b. representaciones   — representaciones.csv -> temp_representaciones
    2c. lobby              — audiencias, asistencias pasivos, match candidato-lobby
    2d. congreso           — API Congreso -> votaciones, asistencia (incremental)
    2e. declaraciones      — csvdeclaraciones.csv -> tabla declaracion_cplt

  FASE 3 — ENRIQUECIMIENTO DE CANDIDATOS
    3a. consolidador       — Consolida funcionarios rescatados con RUT
    3b. cruce_infoprobidad — Asigna uri_declarante a candidatos via CPLT CSV
    3c. completar          — Agrega politicos faltantes (gobierno, ex-diputados)
    3d. ruts               — Extrae RUTs reales desde InfoProbidad (cloudscraper)
    3e. participaciones    — Empresas declaradas CPLT -> participacion_societaria

  FASE 4 — ANALISIS E IA
    4a. enriquecimiento       — Enriquece empresas SII + detecta directores CMF
    4b. mercado_publico       — OC donde empresas de candidatos son proveedores
    4c. financiamiento_servel — Ingresos, gastos, donantes electorales 2024 SERVEL
    4d. ia                    — Detecta conflictos de interes (AUTOLOBBY, FAMILIAR)
    4e. scores                — Calcula score_transparencia por candidato

Opciones:
  --estado            Muestra diagnostico completo sin ejecutar nada
  --lista             Lista los IDs de todos los pasos disponibles
  --solo   PASO       Corre solo ese paso (siempre forzado)
  --pasos  P1,P2,...  Corre una lista especifica de pasos en orden (siempre forzado)
  --desde  PASO       Corre desde ese paso en adelante
  --forzar PASO       Re-corre ese paso y todos los siguientes aunque esten al dia
"""

import os, sys, json, time, subprocess, argparse, psycopg2, shutil
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

LOBBY_DIR  = os.getenv("LOBBY_DIR",  r"C:\Users\Public")
PG_DUMP    = os.getenv("PG_DUMP",    r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe")

LOG_FILE = "data/log_maestro.txt"
_log_file = None


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------

def log(msg=""):
    ts = datetime.now().strftime("%H:%M:%S")
    linea = f"[{ts}] {msg}"
    print(linea)
    if _log_file:
        _log_file.write(linea + "\n")
        _log_file.flush()

def sep(c="-", n=60):
    log(c * n)


# ---------------------------------------------------------------------------
# DB helpers
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

def tabla_existe(cur, nombre):
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name=%s", (nombre,))
    return cur.fetchone() is not None

def columna_existe(cur, tabla, col):
    cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s", (tabla, col))
    return cur.fetchone() is not None

def count(cur, tabla, where=""):
    try:
        cur.execute(f"SELECT COUNT(*) FROM {tabla} {where}")
        return cur.fetchone()[0]
    except Exception:
        return 0

def archivo_existe_y_tiene_datos(ruta, min_bytes=1000):
    return os.path.exists(ruta) and os.path.getsize(ruta) > min_bytes

def contar_filas_csv(ruta):
    """Cuenta filas de un CSV sin cargarlo en memoria (no cuenta el header)."""
    if not os.path.exists(ruta):
        return 0
    with open(ruta, encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f) - 1


def hacer_backup():
    """Crea backup timestamped de CSVs clave + pg_dump de la DB.
    Carpeta: data/backups/YYYY-MM-DD_HHMM/
    """
    ts      = datetime.now().strftime("%Y-%m-%d_%H%M")
    carpeta = os.path.join("data", "backups", ts)
    os.makedirs(carpeta, exist_ok=True)
    log(f"Backup en: {carpeta}")

    csvs_clave = [
        "data/csvdeclaraciones.csv",
        "data/MAESTRO_RUTS_CONSOLIDADOS.csv",
        "data/candidatos_final_limpio.csv",
    ]
    for ruta in csvs_clave:
        if os.path.exists(ruta):
            shutil.copy2(ruta, carpeta)
            log(f"  copiado: {os.path.basename(ruta)}")

    if os.path.exists(PG_DUMP):
        dump_file = os.path.join(carpeta, "ciudadano_db.dump")
        env = os.environ.copy()
        env["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")
        log("  pg_dump en curso...")
        resultado = subprocess.run(
            [PG_DUMP,
             "-h", os.getenv("DB_HOST", "localhost"),
             "-U", os.getenv("DB_USER", "postgres"),
             "-d", os.getenv("DB_NAME", "ciudadano_db"),
             "-F", "c",
             "-f", dump_file],
            env=env, capture_output=True, text=True
        )
        if resultado.returncode == 0:
            mb = os.path.getsize(dump_file) / 1_048_576
            log(f"  pg_dump OK ({mb:.1f} MB)")
        else:
            log(f"  pg_dump FALLO: {resultado.stderr.strip()[:200]}")
    else:
        log(f"  pg_dump omitido (no encontrado en {PG_DUMP})")
        log(f"  Configura PG_DUMP=<ruta> en .env para activarlo")

    log(f"Backup completado: {carpeta}")


def checkpoint_congreso():
    if os.path.exists("data/progreso_congreso.json"):
        with open("data/progreso_congreso.json") as f:
            return json.load(f).get("ultimo_vid_escaneado", 0)
    return 0


# ---------------------------------------------------------------------------
# Definicion de pasos
# ---------------------------------------------------------------------------
#
# Cada paso tiene:
#   script   — ruta al script Python
#   detectar — funcion(cur) -> (necesita: bool, estado: str, razon: str)
#

def detectar_limpiar_audiencias(cur):
    ok = archivo_existe_y_tiene_datos(os.path.join(LOBBY_DIR, "audiencia_final.csv"))
    return (not ok, "audiencia_final.csv existe" if ok else "No existe audiencia_final.csv",
            "Limpiar audiencias.csv UTF-16 -> UTF-8")

def detectar_limpiar_asistencias(cur):
    ok = archivo_existe_y_tiene_datos(os.path.join(LOBBY_DIR, "asistencias_limpio.csv"))
    return (not ok, "asistencias_limpio.csv existe" if ok else "No existe asistencias_limpio.csv",
            "Limpiar asistenciasPasivos.csv UTF-16 -> UTF-8")

def detectar_arreglar_columnas(cur):
    ok = archivo_existe_y_tiene_datos(os.path.join(LOBBY_DIR, "pasivos_final.csv"))
    return (not ok, "pasivos_final.csv existe" if ok else "No existe pasivos_final.csv",
            "Arreglar columnas de pasivos_limpio.csv")

def detectar_ingesta(cur):
    n = count(cur, "candidato")
    return (n < 100, f"{n:,} candidatos en DB",
            "Menos de 100 — re-correr ingesta desde Excel Servel")

def detectar_representaciones(cur):
    n = count(cur, "temp_representaciones") if tabla_existe(cur, "temp_representaciones") else 0
    ok = n >= 1000000
    return (not ok, f"{n:,} representaciones", "Menos de 1M — importar representaciones.csv")

def detectar_congreso(cur):
    n_vot = count(cur, "votacion_camara") if tabla_existe(cur, "votacion_camara") else 0
    vid = checkpoint_congreso()
    # VIDs leg 57/58 estan en rango 80000-85000; umbral minimo 85000
    ok = n_vot > 1000 and vid >= 85000
    return (not ok, f"{n_vot:,} votaciones, scan hasta VID {vid}",
            "Scan incompleto — subir VID_SCAN_HASTA en ingesta_congreso.py")

def detectar_declaraciones(cur):
    n_db  = count(cur, "declaracion_cplt") if tabla_existe(cur, "declaracion_cplt") else 0
    n_csv = contar_filas_csv("data/csvdeclaraciones.csv")
    # Re-importar si el CSV tiene al menos 1% mas filas que la DB (CSV actualizado)
    ok = n_csv > 0 and n_db >= int(n_csv * 0.99)
    return (not ok,
            f"{n_db:,} en DB  /  {n_csv:,} en CSV",
            "El CSV tiene mas declaraciones que la DB — re-importar")

def detectar_consolidador(cur):
    # Solo necesita correr si existen archivos de funcionarios rescatados pendientes
    archivos = [
        "data/funcionarios_rescatados.csv",
        "data/funcionarios_rescatados_bots.csv",
    ]
    tiene_pendientes = any(archivo_existe_y_tiene_datos(a) for a in archivos)
    n_maestro = os.path.exists("data/MAESTRO_RUTS_CONSOLIDADOS.csv")
    return (tiene_pendientes and not n_maestro,
            "MAESTRO_RUTS_CONSOLIDADOS.csv existe" if n_maestro else "Archivos rescatados pendientes de consolidar",
            "Consolidar funcionarios rescatados en maestro")

def detectar_cruce_infoprobidad(cur):
    n_sin_uri = count(cur, "candidato", "WHERE uri_declarante IS NULL")
    n_total   = count(cur, "candidato")
    ok = n_sin_uri < (n_total * 0.10)  # menos del 10% sin uri es aceptable
    return (not ok, f"{n_sin_uri:,} de {n_total:,} candidatos sin uri_declarante",
            "Muchos candidatos sin uri_declarante — cruzar con CPLT CSV")

def detectar_completar(cur):
    n_dipcam = count(cur, "diputado_camara", "WHERE candidato_id IS NULL") if tabla_existe(cur, "diputado_camara") else 0
    n_sin_uri = count(cur, "candidato", "WHERE uri_declarante IS NULL AND rut NOT LIKE 'DIPCAM-%'")
    # ~215 residual = gobierno Kast (CPLT plazo 30d desde 11-mar-2026) + locales sin declaracion
    necesita = n_dipcam > 0 or n_sin_uri > 220
    return (necesita, f"{n_dipcam} diputados sin candidato_id, {n_sin_uri:,} sin uri_declarante",
            "Hay politicos sin vincular o sin uri_declarante")

def detectar_ruts(cur):
    n_sin_rut = count(cur, "candidato",
        "WHERE (rut LIKE 'CPLT-%' OR rut LIKE 'SERVEL-%' OR rut LIKE 'DIPCAM-%') "
        "AND uri_declarante IS NOT NULL")
    return (n_sin_rut > 0, f"{n_sin_rut:,} candidatos con uri_declarante pero sin RUT real",
            "Extraer RUTs desde InfoProbidad via cloudscraper")

def detectar_lobby(cur):
    n_aud   = count(cur, "temp_audiencia")           if tabla_existe(cur, "temp_audiencia")           else 0
    n_pas   = count(cur, "temp_asistencia_pasivo")   if tabla_existe(cur, "temp_asistencia_pasivo")   else 0
    n_match = count(cur, "match_candidato_lobby")    if tabla_existe(cur, "match_candidato_lobby")    else 0
    ok = n_aud > 500000 and n_pas > 500000 and n_match > 100000
    return (not ok,
            f"{n_aud:,} audiencias, {n_pas:,} asistencias, {n_match:,} matches",
            "Importar temp_audiencia, temp_asistencia_pasivo y match_candidato_lobby")

def detectar_participaciones(cur):
    # Candidatos con RUT real y uri_declarante (los que el script puede procesar)
    n_procesables = count(cur, "candidato",
        "WHERE uri_declarante IS NOT NULL "
        "AND rut NOT LIKE 'CPLT-%' AND rut NOT LIKE 'SERVEL-%' AND rut NOT LIKE 'DIPCAM-%'")
    # Usar checkpoint para saber cuantos fueron procesados (OK o SIN_PARTICIPACIONES)
    procesados = 0
    checkpoint = "data/progreso_participaciones.json"
    if os.path.exists(checkpoint):
        with open(checkpoint, encoding="utf-8") as f:
            prog = json.load(f)
        procesados = sum(1 for v in prog.values() if v in ("OK", "SIN_PARTICIPACIONES"))
    faltantes = max(0, n_procesables - procesados)
    ok = faltantes < 50
    return (not ok,
            f"{procesados:,}/{n_procesables:,} procesados via checkpoint",
            f"{faltantes:,} candidatos con RUT real pendientes de explorar")

def detectar_enriquecimiento(cur):
    # Comparar contra empresas UNICAS (no filas de participacion_societaria)
    try:
        cur.execute("SELECT COUNT(DISTINCT empresa_rut) FROM participacion_societaria")
        n_unicas = cur.fetchone()[0]
    except Exception:
        n_unicas = 0
    n_enr = count(cur, "empresa_enriquecida", "WHERE estado_consulta='OK'") \
            if tabla_existe(cur, "empresa_enriquecida") else 0
    n_cmf = count(cur, "directorio_cmf") \
            if tabla_existe(cur, "directorio_cmf") else 0
    ok = n_unicas > 0 and n_enr >= int(n_unicas * 0.90) and n_cmf > 0
    return (not ok,
            f"{n_enr:,}/{n_unicas:,} empresas unicas enriquecidas, {n_cmf:,} registros CMF",
            "Enriquecer empresas con SII y consultar CMF por candidatos")

def detectar_mercado_publico(cur):
    n = count(cur, "orden_compra") if tabla_existe(cur, "orden_compra") else 0
    ok = n > 0
    return (not ok, f"{n:,} OCs de candidatos en DB",
            "Descargar ZIPs mensuales oc-da y filtrar por empresas de candidatos")

def detectar_licitaciones(cur):
    n = count(cur, "licitacion") if tabla_existe(cur, "licitacion") else 0
    ok = n > 500
    return (not ok, f"{n:,} licitaciones en DB",
            "Descargar OCDS bulk mensual y filtrar por empresas de candidatos")

def detectar_bcn(cur):
    n = count(cur, "proyecto_ley") if tabla_existe(cur, "proyecto_ley") else 0
    ok = n > 1000
    return (not ok, f"{n:,} proyectos de ley en DB",
            "Importar mociones BCN para diputados via facetas-buscador-avanzado")

def detectar_ia(cur):
    n_alertas  = count(cur, "alerta_probidad")
    n_matches  = count(cur, "match_candidato_lobby") if tabla_existe(cur, "match_candidato_lobby") else 0
    n_sin_grav = count(cur, "alerta_probidad", "WHERE gravedad IS NULL OR gravedad = ''")
    necesita   = n_matches > 0 and (n_alertas == 0 or n_sin_grav > 0)
    return (necesita, f"{n_alertas:,} alertas ({n_sin_grav} sin gravedad), {n_matches:,} matches lobby",
            "Sin alertas o hay alertas sin clasificar por gravedad")

def detectar_scores(cur):
    tiene_col  = columna_existe(cur, "candidato", "score_transparencia")
    n_candidatos = count(cur, "candidato")
    n_sin_score  = count(cur, "candidato", "WHERE score_transparencia IS NULL") if tiene_col else n_candidatos
    return (n_sin_score > 0, f"{n_sin_score:,} candidatos sin score_transparencia",
            "Calcular scores para todos")

def detectar_financiamiento_servel(cur):
    n = count(cur, "financiamiento_electoral") if tabla_existe(cur, "financiamiento_electoral") else 0
    ok = n > 1000
    return (not ok, f"{n:,} registros en financiamiento_electoral",
            "Importar Reporte_Ingresos_Gastos_Definitivas2024.xlsx desde SERVEL")


# ---------------------------------------------------------------------------
# Registro de pasos en orden
# ---------------------------------------------------------------------------

PASOS = [
    # (id, descripcion, script, funcion_detectar)
    ("limpiar_audiencias",  "Limpiar audiencias CSV UTF-16 -> UTF-8",
     "scripts/limpieza/limpiar_audiencias_final.py", detectar_limpiar_audiencias),

    ("limpiar_asistencias", "Limpiar asistencias CSV UTF-16 -> UTF-8",
     "scripts/limpieza/limpiar_asistencias.py",      detectar_limpiar_asistencias),

    ("arreglar_columnas",   "Arreglar columnas pasivos CSV",
     "scripts/herramientas/arreglar_columnas.py",    detectar_arreglar_columnas),

    ("ingesta",             "Ingestar candidatos desde Servel -> PostgreSQL",
     "scripts/pipeline/pipeline_ingesta.py",         detectar_ingesta),

    ("representaciones",    "Importar representaciones lobby -> PostgreSQL",
     "scripts/pipeline/importar_representaciones.py",detectar_representaciones),

    ("lobby",               "Importar tablas lobby: audiencias, asistencias, match candidato-lobby",
     "scripts/pipeline/importar_lobby.py",           detectar_lobby),

    ("congreso",            "Votaciones y asistencia desde API del Congreso",
     "scripts/pipeline/ingesta_congreso.py",         detectar_congreso),

    ("bcn",                 "Proyectos de ley BCN: mociones de diputados",
     "scripts/pipeline/ingesta_bcn.py",              detectar_bcn),

    ("declaraciones",       "Importar declaraciones CPLT bulk -> declaracion_cplt",
     "scripts/pipeline/importar_declaraciones.py",   detectar_declaraciones),

    ("consolidador",        "Consolidar funcionarios rescatados con RUT",
     "scripts/herramientas/consolidador_maestro.py", detectar_consolidador),

    ("cruce_infoprobidad",  "Cruzar candidatos con CPLT CSV para uri_declarante",
     "scripts/herramientas/cruce_infoprobidad.py",   detectar_cruce_infoprobidad),

    ("completar",           "Agregar politicos faltantes (CPLT + ex-diputados)",
     "scripts/pipeline/completar_candidatos.py",     detectar_completar),

    ("ruts",                "Extraer RUTs reales desde InfoProbidad",
     "scripts/pipeline/extraer_ruts_infoprobidad.py",detectar_ruts),

    ("participaciones",     "Empresas declaradas CPLT -> participacion_societaria",
     "scripts/pipeline/poblar_participaciones.py",   detectar_participaciones),

    ("enriquecimiento",     "Enriquecer empresas via SII + detectar directores CMF",
     "scripts/pipeline/enriquecer_empresas.py",      detectar_enriquecimiento),

    ("mercado_publico",     "OC Mercado Publico: empresas de candidatos como proveedores",
     "scripts/pipeline/ingesta_mercado_publico.py",  detectar_mercado_publico),

    ("licitaciones",        "Licitaciones OCDS: adjudicadas a empresas de candidatos",
     "scripts/pipeline/ingesta_licitaciones.py",     detectar_licitaciones),

    ("financiamiento_servel", "Financiamiento electoral 2024 desde SERVEL (ingresos, gastos, donantes)",
     "scripts/pipeline/ingesta_financiamiento_servel.py", detectar_financiamiento_servel),

    ("ia",                  "IA fiscalizadora: detectar conflictos de interes",
     "scripts/pipeline/ia_fiscalizadora.py",         detectar_ia),

    ("scores",              "Calcular score_transparencia por candidato",
     "scripts/pipeline/calcular_scores.py",          detectar_scores),
]

PASO_IDS = [p[0] for p in PASOS]


# ---------------------------------------------------------------------------
# Diagnostico
# ---------------------------------------------------------------------------

def diagnostico_completo(cur):
    resultado = {}
    for paso_id, desc, script, detectar in PASOS:
        try:
            necesita, estado, razon = detectar(cur)
        except Exception as e:
            necesita, estado, razon = True, "Error al detectar", str(e)
        resultado[paso_id] = (necesita, estado, razon, desc, script)
    return resultado


# ---------------------------------------------------------------------------
# Reporte estado
# ---------------------------------------------------------------------------

def mostrar_estado(cur):
    sep("=")
    log("ESTADO ACTUAL DE LA DB Y ARCHIVOS")
    sep("=")

    tablas = [
        ("candidato",               "candidatos"),
        ("participacion_societaria","participaciones societarias"),
        ("empresa_enriquecida",     "empresas enriquecidas (SII)"),
        ("directorio_cmf",          "registros directorio CMF"),
        ("match_candidato_lobby",   "matches candidato-lobby"),
        ("alerta_probidad",         "alertas de probidad"),
        ("orden_compra",            "OCs de candidatos (Mercado Publico)"),
        ("financiamiento_electoral","registros financiamiento electoral SERVEL 2024"),
        ("donante_electoral",       "transacciones individuales donantes/gastos"),
        ("votacion_camara",         "votaciones Congreso"),
        ("voto_diputado",           "votos individuales"),
        ("asistencia_sesion",       "asistencia sesiones"),
        ("temp_representaciones",   "representaciones lobby"),
    ]

    for tabla, desc in tablas:
        if tabla_existe(cur, tabla):
            n = count(cur, tabla)
            log(f"  {tabla:<30} {n:>10,}  {desc}")
        else:
            log(f"  {tabla:<30} {'--':>10}   (no existe aun)")

    n_rut_real = count(cur, "candidato",
        "WHERE rut NOT LIKE 'CPLT-%' AND rut NOT LIKE 'SERVEL-%' AND rut NOT LIKE 'DIPCAM-%'")
    n_uri      = count(cur, "candidato", "WHERE uri_declarante IS NOT NULL")
    tiene_sc   = columna_existe(cur, "candidato", "score_transparencia")
    n_score    = count(cur, "candidato", "WHERE score_transparencia IS NOT NULL") if tiene_sc else 0
    n_score_avg= None
    if tiene_sc and n_score > 0:
        cur.execute("SELECT ROUND(AVG(score_transparencia),1) FROM candidato WHERE score_transparencia IS NOT NULL")
        n_score_avg = cur.fetchone()[0]

    log()
    log(f"  Con RUT real:          {n_rut_real:,}")
    log(f"  Con uri_declarante:    {n_uri:,}")
    log(f"  Con score:             {n_score:,}" + (f"  (promedio {n_score_avg})" if n_score_avg else ""))

    log()
    sep("-")
    log("DIAGNOSTICO POR PASO")
    sep("-")

    diag = diagnostico_completo(cur)
    pendientes = []
    for paso_id, desc, script, _ in PASOS:
        necesita, estado, razon, *_ = diag[paso_id]
        icono = "PENDIENTE" if necesita else "   OK    "
        existe = os.path.exists(script)
        nota_script = "" if existe else "  [script no encontrado]"
        log(f"  [{icono}] {paso_id:<22} {estado}{nota_script}")
        if necesita and existe:
            log(f"            {'':22} -> {razon}")
            pendientes.append(paso_id)

    log()
    if pendientes:
        log(f"Pendientes: {', '.join(pendientes)}")
    else:
        log("Todo al dia.")

    return diag, pendientes


# ---------------------------------------------------------------------------
# Ejecutar script
# ---------------------------------------------------------------------------

def ejecutar(paso_id, script):
    if not os.path.exists(script):
        log(f"  SKIP: script no encontrado: {script}")
        return None  # None = script no existe (no es fallo)

    log(f"  > python {script}")
    inicio = time.time()
    proc = subprocess.run([sys.executable, script], capture_output=False, text=True)
    duracion = time.time() - inicio

    if proc.returncode == 0:
        log(f"  OK ({duracion:.0f}s)")
        return True
    else:
        log(f"  FALLO exit={proc.returncode} ({duracion:.0f}s)")
        return False


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def correr_pipeline(pasos_a_evaluar, forzar=False):
    conn = get_conn()
    cur  = conn.cursor()

    log()
    sep("=")
    log("DIAGNOSTICO INICIAL")
    sep("=")
    diag, _ = mostrar_estado(cur)

    exitosos = []
    saltados  = []
    fallidos  = []
    no_script = []

    for paso_id, desc, script, detectar in PASOS:
        if paso_id not in pasos_a_evaluar:
            continue

        necesita, estado, razon, *_ = diag[paso_id]

        log()
        sep()
        log(f"PASO: {paso_id.upper()} — {desc}")
        log(f"  Estado:  {estado}")

        if not necesita and not forzar:
            log(f"  Al dia — saltando")
            saltados.append(paso_id)
            continue

        if forzar:
            log(f"  [forzar activado]")
        else:
            log(f"  Trabajo: {razon}")

        # Cerrar conexion antes de lanzar el script hijo para evitar locks en PostgreSQL
        cur.close(); conn.close()

        resultado = ejecutar(paso_id, script)

        # Reabrir conexion para diagnostico del siguiente paso
        conn = get_conn(); cur = conn.cursor()
        diag = diagnostico_completo(cur)

        if resultado is None:
            log(f"  Script no encontrado — saltando")
            no_script.append(paso_id)
        elif resultado:
            exitosos.append(paso_id)
        else:
            fallidos.append(paso_id)
            log(f"  Continuando con el siguiente paso...")

    cur.close()
    conn.close()
    return exitosos, saltados, fallidos, no_script


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _log_file

    parser = argparse.ArgumentParser(
        description="Pipeline maestro CIAP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Pasos disponibles: {', '.join(PASO_IDS)}"
    )
    parser.add_argument("--estado",  action="store_true", help="Solo mostrar diagnostico completo")
    parser.add_argument("--lista",   action="store_true", help="Listar pasos disponibles y salir")
    parser.add_argument("--solo",    metavar="PASO",      help="Correr solo ese paso (forzado)")
    parser.add_argument("--pasos",   metavar="P1,P2,...", help="Correr lista de pasos especificos (forzado), ej: ia,scores")
    parser.add_argument("--desde",   metavar="PASO",      help="Correr desde ese paso en adelante")
    parser.add_argument("--forzar",  metavar="PASO",      help="Forzar ese paso y los siguientes")
    parser.add_argument("--backup",  action="store_true", help="Crear backup de CSVs + pg_dump antes de ejecutar")
    args = parser.parse_args()

    if args.lista:
        print("\nPasos disponibles:\n")
        for paso_id, desc, script, _ in PASOS:
            existe = "OK" if os.path.exists(script) else "NO EXISTE"
            print(f"  {paso_id:<22} — {desc}  [{existe}]")
        print()
        sys.exit(0)

    for arg in [args.solo, args.desde, args.forzar]:
        if arg and arg not in PASO_IDS:
            print(f"Paso desconocido: '{arg}'")
            print(f"Opciones: {', '.join(PASO_IDS)}")
            sys.exit(1)

    if args.pasos:
        pasos_invalidos = [p for p in args.pasos.split(",") if p.strip() not in PASO_IDS]
        if pasos_invalidos:
            print(f"Pasos desconocidos: {', '.join(pasos_invalidos)}")
            print(f"Opciones: {', '.join(PASO_IDS)}")
            sys.exit(1)

    os.makedirs("data", exist_ok=True)
    _log_file = open(LOG_FILE, "a", encoding="utf-8")

    sep("=")
    log("PIPELINE MAESTRO — CIUDADANO INFORMADO (CIAP)")
    log(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sep("=")

    if args.estado:
        conn = get_conn(); cur = conn.cursor()
        mostrar_estado(cur)
        cur.close(); conn.close()
        _log_file.close()
        return

    if args.backup:
        sep("-")
        log("BACKUP PREVIO")
        sep("-")
        hacer_backup()

    # Determinar pasos a evaluar
    if args.solo:
        pasos_a_evaluar = [args.solo]
        forzar = True
    elif args.pasos:
        # Mantener el orden definido en PASOS, no el orden en que se escribieron
        solicitados = set(p.strip() for p in args.pasos.split(","))
        pasos_a_evaluar = [p for p in PASO_IDS if p in solicitados]
        forzar = True
    elif args.forzar:
        idx = PASO_IDS.index(args.forzar)
        pasos_a_evaluar = PASO_IDS[idx:]
        forzar = True
    elif args.desde:
        idx = PASO_IDS.index(args.desde)
        pasos_a_evaluar = PASO_IDS[idx:]
        forzar = False
    else:
        pasos_a_evaluar = PASO_IDS
        forzar = False

    exitosos, saltados, fallidos, no_script = correr_pipeline(pasos_a_evaluar, forzar=forzar)

    # Reporte final
    sep("=")
    log("RESUMEN FINAL")
    sep("=")
    log(f"  Ejecutados OK:      {', '.join(exitosos)  if exitosos   else 'ninguno'}")
    log(f"  Al dia (saltados):  {', '.join(saltados)  if saltados   else 'ninguno'}")
    log(f"  Sin script:         {', '.join(no_script) if no_script  else 'ninguno'}")
    log(f"  Fallidos:           {', '.join(fallidos)  if fallidos   else 'ninguno'}")

    log()
    conn2 = get_conn(); cur2 = conn2.cursor()
    mostrar_estado(cur2)
    cur2.close(); conn2.close()

    sep("=")
    log(f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sep("=")

    _log_file.close()
    if fallidos:
        sys.exit(1)


if __name__ == "__main__":
    main()
