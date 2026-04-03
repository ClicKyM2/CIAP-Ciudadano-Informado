import pandas as pd
import os
import traceback

class ExtractorGobiernoLocal:
    def __init__(self):
        self.archivo_local = "data/servel_autoridades.csv"
        os.makedirs("data", exist_ok=True)

    def obtener_autoridades_locales(self):
        if not os.path.exists(self.archivo_local):
            print(f"⚠️ ADVERTENCIA: No se encontró el archivo {self.archivo_local}.")
            print("💡 Acción requerida: Descarga el CSV de autoridades electas desde servel.cl y colócalo en 'data/servel_autoridades.csv'.")
            return []

        print("🏛️ Extrayendo Autoridades Locales desde el dataset oficial de SERVEL...")
        autoridades = []

        try:
            df = pd.read_csv(self.archivo_local, sep=';', encoding='utf-8', on_bad_lines='skip', low_memory=False)
            df.columns = df.columns.str.strip().str.lower()

            columnas_requeridas = ['rut', 'nombres', 'apellidos', 'cargo', 'comuna', 'partido']
            for col in columnas_requeridas:
                if col not in df.columns:
                    print(f"❌ Error: El CSV de SERVEL no contiene la columna '{col}'.")
                    return []

            df_filtrado = df[df['cargo'].astype(str).str.contains('Alcalde|Gobernador', case=False, na=False)]

            for _, row in df_filtrado.iterrows():
                rut_bruto = str(row['rut']).replace(".", "").replace("-", "").strip().upper()
                if not rut_bruto or rut_bruto == 'NAN':
                    continue

                cargo_real = str(row['cargo']).strip().title()
                comuna_region = str(row['comuna']).strip().title()
                partido = str(row['partido']).strip().upper() if pd.notna(row['partido']) else 'INDEPENDIENTE'
                
                if "Alcalde" in cargo_real:
                    institucion = f"Municipalidad de {comuna_region}"
                    nivel = "LOCAL"
                else:
                    institucion = f"Gobierno Regional de {comuna_region}"
                    nivel = "REGIONAL"

                autoridades.append({
                    "rut": rut_bruto,
                    "nombres": str(row['nombres']).strip().title(),
                    "apellidos": str(row['apellidos']).strip().title(),
                    "partido": partido,
                    "cargo": cargo_real,
                    "nivel_cargo": nivel,
                    "institucion": institucion,
                    "rut_institucion": None 
                })

            print(f"✅ Se extrajeron {len(autoridades)} autoridades locales válidas.")
            return autoridades

        except UnicodeDecodeError:
            print("❌ Error de codificación: El archivo SERVEL parece estar en ISO-8859-1 (Latin1). Intenta guardarlo como UTF-8.")
            return []
        except Exception as e:
            print(f"❌ Error procesando el archivo de SERVEL: {e}")
            return []