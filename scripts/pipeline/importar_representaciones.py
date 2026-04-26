import psycopg2
import os
import pandas as pd
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

DB = dict(
    host=os.getenv('DB_HOST'), dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'),
    port=os.getenv('DB_PORT')
)
conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Skip si la tabla ya tiene datos (evita recargar 1.5M filas innecesariamente)
cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='temp_representaciones'")
if cur.fetchone():
    cur.execute("SELECT COUNT(*) FROM temp_representaciones")
    n = cur.fetchone()[0]
    if n > 1000000:
        print(f"temp_representaciones ya tiene {n:,} filas - saltando")
        cur.close()
        conn.close()
        exit(0)

cur.execute('DROP TABLE IF EXISTS temp_representaciones')
cur.execute('''
    CREATE TABLE temp_representaciones (
        codigo_representado VARCHAR(30),
        representado        VARCHAR(500),
        giro                VARCHAR(255),
        codigo_audiencia    VARCHAR(50),
        personalidad        VARCHAR(100)
    )
''')
conn.commit()

print('Leyendo representaciones.csv (1.5M filas)...')
df = pd.read_csv(
    'data/representaciones.csv', dtype=str,
    encoding='utf-16', on_bad_lines='skip', low_memory=False
)
df.columns = [c.strip().strip('"') for c in df.columns]
df = df.fillna('')
print(f'Filas: {len(df)}')

CHUNK = 50000
total = 0
for start in range(0, len(df), CHUNK):
    chunk = df.iloc[start:start + CHUNK]
    rows = [
        (
            r['codigoRepresentado'][:30],
            r['representado'][:500],
            r['giroRepresentado'][:255],
            r['codigoAudiencia'][:50],
            r['personalidad'][:100]
        )
        for _, r in chunk.iterrows()
    ]
    execute_values(
        cur,
        '''INSERT INTO temp_representaciones
           (codigo_representado, representado, giro, codigo_audiencia, personalidad)
           VALUES %s''',
        rows
    )
    total += len(rows)
    conn.commit()
    print(f'  {total}/{len(df)}')

cur.execute('CREATE INDEX idx_repr_audiencia ON temp_representaciones(codigo_audiencia)')
conn.commit()
cur.execute('SELECT COUNT(*) FROM temp_representaciones')
print('Total importado:', cur.fetchone()[0])
conn.close()
print('Listo.')
