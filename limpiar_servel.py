import pandas as pd
import os

archivo_descargado = "data/2024_10_Alcaldes_Datos_Eleccion.xlsx"
archivo_salida = "data/servel_autoridades.csv"

def limpiar():
    print("📂 Leyendo archivo de 65MB (esto puede tomar 1 o 2 minutos, ten paciencia)...")
    
    # 1. Leemos el Excel
    df = pd.read_excel(archivo_descargado, header=6)
    
    # ¡NUEVO!: Limpiamos los nombres de las columnas por si traen espacios invisibles
    df.columns = df.columns.str.strip()
    
    # 2. ¡NUEVO FILTRO!: Buscamos exactamente donde la columna Cargo contenga la palabra ALCALDE
    df_ganadores = df[df['Cargo'].astype(str).str.contains('ALCALDE', case=False, na=False)]
    
    # 3. Borramos los duplicados (porque hay 1 registro por cada mesa de votación)
    df_unicos = df_ganadores.drop_duplicates(subset=['Comuna', 'Nombres', 'Primer apellido'])
    
    # 4. Armamos la tabla para la Base de Datos
    df_final = pd.DataFrame()
    df_final['rut'] = "SIN_RUT" 
    df_final['nombres'] = df_unicos['Nombres'].str.title() 
    
    apellidos_completos = df_unicos['Primer apellido'] + " " + df_unicos['Segundo apellido'].fillna('')
    df_final['apellidos'] = apellidos_completos.str.title()
    
    df_final['cargo'] = df_unicos['Cargo'].str.title()
    df_final['comuna'] = df_unicos['Comuna'].str.title()
    df_final['partido'] = df_unicos['Partido'].str.title()
    
    # 5. Guardamos el resultado
    os.makedirs("data", exist_ok=True)
    df_final.to_csv(archivo_salida, sep=',', index=False, encoding='utf-8')
    
    print(f"✅ ¡Éxito! Se encontraron y limpiaron {len(df_final)} alcaldes electos.")
    print(f"✅ Archivo liviano guardado en: {archivo_salida}")

if __name__ == "__main__":
    limpiar()