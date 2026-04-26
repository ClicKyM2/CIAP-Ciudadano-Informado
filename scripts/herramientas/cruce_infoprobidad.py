import unicodedata
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv

load_dotenv()

def normalizar(texto):
    if not texto or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    txt = unicodedata.normalize("NFD", str(texto).upper())
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    return " ".join(txt.split())

def ejecutar_cruce():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )
    
    print("📖 Leyendo candidatos de la DB...")
    # Usamos una forma más estándar para evitar el Warning de Pandas
    df_candidatos = pd.read_sql("SELECT id, nombres, apellidos FROM candidato WHERE rut LIKE 'SERVEL-%'", conn)
    
    print("📂 Cargando Infoprobidad (csv)...")
    ruta_csv = os.path.join("data", "csvdeclaraciones.csv")
    df_info = pd.read_csv(ruta_csv, encoding='utf-8', low_memory=False)

    # 1. Crear una columna de "Nombre Completo" en Infoprobidad para un match más rápido
    print("⚙️ Preparando motor de búsqueda...")
    df_info['full_match'] = (
        df_info['Nombre'].apply(normalizar) + " " + 
        df_info['ApPaterno'].apply(normalizar) + " " + 
        df_info['ApMaterno'].apply(normalizar)
    ).str.strip()

    # 2. Crear un diccionario para búsquedas ultra rápidas O(1)
    # Mapeamos Nombre Completo -> UriDeclarante
    dict_info = pd.Series(df_info.UriDeclarante.values, index=df_info.full_match).to_dict()

    updates = []
    print(f"🚀 Cruzando {len(df_candidatos)} candidatos...")

    for _, cand in df_candidatos.iterrows():
        # En la DB tenemos nombres y apellidos separados, los unimos igual que en el CSV
        nombre_completo_db = normalizar(f"{cand['nombres']} {cand['apellidos']}")
        
        uri_encontrada = dict_info.get(nombre_completo_db)
        
        if uri_encontrada:
            updates.append((uri_encontrada, cand['id']))

    if updates:
        print(f"💾 Guardando {len(updates)} matches en la base de datos...")
        cursor = conn.cursor()
        # Usamos execute_values para actualizar miles de filas en un solo viaje a la DB
        query = "UPDATE candidato SET uri_declarante = data.uri FROM (VALUES %s) AS data (uri, id) WHERE candidato.id = data.id"
        execute_values(cursor, query, updates)
        conn.commit()
        cursor.close()
        print("✨ ¡Proceso completado con éxito!")
    else:
        print("❓ No se encontraron coincidencias exactas.")

    conn.close()

if __name__ == "__main__":
    ejecutar_cruce()