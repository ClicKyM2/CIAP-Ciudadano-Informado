"""
mercado_publico_licitaciones.py — Extractor de licitaciones ChileCompra (sin ticket)

Dos modos segun disponibilidad:
  - BULK: ZIP mensual desde ocds.blob.core.windows.net/ocds/yyyymm.zip
          (disponible 2021-01 a 2022-04 y algunos meses de 2023)
  - API:  OCDS list + award por codigo con threading
          (para meses sin bulk disponible)

El ZIP contiene un JSON OCDS por licitacion. Ambos modos usan el mismo parser.
"""

import re
import io
import os
import json
import time
import tempfile
import zipfile
import threading
import requests
from queue import Queue, Empty
from datetime import datetime

BULK_URL  = "https://ocds.blob.core.windows.net/ocds/{yyyymm}.zip"
LIST_URL  = "https://api.mercadopublico.cl/APISOCDS/OCDS/listaOCDSAgnoMes/{anio}/{mes}/{desde}/{hasta}"
AWARD_URL = "https://api.mercadopublico.cl/APISOCDS/OCDS/award/{codigo}"
PAGE_SIZE   = 999
TIMEOUT     = 45
NUM_WORKERS = 10


def normalizar_rut(rut_raw):
    return re.sub(r'[.\-\s]', '', str(rut_raw or '')).upper().strip()


def _get_json(url, reintentos=3):
    for intento in range(reintentos):
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            if resp.status_code in (401, 403):
                raise PermissionError(f"API requiere ticket (HTTP {resp.status_code}).")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except PermissionError:
            raise
        except Exception as e:
            if intento < reintentos - 1:
                time.sleep(1.5 ** intento)
            else:
                return None


def bulk_disponible(anio, mes):
    yyyymm = f"{anio}{mes:02d}"
    url = BULK_URL.format(yyyymm=yyyymm)
    try:
        r = requests.head(url, timeout=10)
        return r.status_code == 200, url
    except Exception:
        return False, url


# ---------------------------------------------------------------------------
# Parser OCDS (compartido entre bulk y API)
# ---------------------------------------------------------------------------

def _extraer_matches(data_ocds, ruts_candidatos):
    """
    Dado un dict OCDS (release package, record package, o release directo),
    retorna lista de matches: {rut_adj, nombre_adj, monto_adj, fecha_adj,
                                buyer_rut, buyer_nombre, candidato_id, codigo}.

    Soporta tres formatos:
      - releases[]           → API award endpoint
      - records[].compiledRelease → bulk ZIP (record package)
      - release directo      → JSON individual sin wrapper
    """
    resultados = []

    # Construir lista de releases a procesar
    releases = list(data_ocds.get('releases') or [])

    # Record package (bulk ZIP): extraer compiledRelease de cada record
    for record in (data_ocds.get('records') or []):
        compiled = record.get('compiledRelease')
        if compiled:
            releases.append(compiled)

    # Release directo sin wrapper
    if not releases and 'tender' in data_ocds:
        releases = [data_ocds]

    for release in releases:
        parties = release.get('parties') or []
        awards  = release.get('awards') or []
        tender  = release.get('tender') or {}

        codigo = str(tender.get('id') or release.get('ocid') or '').replace('ocds-70d2nz-', '').strip()[:50]

        parties_by_id = {str(p.get('id') or ''): p for p in parties}

        buyer_rut, buyer_nombre = '', ''
        for p in parties:
            if 'buyer' in (p.get('roles') or []) or 'procuringEntity' in (p.get('roles') or []):
                ident = p.get('identifier') or {}
                if ident.get('scheme') == 'CL-RUT':
                    buyer_rut = normalizar_rut(ident.get('id', ''))
                buyer_nombre = str(p.get('name') or '').split('|')[0].strip()[:300]
                break

        for award in awards:
            status = str(award.get('status', '')).lower()
            if status not in ('active', 'activo', ''):
                continue
            monto = None
            try:
                raw = float(str((award.get('value') or {}).get('amount') or 0).replace(',', ''))
                # Umbral: ~500 billion CLP — montos mayores son datos corruptos en fuente OCDS
                if 0 < raw <= 500_000_000_000:
                    monto = int(raw)
            except Exception:
                pass
            fecha_adj = str(award.get('date') or '')[:10] or None

            for supplier in (award.get('suppliers') or []):
                sid = str(supplier.get('id') or '').strip()
                party = parties_by_id.get(sid) or {}
                ident = party.get('identifier') or {}
                if ident.get('scheme') == 'CL-RUT':
                    rut_norm = normalizar_rut(ident.get('id', ''))
                else:
                    rut_norm = normalizar_rut(sid)
                rut_sin_dv = rut_norm[:-1] if rut_norm else ''
                nombre_adj = str(party.get('name') or supplier.get('name') or '').split('|')[0].strip()[:300]

                candidato_id = ruts_candidatos.get(rut_norm) or ruts_candidatos.get(rut_sin_dv)
                if candidato_id:
                    resultados.append({
                        'codigo': codigo,
                        'rut_adj': rut_norm,
                        'nombre_adj': nombre_adj,
                        'monto_adj': monto,
                        'fecha_adj': fecha_adj,
                        'buyer_rut': buyer_rut,
                        'buyer_nombre': buyer_nombre,
                        'candidato_id': candidato_id,
                    })
    return resultados


