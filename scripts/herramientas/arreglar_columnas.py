import os
import csv
from dotenv import load_dotenv

load_dotenv()

print("Pasando el archivo por el escaner de columnas... (tomara unos segundos)")

LOBBY_DIR   = os.getenv("LOBBY_DIR", r"C:\Users\Public")
ruta_limpia = os.path.join(LOBBY_DIR, "pasivos_limpio.csv")
ruta_final  = os.path.join(LOBBY_DIR, "pasivos_final.csv")
columnas_esperadas = 10
errores_corregidos = 0

try:
    # Abrimos el archivo que limpiamos antes y creamos uno nuevo definitivo
    with open(ruta_limpia, 'r', encoding='utf-8') as f_in, \
         open(ruta_final, 'w', encoding='utf-8', newline='') as f_out:
         
        lector = csv.reader(f_in)
        escritor = csv.writer(f_out, quoting=csv.QUOTE_ALL)
        
        for fila in lector:
            if len(fila) > columnas_esperadas:
                # Si el gobierno metió comas de más, cortamos lo que sobra
                escritor.writerow(fila[:columnas_esperadas])
                errores_corregidos += 1
            elif len(fila) < columnas_esperadas:
                # Si le faltan datos, rellenamos con espacios en blanco
                fila.extend([''] * (columnas_esperadas - len(fila)))
                escritor.writerow(fila)
                errores_corregidos += 1
            else:
                # Si está perfecta, pasa tal cual
                escritor.writerow(fila)
                
    print(f"Listo. Archivo 'pasivos_final.csv' creado.")
    print(f"Corregidas {errores_corregidos} filas.")
except Exception as e:
    print(f"Error: {e}")