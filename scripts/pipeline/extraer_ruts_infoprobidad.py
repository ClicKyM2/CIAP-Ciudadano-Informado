"""
extraer_ruts_infoprobidad.py
Extrae RUTs reales desde InfoProbidad (CPLT) para candidatos que tienen
uri_declarante pero aun tienen RUT temporal (CPLT-*, SERVEL-*, DIPCAM-*).

- Usa Playwright (Chromium real) para evitar bloqueo de Cloudflare
- Lee candidatos directamente desde PostgreSQL
- Actualiza columna `rut` en la tabla `candidato`
- Checkpoint en data/progreso_ruts.json (clave: uri_declarante)

Flags:
  --limpiar-bloqueados   Borra entradas SIN_RUT/ERROR del checkpoint para reintentarlas

Ejecutar desde la raiz del proyecto:
    .venv/Scripts/python.exe scripts/pipeline/extraer_ruts_infoprobidad.py
    .venv/Scripts/python.exe scripts/pipeline/extraer_ruts_infoprobidad.py --limpiar-bloqueados
"""

import os
import re
import json
import asyncio
import random
import html as html_module
import argparse
import psycopg2
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

load_dotenv()

ARCHIVO_PROGRESO = "data/progreso_ruts.json"
DELAY_MIN = 2.0
DELAY_MAX = 4.0


def cargar_progreso():
    if os.path.exists(ARCHIVO_PROGRESO):
        with open(ARCHIVO_PROGRESO, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_progreso(p):
    with open(ARCHIVO_PROGRESO, "w", encoding="utf-8") as f:
        json.dump(p, f)


def extraer_rut_de_html(html_text):
    texto = html_module.unescape(html_text)

    m = re.search(r'jsonCargado">\s*(\{.*?\})\s*</span>', texto, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(1))
            run = str(obj.get("Datos_del_Declarante", {}).get("RUN", "")).strip()
            if run and run.upper() not in ("", "RESERVADO", "NONE", "NAN"):
                return run.replace(".", "").replace("-", "").upper()
        except (json.JSONDecodeError, AttributeError):
            pass

    m2 = re.search(r'&quot;RUN&quot;\s*:\s*&quot;([^&]+)&quot;', html_text)
    if m2:
        run = m2.group(1).strip()
        if run and run.upper() not in ("RESERVADO", "NONE", ""):
            return run.replace(".", "").replace("-", "").upper()

    return None


async def obtener_rut(page, uri_declarante, uri_declaracion=None):
    urls = [u for u in [uri_declaracion, uri_declarante] if u]
    for url in urls:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            if "challenge" in page.url or "Just a moment" in await page.title():
                await page.wait_for_timeout(8000)
            html = await page.content()
            rut = extraer_rut_de_html(html)
            if rut:
                return rut
        except PWTimeout:
            pass
        except Exception:
            pass
        await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    return None


async def extraer_ruts(limpiar_bloqueados=False):
    os.makedirs("data", exist_ok=True)

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "ciudadano_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                c.id,
                c.nombres,
                c.uri_declarante,
                (
                    SELECT d.uri_declaracion
                    FROM declaracion_cplt d
                    WHERE d.uri_declarante = c.uri_declarante
                    ORDER BY d.fecha_declaracion DESC NULLS LAST
                    LIMIT 1
                ) AS uri_declaracion
            FROM candidato c
            WHERE (
                c.rut LIKE 'CPLT-%%'
                OR c.rut LIKE 'SERVEL-%%'
                OR c.rut LIKE 'DIPCAM-%%'
            )
            AND c.uri_declarante IS NOT NULL
            ORDER BY c.id
        """)
        candidatos = cur.fetchall()

    total = len(candidatos)
    print(f"Candidatos pendientes de RUT real: {total}")

    if total == 0:
        print("Nada que procesar.")
        conn.close()
        return

    progreso = cargar_progreso()

    if limpiar_bloqueados:
        bloqueados = [k for k, v in progreso.items() if v in ("SIN_RUT", "ERROR")]
        for k in bloqueados:
            del progreso[k]
        guardar_progreso(progreso)
        print(f"  Checkpoint: {len(bloqueados)} entradas SIN_RUT/ERROR eliminadas para reintento")

    actualizados = 0
    sin_rut = 0
    errores = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="es-CL",
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        for i, (cand_id, nombres, uri_declarante, uri_declaracion) in enumerate(candidatos, 1):

            if uri_declarante in progreso:
                estado = progreso[uri_declarante]
                if estado not in ("SIN_RUT", "ERROR", "DUPLICADO"):
                    try:
                        with conn.cursor() as cur:
                            cur.execute(
                                "UPDATE candidato SET rut = %s WHERE id = %s "
                                "AND (rut LIKE 'CPLT-%%' OR rut LIKE 'SERVEL-%%' OR rut LIKE 'DIPCAM-%%')",
                                (estado, cand_id),
                            )
                            conn.commit()
                        actualizados += 1
                    except Exception:
                        conn.rollback()
                        progreso[uri_declarante] = "DUPLICADO"
                        sin_rut += 1
                else:
                    sin_rut += 1
                continue

            print(f"  [{i}/{total}] {nombres}")
            try:
                rut = await obtener_rut(page, uri_declarante, uri_declaracion)

                if rut:
                    try:
                        with conn.cursor() as cur:
                            cur.execute(
                                "UPDATE candidato SET rut = %s WHERE id = %s",
                                (rut, cand_id),
                            )
                            conn.commit()
                        progreso[uri_declarante] = rut
                        actualizados += 1
                        print(f"    RUT: {rut}")
                    except Exception:
                        conn.rollback()
                        progreso[uri_declarante] = "DUPLICADO"
                        sin_rut += 1
                        print(f"    RUT {rut} duplicado")
                else:
                    progreso[uri_declarante] = "SIN_RUT"
                    sin_rut += 1
                    print(f"    Sin RUT (oculto en CPLT)")

            except Exception as e:
                errores += 1
                progreso[uri_declarante] = "ERROR"
                print(f"    Error: {e}")

            if i % 50 == 0:
                guardar_progreso(progreso)
                print(f"  [{i}/{total}] actualizados={actualizados} sin_rut={sin_rut} errores={errores}")

            await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        await browser.close()

    guardar_progreso(progreso)
    conn.close()

    print("\nPROCESO COMPLETADO")
    print(f"  RUTs actualizados en DB: {actualizados}")
    print(f"  Sin RUT (oculto/CPLT):   {sin_rut}")
    print(f"  Errores de conexion:     {errores}")
    print(f"  Checkpoint guardado en:  {ARCHIVO_PROGRESO}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limpiar-bloqueados", action="store_true",
                        help="Reintenta candidatos marcados como SIN_RUT o ERROR en checkpoint")
    args = parser.parse_args()
    asyncio.run(extraer_ruts(limpiar_bloqueados=args.limpiar_bloqueados))
