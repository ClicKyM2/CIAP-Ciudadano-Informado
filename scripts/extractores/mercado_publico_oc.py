"""
mercado_publico_oc.py — Descarga masiva de Órdenes de Compra desde Azure Blob Storage
URL pública (sin ticket): https://transparenciachc.blob.core.windows.net/oc-da/{año}-{mes}.zip
Cada ZIP contiene un CSV con todas las OC del mes (~621MB descomprimido).
Este módulo descarga el ZIP en streaming, lo descomprime línea a línea,
y filtra solo las filas donde el proveedor es una empresa vinculada a candidatos.
"""

import io
import re
import csv
import os
import tempfile
import zipfile
import requests
from datetime import datetime

BASE_URL = "https://transparenciachc.blob.core.windows.net/oc-da/{anio}-{mes}.zip"
TIMEOUT_DOWNLOAD = 300  # 5 minutos para descargar ~87MB


def normalizar_rut(rut_raw):
    """Normaliza RUT chileno: elimina puntos, guiones y espacios, uppercase."""
    return re.sub(r'[.\-\s]', '', str(rut_raw)).upper().strip()


def url_disponible(anio, mes):
    """Verifica si existe el ZIP para ese mes (HEAD request)."""
    url = BASE_URL.format(anio=anio, mes=mes)
    try:
        resp = requests.head(url, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def descargar_y_filtrar(anio, mes, ruts_candidatos, verbose=True):
    """
    Descarga el ZIP mensual de OC y filtra filas donde el proveedor está en ruts_candidatos.

    Args:
        anio (int): Año del mes a procesar.
        mes (int): Mes a procesar (1-12).
        ruts_candidatos (dict): {rut_normalizado: candidato_id}
        verbose (bool): Imprimir progreso.

    Yields:
        dict con campos normalizados de la OC + candidato_id.
    """
    url = BASE_URL.format(anio=anio, mes=mes)
    if verbose:
        print(f"  Descargando {anio}-{mes}: {url}")

    # Descargar ZIP a archivo temporal
    tmp_path = None
    try:
        resp = requests.get(url, stream=True, timeout=TIMEOUT_DOWNLOAD)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp_path = tmp.name
            descargado = 0
            for chunk in resp.iter_content(chunk_size=65536):
                tmp.write(chunk)
                descargado += len(chunk)
            if verbose:
                print(f"    ZIP descargado: {descargado / 1024 / 1024:.1f} MB")

        # Leer CSV en streaming dentro del ZIP
        encontrados = 0
        procesados = 0
        with zipfile.ZipFile(tmp_path) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as csv_file:
                reader = csv.DictReader(
                    io.TextIOWrapper(csv_file, encoding='latin-1'),
                    delimiter=';'
                )
                for row in reader:
                    procesados += 1
                    rut_raw = row.get('RutSucursal', '') or ''
                    rut_norm = normalizar_rut(rut_raw)
                    # El CSV trae RUT con DV (ej: "90.299.000-3" → "902990003")
                    # La DB almacena sin DV (ej: "90299000").
                    # Intentar match con DV completo y luego sin DV (strip último char).
                    rut_sin_dv = rut_norm[:-1] if rut_norm else ''
                    candidato_id = ruts_candidatos.get(rut_norm) or ruts_candidatos.get(rut_sin_dv)
                    if candidato_id:
                        encontrados += 1
                        yield _parsear_fila(row, anio, mes, candidato_id)

                    if verbose and procesados % 500000 == 0:
                        print(f"    Procesadas {procesados:,} filas, {encontrados} coincidencias...")

        if verbose:
            print(f"    Total: {procesados:,} filas procesadas, {encontrados} OCs relevantes encontradas")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            if verbose:
                print(f"    No disponible: {anio}-{mes}")
        else:
            print(f"    Error HTTP {e.response.status_code}: {e}")
    except Exception as e:
        print(f"    Error procesando {anio}-{mes}: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _parsear_fila(row, anio, mes, candidato_id):
    """Convierte una fila del CSV al formato de la tabla orden_compra."""
    def safe_int(val):
        try:
            v = str(val).strip().replace('.', '').replace(',', '')
            return int(float(v)) if v else None
        except (ValueError, TypeError):
            return None

    def safe_date(val):
        if not val or str(val).strip() in ('', '0000-00-00', 'null', 'NULL'):
            return None
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                return datetime.strptime(str(val).strip()[:19], fmt).date().isoformat()
            except ValueError:
                continue
        return None

    return {
        'codigo':            str(row.get('Codigo', '') or '').strip()[:50],
        'nombre':            str(row.get('Nombre', '') or '').strip(),
        'estado':            str(row.get('Estado', '') or '').strip()[:100],
        'fecha_creacion':    safe_date(row.get('FechaCreacion')),
        'monto_pesos':       safe_int(row.get('MontoTotalOC_PesosChilenos')),
        'rut_organismo':     normalizar_rut(row.get('RutUnidadCompra', '') or '')[:15],
        'nombre_organismo':  str(row.get('OrganismoPublico', '') or '').strip(),
        'rut_proveedor':     normalizar_rut(row.get('RutSucursal', '') or '')[:15],
        'nombre_proveedor':  str(row.get('NombreProveedor', '') or '').strip(),
        'codigo_licitacion': str(row.get('CodigoLicitacion', '') or '').strip()[:50] or None,
        'link':              str(row.get('Link', '') or '').strip() or None,
        'anio':              anio,
        'mes':               mes,
        'candidato_id':      candidato_id,
    }


def meses_disponibles(anio_inicio=2022):
    """Retorna lista de (anio, mes) disponibles hasta el mes actual."""
    hoy = datetime.now()
    resultado = []
    for anio in range(anio_inicio, hoy.year + 1):
        for mes in range(1, 13):
            if anio == hoy.year and mes > hoy.month:
                break
            resultado.append((anio, mes))
    return resultado
