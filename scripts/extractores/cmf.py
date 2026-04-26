"""
cmf.py - Extractor del portal publico de la CMF (Comision para el Mercado Financiero)
Detecta si funcionarios chilenos aparecen como directores/ejecutivos en empresas
reguladas por la CMF (SA abiertas, fondos, seguros, AFP).

URL verificada (2026-04-13):
  https://www.cmfchile.cl/institucional/mercados/detalle_reporte_ejecutivos.php
  Parametros: rut={numero_sin_dv}&mercado={V|O|S}
  - V = Mercado de Valores (SA abiertas, fondos mutuos)
  - O = Otras entidades (AFP, cooperativas reguladas)
  - S = Seguros (companias de seguros)

Estructura HTML verificada:
  - Tabla con id="Tabla"
  - Columnas en posicion fija: [0]=RUT Entidad, [1]=Razon Social, [2]=Cargo,
    [3]=Cargo Ejec. Principal, [4]=Fecha Nombramiento, [5]=Fecha Cesacion
  - Cuando no hay datos: fila unica con celda "Sin Informacion"

No requiere autenticacion. Rate limit: 1 segundo entre requests.

LIMITACION: Solo cubre empresas FISCALIZADAS por la CMF. Las SpA, SRL y SA cerradas
comunes NO aparecen aqui. Falsos negativos esperados para la mayoria de funcionarios.

Uso:
    from scripts.extractores.cmf import consultar_directorio_cmf
    resultados = consultar_directorio_cmf("5002817")  # solo numero, sin DV
"""

import time
import re
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

URL_CMF    = "https://www.cmfchile.cl/institucional/mercados/detalle_reporte_ejecutivos.php"
MERCADOS   = ["V", "O", "S"]
RATE_LIMIT = 1.0   # segundos entre requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9",
    "Referer": "https://www.cmfchile.cl/institucional/mercados/reporte_ejecutivos.php",
}

# Columnas en posicion fija (verificado contra HTML real)
COL_RUT_ENTIDAD       = 0
COL_NOMBRE_ENTIDAD    = 1
COL_CARGO             = 2
COL_CARGO_EJEC        = 3
COL_FECHA_NOMBRAMIENTO = 4
COL_FECHA_CESACION    = 5
NCOLS_ESPERADAS       = 6


# ---------------------------------------------------------------------------
# Helpers de RUT
# ---------------------------------------------------------------------------

def rut_numero(rut_raw: str) -> str | None:
    """
    Extrae el numero de RUT sin DV, sin puntos, sin guion.
    En candidato.rut el DV esta concatenado al final:
      "169646112" -> DV=2, numero="16964611"
      "930070009" -> DV=9, numero="93007000"
    """
    rut = rut_raw.strip().upper().replace(".", "").replace("-", "")
    if len(rut) < 2:
        return None
    return rut[:-1]  # quitar DV (siempre el ultimo char)


# ---------------------------------------------------------------------------
# Parseo HTML
# ---------------------------------------------------------------------------

def _parsear_tabla_cmf(html: str, mercado: str) -> list[dict]:
    """
    Parsea la respuesta HTML del portal CMF y extrae filas de la tabla#Tabla.
    Retorna lista de dicts o lista vacia si no hay datos.
    """
    soup = BeautifulSoup(html, "html.parser")

    tabla = soup.find("table", id="Tabla")
    if not tabla:
        return []

    tbody = tabla.find("tbody")
    if not tbody:
        return []

    resultados = []
    for fila in tbody.find_all("tr"):
        celdas = [td.get_text(strip=True) for td in fila.find_all("td")]

        # Caso "Sin Informacion" — la CMF retorna una sola celda cuando no hay datos
        if len(celdas) == 1:
            continue

        # Verificar que tiene el numero correcto de columnas
        if len(celdas) < NCOLS_ESPERADAS:
            continue

        # Filtrar filas vacias o con solo encabezados repetidos
        rut_entidad = celdas[COL_RUT_ENTIDAD].strip()
        if not rut_entidad or not rut_entidad.isdigit():
            continue

        resultados.append({
            "rut_entidad":         rut_entidad,
            "nombre_entidad":      celdas[COL_NOMBRE_ENTIDAD] or None,
            "cargo":               celdas[COL_CARGO] or None,
            "cargo_ejec":          celdas[COL_CARGO_EJEC] or None,
            "fecha_nombramiento":  _parsear_fecha(celdas[COL_FECHA_NOMBRAMIENTO]),
            "fecha_cesacion":      _parsear_fecha(celdas[COL_FECHA_CESACION]),
            "mercado":             mercado,
        })

    return resultados


def _parsear_fecha(texto: str | None) -> str | None:
    """Convierte DD/MM/YYYY a YYYY-MM-DD. Retorna None si no es una fecha valida."""
    if not texto:
        return None
    texto = texto.strip()
    if not texto or texto in ("-", "N/A", "Vigente", "VIGENTE"):
        return None
    # DD/MM/YYYY
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", texto)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    # DD-MM-YYYY
    m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", texto)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    # YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", texto)
    if m:
        return texto[:10]
    return None


# ---------------------------------------------------------------------------
# Consulta principal
# ---------------------------------------------------------------------------

def consultar_directorio_cmf(
    rut_raw: str,
    mercados: list[str] | None = None
) -> list[dict]:
    """
    Busca si una persona aparece como director/ejecutivo en empresas CMF.

    Args:
        rut_raw: RUT de la persona. Acepta formatos:
                   "169646112"  (con DV concatenado, como esta en candidato.rut)
                   "16964611"   (sin DV, como lo reporta la CMF)
                   "16.964.611-2" (con puntos y guion)
        mercados: lista de mercados ["V","O","S"] (default: los 3)

    Returns:
        Lista de dicts con:
            rut_entidad, nombre_entidad, cargo, cargo_ejec,
            fecha_nombramiento, fecha_cesacion, mercado
        Lista vacia si no aparece en ningun mercado CMF.
    """
    if mercados is None:
        mercados = MERCADOS

    num = rut_numero(rut_raw)
    if not num:
        return []

    resultados = []
    session = requests.Session()

    for mercado in mercados:
        try:
            resp = session.get(
                URL_CMF,
                params={"rut": num, "mercado": mercado},
                headers=HEADERS,
                timeout=20
            )
            resp.raise_for_status()
            filas = _parsear_tabla_cmf(resp.text, mercado)
            resultados.extend(filas)

        except requests.RequestException:
            pass  # No retryar — el caller maneja errores via checkpoint
        except Exception:
            pass

        time.sleep(RATE_LIMIT)

    return resultados


# ---------------------------------------------------------------------------
# CLI rapido para test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # Ejemplo: python scripts/extractores/cmf.py 169646112
    # (RUT de Luis Fernando Sanchez Ossa segun CIAP — caso AUTOLOBBY conocido)
    rut_arg = sys.argv[1] if len(sys.argv) > 1 else "5002817"
    print(f"Consultando CMF para RUT: {rut_arg} (numero sin DV: {rut_numero(rut_arg)})")
    resultados = consultar_directorio_cmf(rut_arg)
    if resultados:
        for r in resultados:
            print(f"  [{r['mercado']}] {r['rut_entidad']} | {r['nombre_entidad']} "
                  f"| {r['cargo']} | desde: {r['fecha_nombramiento']} "
                  f"hasta: {r['fecha_cesacion']}")
    else:
        print("No aparece como director/ejecutivo en empresas CMF.")
