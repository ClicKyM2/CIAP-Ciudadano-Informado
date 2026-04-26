"""
sii.py - Enriquecedor de datos de empresas desde fuentes locales del CPLT
(originalmente pensado para SII, pero el CAPTCHA de zeus.sii.cl cambio su mecanismo
y ya no es scripteable sin un browser headless)

FUENTE ALTERNATIVA (disponible localmente):
  data/csvacciones.csv — contiene columnas EntidadAccion, Giro, RutJuridica
  Este CSV viene directamente del CPLT y ya tiene los datos de giro y nombre oficial
  para TODAS las empresas que los funcionarios declararon.

El campo 'RutJuridica' en csvacciones.csv es el numero de RUT sin DV (ej: 76123456).
El campo 'empresa_rut' en participacion_societaria puede tener DV concatenado (ej: 761234563).

ESTRATEGIA:
  1. Leer csvacciones.csv y construir un dict {rut_num -> {giro, nombre}}
  2. Para cada empresa_rut en participacion_societaria, extraer el numero sin DV
     y buscar en el dict del CSV
  3. Lo que no este en el CSV se marca como NO_ENCONTRADO_LOCAL

Uso:
    from scripts.extractores.sii import cargar_indice_csv, consultar_empresa_local

    indice = cargar_indice_csv("data/csvacciones.csv")
    datos = consultar_empresa_local("761234563", indice)
    # -> {"razon_social": "EMPRESA SA", "giro_principal": "Comercio", ...}
"""

import os
import pandas as pd

CSV_PATH = "data/csvacciones.csv"

# ---------------------------------------------------------------------------
# Helpers de RUT
# ---------------------------------------------------------------------------

def split_rut(rut_raw: str):
    """
    Separa un RUT (con DV al final) en (numero, dv).
    "761234563" -> ("76123456", "3")
    "76123456K" -> ("76123456", "K")
    Si tiene guion: "76123456-3" -> ("76123456", "3")
    Retorna (None, None) si el RUT es invalido.
    """
    rut = rut_raw.strip().upper().replace(".", "").replace("-", "")
    if len(rut) < 2:
        return None, None
    return rut[:-1], rut[-1]


def rut_numero(rut_raw: str) -> str | None:
    """Extrae solo el numero de RUT sin DV."""
    num, _ = split_rut(rut_raw)
    return num


# ---------------------------------------------------------------------------
# Carga del indice desde CSV local
# ---------------------------------------------------------------------------

def cargar_indice_csv(csv_path: str = CSV_PATH) -> dict[str, dict]:
    """
    Lee csvacciones.csv y construye un indice {rut_numero_str -> {razon_social, giro}}.

    El campo RutJuridica en el CSV es el numero sin DV (sin puntos).
    Cuando hay multiples filas para el mismo RUT, se usa la primera con Giro no vacio.

    Returns:
        dict: {rut_num (str) -> {"razon_social": str, "giro_principal": str}}
    """
    if not os.path.exists(csv_path):
        return {}

    try:
        df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    except Exception:
        return {}

    # Normalizar columnas
    df.columns = [c.strip() for c in df.columns]

    col_rut    = "RutJuridica"
    col_nombre = "EntidadAccion"
    col_giro   = "Giro"

    if col_rut not in df.columns:
        return {}

    df[col_rut] = df[col_rut].astype(str).str.strip()

    # Priorizar filas con giro no vacio
    if col_giro in df.columns:
        df[col_giro] = df[col_giro].astype(str).str.strip()
        con_giro    = df[df[col_giro].notna() & (df[col_giro] != "") & (df[col_giro] != "nan")]
        sin_giro    = df[~df.index.isin(con_giro.index)]
        df_ordenado = pd.concat([con_giro, sin_giro])
    else:
        df_ordenado = df

    indice: dict[str, dict] = {}
    for _, row in df_ordenado.iterrows():
        rut_num = str(row[col_rut]).strip()
        if not rut_num or rut_num == "nan":
            continue
        if rut_num in indice:
            continue  # ya tenemos la mejor fila para este RUT

        nombre = str(row.get(col_nombre, "")).strip()
        giro   = str(row.get(col_giro, "")).strip()

        indice[rut_num] = {
            "razon_social":   nombre if nombre and nombre != "nan" else None,
            "giro_principal": giro   if giro   and giro   != "nan" else None,
            "codigo_giro":    None,
            "fecha_inicio_act": None,
            "fuente":         "csvacciones_cplt",
        }

    return indice


# ---------------------------------------------------------------------------
# Consulta por empresa
# ---------------------------------------------------------------------------

def consultar_empresa_local(rut_raw: str, indice: dict) -> dict | None:
    """
    Busca los datos de una empresa en el indice local del CSV de acciones CPLT.

    Estrategia de busqueda (ambos formatos):
      1. Lookup directo (empresa_rut en DB ya NO tiene DV: "93007000")
      2. Si no, strip ultimo char por si viene con DV ("930070009" -> "93007000")

    Args:
        rut_raw: RUT de la empresa (con o sin DV, con o sin puntos/guion)
        indice:  Dict retornado por cargar_indice_csv()

    Returns:
        dict con razon_social, giro_principal, fuente
        o None si no se encontro en el CSV.
    """
    rut = rut_raw.strip().replace(".", "").replace("-", "")
    if not rut:
        return None

    # Intento 1: lookup directo (sin manipular — formato de participacion_societaria)
    resultado = indice.get(rut)
    if resultado:
        return resultado

    # Intento 2: strip ultimo char por si viene con DV concatenado
    if len(rut) > 1:
        resultado = indice.get(rut[:-1])
        if resultado:
            return resultado

    return None


# ---------------------------------------------------------------------------
# Funcion de compatibilidad (para no romper imports desde enriquecer_empresas)
# ---------------------------------------------------------------------------

def consultar_empresa_sii(rut: str, dv: str, indice: dict | None = None) -> dict | None:
    """
    Alias de consultar_empresa_local para compatibilidad con el pipeline.
    Si se pasa indice, busca ahi. Si no, carga el CSV automaticamente.

    NOTA: el parametro 'dv' se ignora — la busqueda es por numero de RUT.
    """
    if indice is None:
        indice = cargar_indice_csv()
    rut_completo = rut + (dv or "")
    return consultar_empresa_local(rut_completo, indice)


# ---------------------------------------------------------------------------
# CLI rapido para test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    csv = sys.argv[2] if len(sys.argv) > 2 else CSV_PATH
    rut_arg = sys.argv[1] if len(sys.argv) > 1 else "93007000"

    print(f"Cargando indice desde {csv} ...")
    indice = cargar_indice_csv(csv)
    print(f"  Empresas en indice: {len(indice)}")

    datos = consultar_empresa_local(rut_arg, indice)
    if datos:
        print(f"RUT {rut_arg}:")
        for k, v in datos.items():
            print(f"  {k}: {v}")
    else:
        print(f"RUT {rut_arg} no encontrado en CSV local.")
