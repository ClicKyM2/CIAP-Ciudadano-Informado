import pandas as pd
import glob
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
archivos = glob.glob(os.path.join(base_dir, "data", "*.xlsx"))

if archivos:
    archivo = archivos[0]
    print(f"📄 Analizando a fondo: {os.path.basename(archivo)}\n")
    
    # 1. Miramos cuántas pestañas tiene el Excel
    xl = pd.ExcelFile(archivo)
    print(f"📑 Pestañas (Hojas) encontradas: {xl.sheet_names}\n")
    
    # 2. Leemos las primeras 15 filas de la primera pestaña
    df = pd.read_excel(archivo, sheet_name=xl.sheet_names[0], nrows=15)
    
    print("👀 ESTO ES LO QUE HAY EN LAS PRIMERAS FILAS:")
    print(df.head(15).to_string())
    
else:
    print("❌ No encontré archivos Excel en la carpeta data.")