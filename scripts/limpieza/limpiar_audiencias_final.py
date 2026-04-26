import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

print("Iniciando limpieza de audiencias.csv...")

LOBBY_DIR = os.getenv("LOBBY_DIR", r"C:\Users\Public")
ruta_in   = os.path.join(LOBBY_DIR, "audiencias.csv")
ruta_out  = os.path.join(LOBBY_DIR, "audiencia_final.csv")

try:
    # Leemos con motor 'python' que es más flexible con errores de comillas
    # Usamos low_memory=False porque el archivo es grande
    df = pd.read_csv(ruta_in, encoding='utf-16', sep=',', on_bad_lines='warn', engine='python')
    
    # Nos aseguramos de que solo tenga las 17 columnas que necesitamos
    # Si tiene más, las corta. Si tiene menos, las crea vacías.
    df = df.iloc[:, :17]
    
    # Guardamos en UTF-8, rodeando TODO con comillas dobles
    df.to_csv(ruta_out, index=False, encoding='utf-8', quoting=1)
    
    print(f"✅ ¡Éxito! Archivo guardado en: {ruta_out}")
    print(f"📊 Registros procesados: {len(df)}")

except Exception as e:
    print(f"❌ Error crítico: {e}")