def _parsear_match(match, anio, mes):
    codigo = match.get('codigo', '')
    return {
        'codigo':              codigo[:50],
        'nombre':              None,
        'estado':              'adjudicada',
        'fecha_publicacion':   None,
        'fecha_cierre':        None,
        'fecha_adjudicacion':  match.get('fecha_adj'),
        'monto_estimado':      None,
        'monto_adjudicado':    match.get('monto_adj'),
        'rut_organismo':       match.get('buyer_rut', '')[:15],
        'nombre_organismo':    match.get('buyer_nombre') or None,
        'rut_adjudicatario':   match.get('rut_adj', '')[:15],
        'nombre_adjudicatario': match.get('nombre_adj') or None,
        'link': f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?qs={codigo}" if codigo else None,
        'anio':                anio,
        'mes':                 mes,
        'candidato_id':        match.get('candidato_id'),
    }


# ---------------------------------------------------------------------------
# Modo BULK (ZIP)
# ---------------------------------------------------------------------------

def _descargar_bulk(anio, mes, ruts_candidatos, verbose=True):
    yyyymm = f"{anio}{mes:02d}"
    url = BULK_URL.format(yyyymm=yyyymm)
    if verbose:
        print(f"  Descargando bulk ZIP {yyyymm}: {url}")

    tmp_path = None
    try:
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp_path = tmp.name
            descargado = 0
            for chunk in resp.iter_content(65536):
                tmp.write(chunk)
                descargado += len(chunk)
        if verbose:
            print(f"    Descargado: {descargado / 1024 / 1024:.0f} MB")

        encontrados = procesados = 0
        with zipfile.ZipFile(tmp_path) as zf:
            nombres = zf.namelist()
            if verbose:
                print(f"    {len(nombres):,} archivos JSON en el ZIP")
            for nombre in nombres:
                procesados += 1
                try:
                    with zf.open(nombre) as f:
                        data = json.load(f)
                    matches = _extraer_matches(data, ruts_candidatos)
                    for m in matches:
                        encontrados += 1
                        yield _parsear_match(m, anio, mes)
                except Exception:
                    pass
                if verbose and procesados % 10000 == 0:
                    print(f"    {procesados:,}/{len(nombres):,} procesados, {encontrados} relevantes...")

        if verbose:
            print(f"    Completado: {procesados:,} licitaciones, {encontrados} relevantes")

    except Exception as e:
        print(f"  Error bulk {yyyymm}: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Modo API (OCDS list + award por codigo con threading)
# ---------------------------------------------------------------------------

def _worker_api(queue_in, queue_out, ruts_candidatos, stop_event):
    while not stop_event.is_set():
        try:
            codigo = queue_in.get(timeout=2)
        except Empty:
            continue
        try:
            data = _get_json(AWARD_URL.format(codigo=codigo))
            if data:
                for m in _extraer_matches(data, ruts_candidatos):
                    if not m.get('codigo'):
                        m['codigo'] = codigo
                    queue_out.put(m)
        except Exception:
            pass
        finally:
            queue_in.task_done()


def _descargar_api(anio, mes, ruts_candidatos, verbose=True):
    # Paginar lista de codigos
    codigos = []
    offset = 0
    total = None

    while True:
        data = _get_json(LIST_URL.format(anio=anio, mes=mes, desde=offset, hasta=offset + PAGE_SIZE - 1))
        if not data:
            break
        pagination = data.get('pagination') or {}
        if total is None:
            total = int(pagination.get('total') or 0)
            if verbose:
                print(f"  {anio}-{mes:02d}: {total:,} licitaciones via API")
        items = data.get('data') or []
        codigos += [item['ocid'].replace('ocds-70d2nz-', '') for item in items if item.get('ocid')]
        offset += PAGE_SIZE
        if offset >= total:
            break
        time.sleep(0.3)

    if not codigos:
        return

    if verbose:
        print(f"    {len(codigos):,} codigos, consultando awards con {NUM_WORKERS} threads...")

    queue_in  = Queue()
    queue_out = Queue()
    stop_event = threading.Event()

    for c in codigos:
        queue_in.put(c)

    workers = []
    for _ in range(NUM_WORKERS):
        t = threading.Thread(target=_worker_api, args=(queue_in, queue_out, ruts_candidatos, stop_event), daemon=True)
        t.start()
        workers.append(t)

    total_codigos = len(codigos)
    encontrados = 0

    while not queue_in.empty() or queue_in.unfinished_tasks > 0:
        while not queue_out.empty():
            match = queue_out.get_nowait()
            encontrados += 1
            yield _parsear_match(match, anio, mes)
        time.sleep(0.5)

    queue_in.join()
    stop_event.set()

    while not queue_out.empty():
        match = queue_out.get_nowait()
        encontrados += 1
        yield _parsear_match(match, anio, mes)

    if verbose:
        print(f"    Completado: {total_codigos:,} revisadas, {encontrados} relevantes")


# ---------------------------------------------------------------------------
# Interfaz publica
# ---------------------------------------------------------------------------

def descargar_y_filtrar(anio, mes, ruts_candidatos, verbose=True):
    """
    Descarga licitaciones del mes y filtra adjudicadas a empresas de candidatos.
    Usa bulk ZIP si esta disponible, API OCDS si no.

    Yields: dict con campos normalizados + candidato_id.
    """
    disponible, url = bulk_disponible(anio, mes)
    if disponible:
        if verbose:
            print(f"  Modo: BULK ZIP")
        yield from _descargar_bulk(anio, mes, ruts_candidatos, verbose)
    else:
        if verbose:
            print(f"  Modo: API OCDS (no hay bulk para {anio}-{mes:02d})")
        yield from _descargar_api(anio, mes, ruts_candidatos, verbose)


def meses_disponibles(anio_inicio=2021):
    hoy = datetime.now()
    resultado = []
    for anio in range(anio_inicio, hoy.year + 1):
        for mes in range(1, 13):
            if anio == hoy.year and mes > hoy.month:
                break
            resultado.append((anio, mes))
    return resultado
