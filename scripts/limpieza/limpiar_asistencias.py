import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

print("Limpiando asistenciasPasivos.csv...")

LOBBY_DIR = os.getenv("LOBBY_DIR", r"C:\Users\Public")
ruta_in   = os.path.join(LOBBY_DIR, "asistenciasPasivos.csv")
ruta_out  = os.path.join(LOBBY_DIR, "asistencias_limpio.csv")

try:
    # Leemos el original (UTF-16)
    df = pd.read_csv(ruta_in, encoding='utf-16', sep=',', on_bad_lines='skip', engine='python')
    
    # Nos aseguramos de que tenga exactamente 2 columnas
    df = df.iloc[:, :2]
    
    # Guardamos en UTF-8 con comillas protectoras
    df.to_csv(ruta_out, index=False, encoding='utf-8', quoting=1)
    
    print(f"✅ ¡Listo! Archivo creado: {ruta_out}")
    print(f"📊 Registros: {len(df)}")

except Exception as e:
    print(f"❌ Error: {e}")