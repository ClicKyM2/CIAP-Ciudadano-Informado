"""
ingesta_financiamiento_servel.py — Importa financiamiento electoral 2024 desde SERVEL
Ejecutar desde la raiz: python scripts/pipeline/ingesta_financiamiento_servel.py

Fuente: Reporte_Ingresos_Gastos_Definitivas2024.xlsx (descargado automaticamente)
Tablas creadas:
  - financiamiento_electoral  — totales por candidato (ingresos, gastos, aportes privados)
  - donante_electoral         — transacciones individuales (donante, monto, fecha)

Alerta nueva generada: DONANTE_PROVEEDOR
  Si el RUT de un donante aparece en participacion_societaria o empresa_enriquecida
  de otro candidato que tambien recibio OCs → posible conflicto de interes.
"""

import os, sys, re, unicodedata, urllib.request
import psycopg2
from dotenv import load_dotenv

load_dotenv()

EXCEL_URL  = 'https://www.servel.cl/wp-content/uploads/2025/08/Reporte_Ingresos_Gastos_Definitivas2024.xlsx'
EXCEL_PATH = 'data/Reporte_Ingresos_Gastos_Definitivas2024.xlsx'
SHEET_NAME = 'INGRESOS Y GASTOS'
HEADER_ROW = 11   # fila 1-indexed donde estan los headers
DATA_START  = 12  # primera fila de datos

# Mapeo de cargo SERVEL → cargo en la DB
CARGO_MAP = {
    'ALCALDE':             'ALCALDE',
    'CONCEJAL':            'CONCEJAL',
    'GOBERNADOR REGIONAL': 'GOBERNADOR REGIONAL',
    'CONSEJERO REGIONAL':  'CONSEJERO REGIONAL',
    'CORE':                'CONSEJERO REGIONAL',
}


