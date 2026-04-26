"""
bcn.py — Extractor de proyectos de ley BCN para CIAP

API: https://www.bcn.cl/laborparlamentaria/facetas-buscador-avanzado
     (motor Solr interno del portal Labor Parlamentaria)

Flujo:
  1. Por cada diputado: buscar su ID BCN via SPARQL foaf:name (rapido, indexado)
  2. Llamar a facetas-buscador-avanzado con ese ID para obtener sus mociones
  3. Extraer boletin con regex de descripcion_debate
"""

import re
import time
import unicodedata
import requests

SPARQL_ENDPOINT  = "https://datos.bcn.cl/sparql"
FACETAS_URL      = "https://www.bcn.cl/laborparlamentaria/facetas-buscador-avanzado"
TIPO_MOCION      = 915   # id_tipo_participacion = Mociones (proyectos de ley)
PAGE_ROWS        = 200   # filas por peticion a Solr
TIMEOUT_SPARQL   = 20
TIMEOUT_FACETAS  = 30

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CIAP-BCN/1.0)",
    "Accept":     "application/json",
}

RE_BOLETIN = re.compile(r'BOLET[ÍI]N\s*N[°º\.]\s*(\d{3,6}-\d{2})', re.IGNORECASE)


def _normalizar(texto):
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_tilde = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tilde.upper().strip()


# ---------------------------------------------------------------------------
# Paso 1: buscar ID BCN de una persona por nombre (SPARQL foaf:name)
# ---------------------------------------------------------------------------

def buscar_id_bcn(nombre, reintentos=3):
    """
    Busca el ID numerico BCN de un parlamentario por su nombre normalizado.
    Retorna int (ID) o None si no encuentra o timeout.
    Intenta primero con el primer apellido (ultima palabra del nombre compuesto),
    luego con el primer nombre, para maximizar cobertura.
    """
    nombre_norm = _normalizar(nombre)
    palabras = nombre_norm.split()
    # Intentar con apellido (ultima palabra) y primer nombre por separado
    candidatos_filtro = []
    if len(palabras) >= 1:
        candidatos_filtro.append(palabras[-1])   # apellido paterno (ultima palabra)
    if len(palabras) >= 2:
        candidatos_filtro.append(palabras[0])    # primer nombre
    # Eliminar palabras cortas/comunes que no discriminan
    STOPWORDS = {"DE", "DEL", "LA", "LAS", "LOS", "DON", "Y", "A"}
    candidatos_filtro = [p for p in candidatos_filtro if p not in STOPWORDS and len(p) > 2]

    for filtro in candidatos_filtro:
        query = f"""
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX bcnbio: <http://datos.bcn.cl/ontologies/bcn-biographies#>
SELECT ?persona ?nombre ?dipid
WHERE {{
  ?persona foaf:name ?nombre .
  OPTIONAL {{ ?persona bcnbio:idCamaraDeDiputados ?dipid }}
  FILTER(CONTAINS(UCASE(?nombre), "{filtro}"))
}}
LIMIT 30
"""
        for i in range(reintentos):
            try:
                r = requests.get(
                    SPARQL_ENDPOINT,
                    params={"query": query, "format": "json"},
                    headers={"Accept": "application/sparql-results+json"},
                    timeout=TIMEOUT_SPARQL,
                )
                r.raise_for_status()
                bindings = r.json()["results"]["bindings"]
                # Buscar la mejor coincidencia por similitud de nombre completo
                for b in bindings:
                    nombre_bcn = _normalizar(b.get("nombre", {}).get("value", ""))
                    if _similitud_suficiente(nombre_norm, nombre_bcn):
                        uri = b["persona"]["value"]
                        bcn_id = int(uri.split("/")[-1])
                        return bcn_id
                break  # no error, pero no encontrado con este filtro — probar el siguiente
            except Exception:
                if i < reintentos - 1:
                    time.sleep(1.5 ** i)
    return None


def _similitud_suficiente(a, b):
    """
    True si hay suficiente coincidencia de palabras clave entre los nombres a y b.
    - 2+ palabras en comun: match seguro
    - 1 palabra en comun solo si es un apellido largo (>= 5 chars) — evita falsos positivos
    """
    STOPWORDS = {"DE", "DEL", "LA", "LAS", "LOS", "DON", "DONA", "Y", "A"}
    palabras_a = set(a.split()) - STOPWORDS
    palabras_b = set(b.split()) - STOPWORDS
    comunes = palabras_a & palabras_b
    if len(comunes) >= 2:
        return True
    if len(comunes) == 1:
        palabra = next(iter(comunes))
        return len(palabra) >= 5  # apellido largo reduce ambiguedad
    return False


# ---------------------------------------------------------------------------
# Paso 2: obtener mociones de una persona por ID BCN
# ---------------------------------------------------------------------------

def obtener_mociones(bcn_id, verbose=False):
    """
    Llama a facetas-buscador-avanzado y retorna lista de dicts:
      {boletin, titulo, fecha, tipo, camara, coautores: [{id, nombre}]}
    """
    resultados = []
    start = 0

    while True:
        try:
            r = requests.get(
                FACETAS_URL,
                params={
                    "personas":              bcn_id,
                    "id_tipo_participacion": TIPO_MOCION,
                    "start":                 start,
                    "rows":                  PAGE_ROWS,
                    "sort":                  "date",
                },
                headers=_HEADERS,
                timeout=TIMEOUT_FACETAS,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            if verbose:
                print(f"    ERROR facetas persona={bcn_id} start={start}: {e}")
            break

        docs = data.get("docs") or []
        total = int(data.get("numFound") or 0)

        for doc in docs:
            # Usar campo boletin directo de Solr; fallback a regex sobre texto
            boletin = doc.get("boletin") or ""
            if not boletin:
                descripcion = doc.get("descripcion_debate") or doc.get("texto") or ""
                m = RE_BOLETIN.search(descripcion)
                if not m:
                    continue
                boletin = m.group(1)

            titulo = (
                doc.get("titulo")
                or doc.get("dc_title")
                or _limpiar_titulo(doc.get("descripcion_debate") or doc.get("texto") or "")
            )

            coautores = [
                {"id": p["id"], "nombre": p["nombre"]}
                for p in (doc.get("personas_obj") or [])
                if p.get("id") != bcn_id
            ]

            resultados.append({
                "boletin":        boletin,
                "titulo":         titulo,
                "fecha":          (doc.get("fecha") or "")[:10] or None,
                "tipo_iniciativa": "Mocion",
                "camara_origen":  doc.get("descripcion_camara") or "Camara de Diputados",
                "legislatura":    doc.get("numero_legislatura"),
                "coautores":      coautores,
            })

        start += PAGE_ROWS
        if start >= total:
            break
        time.sleep(0.5)

    if verbose:
        print(f"    BCN ID {bcn_id}: {len(resultados)} mociones")
    return resultados


def _limpiar_titulo(descripcion):
    """
    Extrae el titulo del proyecto del texto de descripcion_debate.
    El titulo esta entre comillas: 'que "Titulo del proyecto"'
    """
    m = re.search(r'que\s*["“”]([^"“”]+)["“”]', descripcion)
    if m:
        return m.group(1).strip()
    # Fallback: tomar desde 'que' hasta el boletin
    m2 = re.search(r'que (.+?)[\.\s]*BOLET', descripcion, re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return descripcion[:200]
