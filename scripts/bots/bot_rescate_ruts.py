"""
bot_rescate_ruts.py - Bot Selenium para rescatar RUTs via nombrerutyfirma.com
Unifica bot_ninja_csv.py y bot_visual_rutificador.py.

Lee: data/funcionarios_sin_rut.csv  (columnas: nombres, cargo, comuna, link_declaracion)
Escribe: data/funcionarios_rescatados_bots.csv (mismas columnas + rut)

Requiere: undetected-chromedriver, selenium, pandas
Ejecutar desde la raiz del proyecto:
    .venv/Scripts/python.exe scripts/bots/bot_rescate_ruts.py
"""

import os
import re
import time
import random
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ARCHIVO_FALTANTES  = "data/funcionarios_sin_rut.csv"
ARCHIVO_RESCATADOS = "data/funcionarios_rescatados_bots.csv"
CHROME_VERSION     = 146   # ajustar a la version instalada
REINICIO_CADA      = 15    # reiniciar el driver cada N busquedas


def limpiar_texto(texto):
    if pd.isna(texto):
        return ""
    return str(texto).upper().strip()


def iniciar_driver():
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    return uc.Chrome(options=options, use_subprocess=True, version_main=CHROME_VERSION)


def buscar_rut(driver, nombre_completo, comuna_oficial):
    """Busca un RUT en nombrerutyfirma.com. Valida por comuna si hay multiples resultados.
    Retorna el RUT limpio (ej: '123456789') o un string descriptivo del fallo."""
    try:
        driver.get("https://nombrerutyfirma.com/")
        wait = WebDriverWait(driver, 10)

        campo = wait.until(EC.presence_of_element_located((By.NAME, "term")))
        campo.clear()
        campo.send_keys(nombre_completo)

        btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        driver.execute_script("arguments[0].click();", btn)

        try:
            filas = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.XPATH, "//table/tbody/tr"))
            )
        except Exception:
            return "NO_ENCONTRADO"

        comuna_objetivo = limpiar_texto(comuna_oficial)
        candidatos = []

        for fila in filas:
            texto = limpiar_texto(fila.text)
            m = re.search(r'\d{1,2}\.\d{3}\.\d{3}-[\dkK]', texto)
            if m:
                rut = m.group(0).replace(".", "").upper()
                if len(filas) == 1:
                    return rut
                if comuna_objetivo and comuna_objetivo in texto:
                    candidatos.append(rut)

        if len(candidatos) == 1:
            return candidatos[0]
        if len(candidatos) > 1:
            return "ERROR_AMBIGUO"
        return "SIN_COINCIDENCIA_COMUNA"

    except Exception:
        return "ERROR_NAVEGACION"


def ejecutar():
    if not os.path.exists(ARCHIVO_FALTANTES):
        print(f"No se encontro: {ARCHIVO_FALTANTES}")
        return

    df = pd.read_csv(ARCHIVO_FALTANTES)
    print(f"Iniciando rescate para {len(df)} funcionarios sin RUT...")

    # Cargar rescatados previos para no repetir
    ya_rescatados = set()
    rescatados = []
    if os.path.exists(ARCHIVO_RESCATADOS):
        prev = pd.read_csv(ARCHIVO_RESCATADOS)
        ya_rescatados = set(prev["nombres"].str.upper())
        rescatados = prev.to_dict("records")
        print(f"  {len(rescatados)} rescates previos cargados - se saltaran nombres ya procesados")

    driver = iniciar_driver()
    contador = 0

    for idx, row in df.iterrows():
        nombre = str(row["nombres"]).strip()
        if nombre.upper() in ya_rescatados:
            continue

        comuna = row.get("comuna", "")

        if contador > 0 and contador % REINICIO_CADA == 0:
            print("  Reiniciando driver para evitar bloqueos...")
            driver.quit()
            time.sleep(5)
            driver = iniciar_driver()

        print(f"[{idx + 1}/{len(df)}] {nombre} ({comuna})...", end=" ", flush=True)

        resultado = buscar_rut(driver, nombre, comuna)

        if "-" in resultado and len(resultado) > 5:
            print(f"OK: {resultado}")
            rescatados.append({
                "rut": resultado,
                "nombres": nombre,
                "cargo": row.get("cargo", ""),
                "comuna": comuna,
                "link_declaracion": row.get("link_declaracion", ""),
            })
            ya_rescatados.add(nombre.upper())
            pd.DataFrame(rescatados).to_csv(ARCHIVO_RESCATADOS, index=False, encoding="utf-8-sig")
        else:
            print(resultado)

        time.sleep(random.uniform(4.5, 8.5))
        contador += 1

    driver.quit()
    print(f"\nFinalizado. {len(rescatados)} RUTs rescatados en total.")
    print(f"Archivo: {ARCHIVO_RESCATADOS}")


if __name__ == "__main__":
    ejecutar()
