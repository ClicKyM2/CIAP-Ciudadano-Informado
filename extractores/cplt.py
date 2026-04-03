import pandas as pd
import os
import traceback

class ExtractorCPLT:
    def __init__(self):
        self.archivo_local = "data/declaraciones_cplt.csv"

    def extraer_patrimonio_y_empresas(self, ruts_politicos):
        """
        Extrae las empresas vinculadas leyendo de un dataset local seguro.
        """
        print("💼 Extrayendo sociedades y empresas vinculadas (CPLT)...")
        
        if not os.path.exists(self.archivo_local):
            print(f"⚠️ Archivo no encontrado: {self.archivo_local}. Descarga el CSV de InfoProbidad manualmente y ponlo en 'data/'.")
            return {}

        try:
            # Leer CSV asegurando que los RUTs se traten como texto para no perder ceros
            df = pd.read_csv(self.archivo_local, dtype=str)
            
            # Limpiar RUT de la base de datos para que coincida (sin puntos ni guiones)
            if 'RutDeclarante' in df.columns:
                df['RutDeclarante'] = df['RutDeclarante'].astype(str).str.replace(r'[\.\-]', '', regex=True).str.upper()
            else:
                print("❌ El CSV de CPLT no tiene la columna 'RutDeclarante'. Revisa el formato.")
                return {}

            # Filtrar solo las autoridades que ya tenemos en PostgreSQL para ahorrar memoria
            df_filtrado = df[df['RutDeclarante'].isin(ruts_politicos)]
            
            resultados = {}
            for rut, grupo in df_filtrado.groupby('RutDeclarante'):
                empresas = []
                columna_tipo = 'TipoBien' if 'TipoBien' in df.columns else 'TipoDeclaracion' 
                
                if columna_tipo in df.columns:
                    # Buscar filas donde se declare participación en sociedades
                    filas_empresas = grupo[grupo[columna_tipo].astype(str).str.contains('Sociedad|Participacion|Empresa', case=False, na=False)]
                    
                    for _, fila in filas_empresas.iterrows():
                        rut_empresa = str(fila.get('RutSociedad', '')).replace(".", "").replace("-", "").upper()
                        if rut_empresa and rut_empresa != 'NAN':
                            empresas.append({
                                "rut": rut_empresa,
                                "razon_social": str(fila.get('NombreSociedad', 'SIN NOMBRE')),
                                "porcentaje": float(fila.get('PorcentajeParticipacion', 0) or 0)
                            })
                
                resultados[rut] = {"empresas_vinculadas": empresas}
                
            print(f"✅ Se extrajeron empresas para {len(resultados)} autoridades.")
            return resultados

        except Exception as e:
            print(f"❌ Error procesando el CSV de CPLT: {e}")
            traceback.print_exc()
            return {}