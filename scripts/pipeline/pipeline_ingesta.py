import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
import glob
from dotenv import load_dotenv

load_dotenv()

class PipelineIngesta:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "ciudadano_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", "5432"),
            client_encoding="UTF8"
        )

    def _upsert_catalogo(self, cursor, tabla, nombre):
        if pd.isna(nombre) or str(nombre).strip() == "":
            return None
        cursor.execute("SELECT id FROM " + tabla + " WHERE nombre = %s", (nombre,))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0]
        else:
            cursor.execute("INSERT INTO " + tabla + " (nombre) VALUES (%s) RETURNING id", (nombre,))
            return cursor.fetchone()[0]

    def procesar_autoridades(self, carpeta_data):
        archivos_excel = glob.glob(os.path.join(carpeta_data, "*.xlsx"))

        if not archivos_excel:
            print("❌ No encontre archivos Excel (.xlsx) en " + carpeta_data)
            return

        print(f"📂 Encontre {len(archivos_excel)} archivos Excel. Escaneando los formatos...")

        lista_dataframes = []
        for archivo in archivos_excel:
            nombre_archivo = os.path.basename(archivo)
            print(f"   -> Procesando: {nombre_archivo}")

            cargo_inferido = "DESCONOCIDO"
            nombre_min = nombre_archivo.lower()
            if "alcaldes" in nombre_min: cargo_inferido = "ALCALDE"
            elif "concejales" in nombre_min: cargo_inferido = "CONCEJAL"
            elif "consejeros" in nombre_min: cargo_inferido = "CONSEJERO REGIONAL"
            elif "gobernadores" in nombre_min: cargo_inferido = "GOBERNADOR REGIONAL"

            df_buscador = pd.read_excel(archivo, header=None, nrows=20)
            fila_titulos = 0
            for index, row in df_buscador.iterrows():
                fila_texto = " ".join([str(val).lower() for val in row.values])
                
                # 🔥 EL CAMBIO CLAVE: Exigir que estén NOMBRES y COMUNA al mismo tiempo
                if 'nombres' in fila_texto and 'comuna' in fila_texto:
                    fila_titulos = index
                    break

            print(f"      📌 Titulos reales encontrados en la fila {fila_titulos + 1}")

            df_temp = pd.read_excel(archivo, header=fila_titulos)
            
            # --- EL EXTERMINADOR DE COLUMNAS TRAMPA ---
            df_temp.columns = df_temp.columns.astype(str).str.lower().str.strip()
            
            if 'cargo' in df_temp.columns:
                df_temp = df_temp.drop(columns=['cargo'])
                
            df_temp['cargo'] = cargo_inferido
            lista_dataframes.append(df_temp)

        df = pd.concat(lista_dataframes, ignore_index=True)

        # --- LIMPIEZA INTELIGENTE DE COLUMNAS ---
        df = df.loc[:, ~df.columns.duplicated()]

        mapping = {}
        for col in df.columns:
            if 'nombres' in col or col == 'nombre' or 'candidato' in col: mapping[col] = 'nombres'
            elif 'primer apellido' in col: mapping[col] = 'apellido_1'
            elif 'segundo apellido' in col: mapping[col] = 'apellido_2'
            elif col == 'comuna' or col == 'desc comuna': mapping[col] = 'comuna'
            elif 'partido' in col or 'pacto' in col: mapping[col] = 'partido'

        df = df.rename(columns=mapping)
        df = df.loc[:, ~df.columns.duplicated()]
        
        print(f"📊 Total de filas crudas: {len(df)}")

        # --- FILTRADO DE BASURA ---
        if 'nombres' not in df.columns:
            print("❌ Error: No se pudo encontrar la columna de nombres. Revisa los Excel.")
            return
            
        df = df.dropna(subset=['nombres'])
        df = df[~df['nombres'].astype(str).str.contains("VOTOS NULOS|VOTOS EN BLANCO|TOTAL", na=False, case=False)]

        # --- UNIÓN DE APELLIDOS SEGURA ---
        ap1 = df['apellido_1'].astype(str).replace('nan', '').fillna('') if 'apellido_1' in df.columns else pd.Series([""] * len(df))
        ap2 = df['apellido_2'].astype(str).replace('nan', '').fillna('') if 'apellido_2' in df.columns else pd.Series([""] * len(df))
        df['apellidos'] = ap1 + ' ' + ap2
        
        # --- SOLUCIÓN AL BUG DEL RUT Y DUPLICADOS ---
        rut_col = next((c for c in df.columns if "rut" in c.lower() or "cedula" in c.lower()), None)
        
        columnas_base = ['nombres', 'apellidos', 'partido', 'comuna', 'cargo']
        if rut_col:
            df['rut'] = df[rut_col].astype(str).str.replace(".", "").str.replace("-", "").str.upper()
            columnas_base.insert(0, 'rut')
            
        df_candidatos = df[[c for c in columnas_base if c in df.columns]].drop_duplicates().copy()
        
        if not rut_col:
            df_candidatos["rut"] = ["SERVEL-" + str(i) for i in range(1, len(df_candidatos) + 1)]
            
        columnas_finales = ['rut', 'nombres', 'apellidos', 'partido', 'comuna', 'cargo']
        df_candidatos = df_candidatos[[c for c in columnas_finales if c in df_candidatos.columns]]

        print(f"🎯 Total de candidatos unicos encontrados: {len(df_candidatos)}")

        # 💾 GUARDAR RESPALDO EN CSV
        ruta_respaldo = os.path.join(carpeta_data, "candidatos_final_limpio.csv")
        df_candidatos.to_csv(ruta_respaldo, index=False, encoding='utf-8-sig')
        print(f"💾 Respaldo guardado en: {ruta_respaldo}")

        # --- INSERCIÓN A BASE DE DATOS ---
        cursor = self.conn.cursor()
        try:
            # ATENCION: TRUNCATE CASCADE borra en cascada participaciones, alertas,
            # lobby matches, licitaciones y ordenes de compra vinculados.
            # Si se re-corre este paso hay que volver a correr todo el pipeline desde 'participaciones'.
            print("ATENCION: TRUNCATE TABLE candidato CASCADE - se borran todos los datos vinculados.")
            print("Continua en 5 segundos (Ctrl+C para cancelar)...")
            import time; time.sleep(5)
            cursor.execute("TRUNCATE TABLE candidato CASCADE;")
            
            candidatos_a_insertar = []
            for _, row in df_candidatos.iterrows():
                partido_id = self._upsert_catalogo(cursor, "partido", row.get("partido"))
                cargo_id = self._upsert_catalogo(cursor, "cargo", row.get("cargo"))

                candidatos_a_insertar.append((
                    str(row["rut"]).strip(),
                    str(row.get("nombres", "")).strip(),
                    str(row.get("apellidos", "")).strip(),
                    partido_id,
                    cargo_id,
                    str(row.get("comuna", "")).strip()
                ))

            query_insert = (
                "INSERT INTO candidato (rut, nombres, apellidos, partido_id, cargo_id, comuna) "
                "VALUES %s ON CONFLICT (rut) DO UPDATE SET "
                "nombres = EXCLUDED.nombres, "
                "apellidos = EXCLUDED.apellidos, "
                "partido_id = EXCLUDED.partido_id, "
                "cargo_id = EXCLUDED.cargo_id, "
                "comuna = EXCLUDED.comuna"
            )
            execute_values(cursor, query_insert, candidatos_a_insertar)
            self.conn.commit()
            print(f"✅ EXITO: {len(candidatos_a_insertar)} candidatos insertados limpios en PostgreSQL.")

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