def normalizar(texto):
    if not texto:
        return ''
    txt = unicodedata.normalize('NFD', str(texto).upper())
    txt = ''.join(c for c in txt if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', txt).strip()


def descargar_excel():
    if os.path.exists(EXCEL_PATH) and os.path.getsize(EXCEL_PATH) > 1_000_000:
        print(f'[OK] Excel ya existe ({os.path.getsize(EXCEL_PATH):,} bytes)')
        return
    print(f'[..] Descargando Excel desde SERVEL (~60MB)...')
    req = urllib.request.Request(EXCEL_URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as r, open(EXCEL_PATH, 'wb') as f:
        f.write(r.read())
    print(f'[OK] Descargado: {os.path.getsize(EXCEL_PATH):,} bytes')


def crear_tablas(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS financiamiento_electoral (
            id               SERIAL PRIMARY KEY,
            candidato_id     INTEGER REFERENCES candidato(id),
            nombre_servel    TEXT NOT NULL,
            cargo_servel     VARCHAR(50),
            territorio       VARCHAR(100),
            region           VARCHAR(100),
            partido          TEXT,
            pacto            TEXT,
            total_ingresos   BIGINT DEFAULT 0,
            total_gastos     BIGINT DEFAULT 0,
            n_transacciones  INTEGER DEFAULT 0,
            fuente           VARCHAR(30) DEFAULT 'SERVEL_2024',
            UNIQUE(nombre_servel, cargo_servel, territorio)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS donante_electoral (
            id               SERIAL PRIMARY KEY,
            financiamiento_id INTEGER REFERENCES financiamiento_electoral(id),
            candidato_id     INTEGER REFERENCES candidato(id),
            tipo             VARCHAR(10),  -- INGRESOS / GASTO
            rut_donante      VARCHAR(15),
            nombre_donante   TEXT,
            monto            BIGINT,
            fecha            DATE,
            descripcion      TEXT,
            tipo_documento   VARCHAR(10)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_donante_rut ON donante_electoral(rut_donante)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_donante_candidato ON donante_electoral(candidato_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fin_candidato ON financiamiento_electoral(candidato_id)")


def parsear_monto(valor):
    if valor is None:
        return 0
    try:
        return int(str(valor).replace('.', '').replace(',', '').strip())
    except (ValueError, AttributeError):
        return 0


def parsear_fecha(valor):
    if not valor:
        return None
    s = str(valor).strip()
    # Formato DD-MM-YYYY
    m = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', s)
    if m:
        return f'{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}'
    # Ya en YYYY-MM-DD
    m2 = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m2:
        return s[:10]
    return None


def leer_excel():
    """Lee la hoja INGRESOS Y GASTOS y devuelve lista de dicts."""
    try:
        import openpyxl
    except ImportError:
        print('[ERR] openpyxl no instalado. Ejecuta: pip install openpyxl')
        sys.exit(1)

    print(f'[..] Leyendo Excel (puede tardar 2-3 min para 352K filas)...')
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    ws = wb[SHEET_NAME]

    filas = []
    for i, row in enumerate(ws.iter_rows(min_row=DATA_START, values_only=True), DATA_START):
        tipo_cuenta = row[0]
        if tipo_cuenta not in ('Candidato', 'CANDIDATO', 'candidato'):
            continue  # saltar filas de partido u otras

        filas.append({
            'tipo':            str(row[1] or '').strip().upper(),   # INGRESOS / GASTO
            'eleccion':        str(row[2] or '').strip().upper(),   # ALCALDE / CONCEJAL / ...
            'region':          str(row[3] or '').strip(),
            'territorio':      str(row[4] or '').strip().upper(),   # comuna
            'nombre_cand':     str(row[5] or '').strip().upper(),   # nombre candidato
            'partido':         str(row[6] or '').strip(),
            'pacto':           str(row[7] or '').strip(),
            'rut_donante':     str(row[9] or '').strip() if row[9] else None,
            'dv_donante':      str(row[10] or '').strip() if row[10] else None,
            'nombre_donante':  str(row[11] or '').strip() if row[11] else None,
            'fecha':           parsear_fecha(row[12]),
            'monto':           parsear_monto(row[13]),
            'tipo_doc':        str(row[14] or '').strip() if row[14] else None,
            'descripcion':     str(row[19] or '').strip() if row[19] else None,
        })

        if i % 50000 == 0:
            print(f'   {i:,} filas leidas...')

    wb.close()
    print(f'[OK] {len(filas):,} transacciones de candidatos leidas')
    return filas


def cargar_candidatos(cur):
    """Carga diccionario (nombre_normalizado, cargo, territorio) -> candidato_id."""
    cur.execute("""
        SELECT c.id, c.nombre_limpio, c.nombres, ca.nombre AS cargo, c.comuna
        FROM candidato c
        LEFT JOIN cargo ca ON ca.id = c.cargo_id
    """)
    indice = {}
    for cid, nombre_limpio, nombres, cargo, comuna in cur.fetchall():
        nombre_norm = normalizar(nombre_limpio or nombres or '')
        cargo_norm  = normalizar(cargo or '')
        comuna_norm = normalizar(comuna or '')
        if nombre_norm:
            # clave completa
            indice[(nombre_norm, cargo_norm, comuna_norm)] = cid
            # sin cargo (fallback)
            indice[(nombre_norm, '', comuna_norm)] = cid
            # solo nombre (fallback de ultimo recurso)
            if nombre_norm not in indice:
                indice[nombre_norm] = cid
    return indice


def buscar_candidato(indice, nombre_servel, cargo_servel, territorio):
    nombre_n  = normalizar(nombre_servel)
    cargo_n   = normalizar(CARGO_MAP.get(cargo_servel, cargo_servel))
    territ_n  = normalizar(territorio)

    # 1. Match exacto
    cid = indice.get((nombre_n, cargo_n, territ_n))
    if cid: return cid
    # 2. Sin cargo
    cid = indice.get((nombre_n, '', territ_n))
    if cid: return cid
    # 3. Solo nombre
    cid = indice.get(nombre_n)
    return cid


def main():
    descargar_excel()

    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'ciudadano_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', '5432'),
        client_encoding='utf-8'
    )
    cur = conn.cursor()

    print('[..] Creando tablas...')
    crear_tablas(cur)
    conn.commit()

    print('[..] Cargando indice de candidatos...')
    indice = cargar_candidatos(cur)

    filas = leer_excel()

    # Agrupar por candidato (nombre, cargo, territorio)
    print('[..] Agrupando por candidato...')
    grupos = {}  # (nombre_cand, eleccion, territorio) -> {ingresos, gastos, txs, partido, pacto, region}
    for f in filas:
        key = (f['nombre_cand'], f['eleccion'], f['territorio'])
        if key not in grupos:
            grupos[key] = {
                'total_ingresos': 0, 'total_gastos': 0, 'n_txs': 0,
                'partido': f['partido'], 'pacto': f['pacto'], 'region': f['region']
            }
        g = grupos[key]
        if f['tipo'] == 'INGRESOS':
            g['total_ingresos'] += f['monto']
        elif f['tipo'] == 'GASTO':
            g['total_gastos'] += f['monto']
        g['n_txs'] += 1

    print(f'[OK] {len(grupos):,} candidatos/entidades distintos en el Excel')

    # Insertar financiamiento_electoral
    print('[..] Insertando financiamiento_electoral...')
    fin_id_map = {}  # key -> financiamiento_id
    insertados = 0
    sin_match  = 0

    for key, g in grupos.items():
        nombre_cand, eleccion, territorio = key
        cid = buscar_candidato(indice, nombre_cand, eleccion, territorio)
        if not cid:
            sin_match += 1

        cur.execute("""
            INSERT INTO financiamiento_electoral
                (candidato_id, nombre_servel, cargo_servel, territorio, region, partido, pacto,
                 total_ingresos, total_gastos, n_transacciones)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (nombre_servel, cargo_servel, territorio) DO UPDATE SET
                candidato_id   = EXCLUDED.candidato_id,
                total_ingresos = EXCLUDED.total_ingresos,
                total_gastos   = EXCLUDED.total_gastos,
                n_transacciones= EXCLUDED.n_transacciones
            RETURNING id
        """, (cid, nombre_cand, eleccion, territorio, g['region'],
              g['partido'], g['pacto'], g['total_ingresos'], g['total_gastos'], g['n_txs']))
        fin_id = cur.fetchone()[0]
        fin_id_map[key] = (fin_id, cid)
        insertados += 1

    conn.commit()
    print(f'[OK] {insertados:,} candidatos insertados en financiamiento_electoral')
    print(f'     {sin_match:,} sin match en nuestra DB (candidatos que no ganaron o no estan en Servel)')

    # Insertar donante_electoral (transacciones individuales)
    print('[..] Insertando donante_electoral...')
    BATCH = 2000
    batch = []
    total_don = 0

    for f in filas:
        key = (f['nombre_cand'], f['eleccion'], f['territorio'])
        if key not in fin_id_map:
            continue
        fin_id, cid = fin_id_map[key]

        # Solo registrar transacciones con donante identificado o monto relevante
        if not f['rut_donante'] and not f['nombre_donante']:
            continue

        rut_completo = None
        if f['rut_donante'] and f['dv_donante']:
            rut_completo = f['rut_donante'].lstrip('0') + f['dv_donante']
        elif f['rut_donante']:
            rut_completo = f['rut_donante'].lstrip('0')

        batch.append((
            fin_id, cid, f['tipo'], rut_completo, f['nombre_donante'],
            f['monto'], f['fecha'], f['descripcion'], f['tipo_doc']
        ))

        if len(batch) >= BATCH:
            cur.executemany("""
                INSERT INTO donante_electoral
                    (financiamiento_id, candidato_id, tipo, rut_donante, nombre_donante,
                     monto, fecha, descripcion, tipo_documento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, batch)
            conn.commit()
            total_don += len(batch)
            print(f'   {total_don:,} transacciones insertadas...')
            batch = []

    if batch:
        cur.executemany("""
            INSERT INTO donante_electoral
                (financiamiento_id, candidato_id, tipo, rut_donante, nombre_donante,
                 monto, fecha, descripcion, tipo_documento)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, batch)
        conn.commit()
        total_don += len(batch)

    print(f'[OK] {total_don:,} transacciones insertadas en donante_electoral')

    # Resumen final
    cur.execute('SELECT COUNT(*) FROM financiamiento_electoral WHERE candidato_id IS NOT NULL')
    n_vinculados = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM financiamiento_electoral')
    n_total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(DISTINCT rut_donante) FROM donante_electoral WHERE rut_donante IS NOT NULL')
    n_donantes = cur.fetchone()[0]

    cur.close()
    conn.close()

    print()
    print('=== RESUMEN ===')
    print(f'  Candidatos en SERVEL:          {n_total:,}')
    print(f'  Vinculados a nuestra DB:       {n_vinculados:,}')
    print(f'  Donantes unicos identificados: {n_donantes:,}')
    print(f'  Transacciones individuales:    {total_don:,}')
    print()
    print('Siguiente paso sugerido: detectar DONANTE_PROVEEDOR en ia_fiscalizadora.py')
    print('  -> donante que aporto a candidato X tambien es proveedor del estado (orden_compra)')


if __name__ == '__main__':
    main()
