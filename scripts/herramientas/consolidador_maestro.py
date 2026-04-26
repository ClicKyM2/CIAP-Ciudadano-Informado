import pandas as pd
import json
import os

def limpiar_rut(rut):
    if pd.isna(rut): return ""
    # Quitamos puntos y pasamos a mayúscula la K
    rut_limpio = str(rut).replace(".", "").upper().strip()
    return rut_limpio

def obtener_ruta(nombre_archivo):
    # Busca primero en la carpeta 'data', y si no, en la carpeta principal
    if os.path.exists(f"data/{nombre_archivo}"):
        return f"data/{nombre_archivo}"
    elif os.path.exists(nombre_archivo):
        return nombre_archivo
    return None

def consolidar_bases():
    print("🧹 Iniciando la consolidación maestra de RUTs...")
    dataframes_a_unir = []

    # 1. Procesar la base original (funcionarios_nacionales_con_rut.csv)
    ruta_base = obtener_ruta("funcionarios_nacionales_con_rut.csv")
    if ruta_base:
        df_base = pd.read_csv(ruta_base)
        # Unimos los nombres y apellidos en una sola columna para estandarizar
        df_base['nombres_completos'] = df_base['nombres'].fillna('') + ' ' + df_base['apellido_paterno'].fillna('') + ' ' + df_base['apellido_materno'].fillna('')
        if 'uri_declarante' in df_base.columns:
            df_base = df_base.rename(columns={'uri_declarante': 'link_declaracion'})
        df_base = df_base[['rut', 'nombres_completos', 'cargo', 'comuna', 'link_declaracion']].rename(columns={'nombres_completos': 'nombres'})
        dataframes_a_unir.append(df_base)
        print(f"  📁 Base original cargada: {len(df_base)} registros.")

    # 2. Procesar funcionarios_rescatados.csv
    ruta_resc = obtener_ruta("funcionarios_rescatados.csv")
    if ruta_resc:
        df_resc = pd.read_csv(ruta_resc)
        if 'uri_declaracion' in df_resc.columns:
            df_resc = df_resc.rename(columns={'uri_declaracion': 'link_declaracion'})
        dataframes_a_unir.append(df_resc)
        print(f"  📁 Rescatados cargados: {len(df_resc)} registros.")

    # 3. Procesar funcionarios_rescatados_ninja.csv
    ruta_ninja = obtener_ruta("funcionarios_rescatados_ninja.csv")
    if ruta_ninja:
        df_ninja = pd.read_csv(ruta_ninja)
        dataframes_a_unir.append(df_ninja)
        print(f"  📁 Rescatados Ninja cargados: {len(df_ninja)} registros.")

    # 4. Procesar funcionarios_rescatados_visual.csv
    ruta_visual = obtener_ruta("funcionarios_rescatados_visual.csv")
    if ruta_visual:
        df_visual = pd.read_csv(ruta_visual)
        df_visual['link_declaracion'] = None # Agregamos la columna vacía para que cuadre
        dataframes_a_unir.append(df_visual)
        print(f"  📁 Rescatados Visuales cargados: {len(df_visual)} registros.")

    # 5. Procesar el JSON (progreso_ruts.json) cruzándolo con los sin RUT
    ruta_json = obtener_ruta("progreso_ruts.json")
    ruta_sin_rut = obtener_ruta("funcionarios_sin_rut.csv")
    if ruta_json and ruta_sin_rut:
        with open(ruta_json, "r", encoding="utf-8") as f:
            json_ruts = json.load(f)
        
        df_json = pd.DataFrame(list(json_ruts.items()), columns=['link_declaracion', 'rut'])
        df_sin_rut = pd.read_csv(ruta_sin_rut)
        df_json_full = pd.merge(df_json, df_sin_rut, on="link_declaracion", how="inner")
        df_json_full = df_json_full[['rut', 'nombres', 'cargo', 'comuna', 'link_declaracion']]
        dataframes_a_unir.append(df_json_full)
        print(f"  📁 RUTs del JSON cruzados con éxito: {len(df_json_full)} registros.")

    # --- VERIFICACIÓN DE SEGURIDAD ---
    if not dataframes_a_unir:
        print("❌ Error fatal: No encontré ningún archivo CSV ni JSON para procesar.")
        return

    # --- UNIÓN TOTAL ---
    df_final = pd.concat(dataframes_a_unir, ignore_index=True)
    
    # Limpiar la columna RUT
    df_final['rut'] = df_final['rut'].apply(limpiar_rut)
    
    # Eliminar duplicados
    total_antes = len(df_final)
    df_final = df_final.drop_duplicates(subset=['rut'], keep='first')
    total_despues = len(df_final)
    
    print(f"\n🔄 Se eliminaron {total_antes - total_despues} registros duplicados (personas atrapadas más de una vez).")

    # Guardar el archivo maestro
    archivo_salida = "data/MAESTRO_RUTS_CONSOLIDADOS.csv"
    os.makedirs("data", exist_ok=True)
    df_final.to_csv(archivo_salida, index=False, encoding="utf-8-sig")
    
    print(f"\n🎯 ¡Consolidación exitosa! Tu base de datos oficial tiene ahora {len(df_final)} funcionarios con RUT.")
    print(f"💾 Archivo guardado en: {archivo_salida}")

if __name__ == '__main__':
    consolidar_bases()