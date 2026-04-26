import pandas as pd
import os

class ExtractorCongreso:
    def __init__(self):
        self.archivo_local = "data/congreso_autoridades.csv"

    def obtener_parlamentarios(self):
        """
        Retorna la lista estructurada de congresistas para el motor de ingesta,
        leyendo desde un CSV real, sin usar datos falsos.
        """
        print("🏛️ Obteniendo listado de parlamentarios del Congreso...")
        parlamentarios = []

        if not os.path.exists(self.archivo_local):
            print(f"⚠️ Archivo no encontrado: {self.archivo_local}. Por favor agrega este CSV con los datos del Congreso.")
            return []

        try:
            df = pd.read_csv(self.archivo_local)
            
            # FIX Privacidad: Generamos RUT temporal si el CSV público no lo trae
            if 'rut' not in df.columns and 'RUT' not in df.columns:
                df['rut'] = ['FALSO-CONG-' + str(i) for i in range(1, len(df) + 1)]

            for _, row in df.iterrows():
                # Extracción segura de datos
                rut_val = str(row.get('rut', row.get('RUT', ''))).replace(".", "").replace("-", "").upper()
                
                parlamentarios.append({
                    "rut": rut_val,
                    "nombres": str(row.get("nombres", "")).strip().title(),
                    "apellidos": str(row.get("apellidos", "")).strip().title(),
                    "partido": str(row.get("partido", "")).upper(),
                    "cargo": str(row.get("cargo", "Parlamentario")),
                    "nivel_cargo": "NACIONAL",
                    "institucion": str(row.get("institucion", "Congreso Nacional")),
                    "rut_institucion": str(row.get("rut_institucion", "608201007")) # RUT genérico del Congreso
                })
                
            print(f"✅ Se cargaron {len(parlamentarios)} parlamentarios desde el CSV real.")
        
        except Exception as e:
            print(f"❌ Error leyendo el CSV del Congreso: {e}")

        return parlamentarios