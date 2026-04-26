import os
import re
import json
import time
import random
import html as html_module
import psycopg2
from psycopg2.extras import execute_values
import cloudscraper
from dotenv import load_dotenv

load_dotenv()

ARCHIVO_PROGRESO = "data/progreso_participaciones.json"

# Secciones del JSON CPLT que contienen participaciones en empresas.
# En orden de relevancia para detectar conflictos de interés:
#   1. Derechos_Acciones_Chile / Extranjero — participaciones accionarias directas
#   2. Actividades_Profesionales_A_La_Fecha — actividad actual con empresa (puede indicar dueño)
#   3. Actividades_Profesionales_Ultimos_12_Meses — actividades recientes
#   4. Actividades_Profesionales_Conyuge — actividad del cónyuge (conflicto indirecto)
SECCIONES_EMPRESA = [
    'Derechos_Acciones_Chile',
    'Derechos_Acciones_Extranjero',
    'Actividades_Profesionales_A_La_Fecha',
    'Actividades_Profesionales_Ultimos_12_Meses',
    'Actividades_Profesionales_Conyuge',
]

# RUTs que no son empresas reales (ignorar)
RUTS_IGNORAR = {'', 'NAN', 'RESERVADO', 'NONE', 'NULL', 'N/A'}


def crear_scraper():
    return cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )


def normalizar_rut(rut):
    if rut is None:
        return ""
    s = str(rut).strip()
    if s.upper() in ("", "NAN", "NONE", "NULL"):
        return ""
    return s.replace(".", "").replace("-", "").upper()


def cargar_progreso():
    if os.path.exists(ARCHIVO_PROGRESO):
        with open(ARCHIVO_PROGRESO, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_progreso(progreso):
    with open(ARCHIVO_PROGRESO, "w", encoding="utf-8") as f:
        json.dump(progreso, f)


def extraer_participaciones_de_declaracion(scraper, uri_declaracion):
    """
    Descarga una declaracion CPLT y extrae todas las empresas vinculadas al funcionario.
    Devuelve lista de dicts: [{rut, nombre, porcentaje, fuente}]
    """
    r = scraper.get(uri_declaracion, timeout=20)
    r.raise_for_status()

    texto = html_module.unescape(r.text)
    m = re.search(r'jsonCargado">\s*(\{.*?\})\s*</span>', texto, re.DOTALL)
    if not m:
        return []

    try:
        obj = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    participaciones = []

    for seccion in SECCIONES_EMPRESA:
        items = obj.get(seccion)
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            rut_raw = item.get('RUT', '')
            rut_empresa = normalizar_rut(rut_raw)

            if not rut_empresa or rut_empresa in RUTS_IGNORAR:
                continue

            nombre_empresa = (
                item.get('Nombre_Razon_Social') or
                item.get('Nombre_Sociedad') or
                item.get('Nombre') or
                'SIN NOMBRE'
            )

            # Para Derechos_Acciones, el porcentaje está en Cantidad_Porcentaje
            # Para Actividades, está en Porcentaje o no existe
            try:
                porcentaje = float(
                    item.get('Cantidad_Porcentaje') or
                    item.get('Porcentaje') or
                    0
                )
                porcentaje = max(0.0, min(porcentaje, 999.99))  # clamp DECIMAL(5,2)
            except (ValueError, TypeError):
                porcentaje = 0.0

            participaciones.append({
                'rut':       rut_empresa,
                'nombre':    str(nombre_empresa)[:255],
                'porcentaje': porcentaje,
                'fuente':    seccion,
            })

    return participaciones


def obtener_candidatos_con_uri(conn):
    """
    Devuelve lista de (candidato_id, rut, uri_declaracion) consultando directamente
    la tabla declaracion_cplt. Cubre todos los candidatos con uri_declarante en la DB,
    incluyendo los que no estan en los CSV maestros (ex-diputados, gobierno, etc.).
    Usa la declaracion mas reciente de cada candidato.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (c.id)
                c.id,
                c.rut,
                d.uri_declaracion
            FROM candidato c
            JOIN declaracion_cplt d ON d.uri_declarante = c.uri_declarante
            WHERE c.uri_declarante IS NOT NULL
              AND c.rut NOT LIKE 'CPLT-%%'
              AND c.rut NOT LIKE 'SERVEL-%%'
              AND c.rut NOT LIKE 'DIPCAM-%%'
            ORDER BY c.id, d.fecha_declaracion DESC NULLS LAST
        """)
        return cur.fetchall()


def poblar():
    print("Conectando a PostgreSQL...")
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "ciudadano_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )

    print("Obteniendo candidatos con uri_declaracion desde declaracion_cplt...")
    candidatos = obtener_candidatos_con_uri(conn)
    print(f"  {len(candidatos)} candidatos con declaracion vinculada en DB")

    progreso = cargar_progreso()
    scraper  = crear_scraper()

    total      = len(candidatos)
    con_datos  = 0
    sin_url    = 0
    sin_partic = 0
    errores    = 0
    insertados = 0

    for i, (cand_id, rut_db, uri_declaracion) in enumerate(candidatos, 1):
        if not uri_declaracion:
            sin_url += 1
            continue

        if uri_declaracion in progreso:
            estado = progreso[uri_declaracion]
            if estado == 'OK':
                con_datos  += 1
            elif estado == 'SIN_PARTICIPACIONES':
                sin_partic += 1
            continue

        try:
            participaciones = extraer_participaciones_de_declaracion(scraper, uri_declaracion)

            if participaciones:
                rows = [
                    (cand_id, p['rut'], p['nombre'], p['porcentaje'])
                    for p in participaciones
                ]
                with conn.cursor() as cur:
                    execute_values(
                        cur,
                        """INSERT INTO participacion_societaria
                           (candidato_id, empresa_rut, empresa_nombre, porcentaje_propiedad)
                           VALUES %s
                           ON CONFLICT (candidato_id, empresa_rut) DO NOTHING""",
                        rows
                    )
                conn.commit()
                insertados += len(rows)
                con_datos  += 1
                progreso[uri_declaracion] = 'OK'
                fuentes = set(p['fuente'] for p in participaciones)
                print(f"  OK [{i}/{total}] {rut_db}: {len(participaciones)} empresa(s) [{', '.join(fuentes)}]")
            else:
                sin_partic += 1
                progreso[uri_declaracion] = 'SIN_PARTICIPACIONES'

        except Exception as e:
            conn.rollback()
            errores += 1
            progreso[uri_declaracion] = f'ERROR: {str(e)[:80]}'
            print(f"  ERR [{i}/{total}] {rut_db}: {e}")

        if i % 50 == 0:
            guardar_progreso(progreso)
            print(f"  [{i}/{total}] insertadas={insertados} errores={errores}")

        time.sleep(random.uniform(0.5, 1.5))

    guardar_progreso(progreso)
    conn.close()

    print("\nPROCESO COMPLETADO")
    print(f"  Candidatos con empresas declaradas:  {con_datos}")
    print(f"  Candidatos sin participaciones:      {sin_partic}")
    print(f"  Candidatos sin URL en maestro:       {sin_url}")
    print(f"  Errores de red:                      {errores}")
    print(f"  Total filas insertadas en DB:        {insertados}")


if __name__ == "__main__":
    poblar()
