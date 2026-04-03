import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
import glob

class PipelineIngesta:
    def __init__(self):
        self.conn = psycopg2.connect(
            host="localhost",
            database="ciudadano_db",
            user="postgres",
            password="Canelo123_", 
            port="5432",
            client_encoding="UTF8"
        )

    def _upsert_catalogo(self, cursor, tabla, nombre):
        if pd.isna(nombre) or str(nombre).strip() == "":
            return None
        cursor.execute(f"SELECT id FROM {tabla} WHERE nombre = %s", (nombre,))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0]
        else:
            cursor.execute(f"INSERT INTO {tabla} (nombre) VALUES (%s) RETURNING id", (nombre,))
            return cursor.fetchone()[0]

    def procesar_autoridades(self, carpeta_data):
        archivos_excel = glob.glob(os.path.join(carpeta_data, "*.xlsx"))
        
        if not archivos_excel:
            print(f"❌ No encontré archivos Excel (.xlsx) en {carpeta_data}")
            return
            
        print(f"📂 Encontré {len(archivos_excel)} archivos Excel. Escaneando los formatos...")
        
        lista_dataframes = []
        for archivo in archivos_excel:
            print(f"   -> Procesando: {os.path.basename(archivo)}")
            
            # 🕵️‍♂️ BÚSQUEDA DINÁMICA DEL ENCABEZADO
            df_buscador = pd.read_excel(archivo, header=None, nrows=20)
            fila_titulos = 0
            for index, row in df_buscador.iterrows():
                # 🔥 CORRECCIÓN: Convertimos cada valor a texto puro, incluso los vacíos (NaN)
                fila_texto = " ".join([str(val).lower() for val in row.values])
                if 'nombres' in fila_texto or 'primer apellido' in fila_texto or 'comuna' in fila_texto:
                    fila_titulos = index
                    break
            
            print(f"      📌 ¡Títulos reales encontrados en la fila {fila_titulos + 1}!")
            
            # Leemos usando la fila correcta
            df_temp = pd.read_excel(archivo, header=fila_titulos)
            lista_dataframes.append(df_temp)
            
        df = pd.concat(lista_dataframes, ignore_index=True)
        
        # --- LIMPIEZA INTELIGENTE DE COLUMNAS ---
        df.columns = df.columns.astype(str).str.lower().str.strip()
        
        mapping = {}
        for col in df.columns:
            if 'nombres' in col or col == 'nombre': mapping[col] = 'nombres'
            elif 'primer apellido' in col: mapping[col] = 'apellido_1'
            elif 'segundo apellido' in col: mapping[col] = 'apellido_2'
            elif 'comuna' in col: mapping[col] = 'comuna'
            elif 'partido' in col: mapping[col] = 'partido'
            elif 'cargo' in col: mapping[col] = 'cargo'

        df = df.rename(columns=mapping)
        print(f"📊 Total de filas crudas (Mesa por Mesa): {len(df)}")

        # --- FILTRADO DE BASURA ---
        if 'nombres' not in df.columns:
            print("❌ Error crítico: Aún no encuentro la columna 'nombres'. Columnas que veo:")
            print(list(df.columns))
            return

        df = df.dropna(subset=['nombres'])
        df = df[~df['nombres'].astype(str).str.contains("VOTOS NULOS|VOTOS EN BLANCO|TOTAL", na=False, case=False)]

        # --- UNIÓN DE APELLIDOS ---
        ap1 = df['apellido_1'] if 'apellido_1' in df.columns else ""
        ap2 = df['apellido_2'] if 'apellido_2' in df.columns else ""
        df['apellidos'] = ap1.astype(str).replace('nan', '') + ' ' + ap2.astype(str).replace('nan', '')
        
        # --- SELECCIÓN Y ELIMINACIÓN DE DUPLICADOS ---
        columnas_finales = ['nombres', 'apellidos', 'partido', 'comuna', 'cargo']
        df_candidatos = df[[c for c in columnas_finales if c in df.columns]].drop_duplicates().copy()
        
        print(f"🎯 Total de CANDIDATOS REALES únicos encontrados: {len(df_candidatos)}")
        
        # 💾 GUARDAR RESPALDO EN CSV
        ruta_respaldo = os.path.join(carpeta_data, "candidatos_final_limpio.csv")
        df_candidatos.to_csv(ruta_respaldo, index=False, encoding='utf-8-sig')
        print(f"💾 ¡Respaldo guardado! Podrás ver la tabla limpia en: {ruta_respaldo}")

        # --- INSERCIÓN A BASE DE DATOS ---
        df_candidatos['rut'] = ['FALSO-' + str(i) for i in range(1, len(df_candidatos) + 1)]
            
        cursor = self.conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE candidato CASCADE;")
            print("🧹 Tabla PostgreSQL limpiada de errores anteriores.")

            candidatos_a_insertar = []
            for _, row in df_candidatos.iterrows():
                partido_id = self._upsert_catalogo(cursor, 'partido', row.get('partido'))
                cargo_id = self._upsert_catalogo(cursor, 'cargo', row.get('cargo'))
                
                candidatos_a_insertar.append((
                    str(row['rut']).strip(),
                    str(row.get('nombres', '')).strip(),
                    str(row.get('apellidos', '')).strip(),
                    partido_id,
                    cargo_id,
                    str(row.get('comuna', '')).strip()
                ))
            
            query_insert = """
                INSERT INTO candidato (rut, nombres, apellidos, partido_id, cargo_id, comuna)
                VALUES %s
            """
            execute_values(cursor, query_insert, candidatos_a_insertar)
            self.conn.commit()
            print(f"✅ ¡ÉXITO! {len(candidatos_a_insertar)} candidatos insertados perfectamente en PostgreSQL.")
            
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error insertando datos: {e}")
        finally:
            cursor.close()

if __name__ == "__main__":
    pipeline = PipelineIngesta()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    carpeta_data = os.path.join(base_dir, "data")
    pipeline.procesar_autoridades(carpeta_data)