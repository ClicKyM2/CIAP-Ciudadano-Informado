import os
import requests
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential
import traceback

class ExtractorMercadoPublico:
    def __init__(self):
        self.url_diaria = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
        self.ticket = os.environ.get("MERCADO_PUBLICO_TICKET", "")
        
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _fetch_licitaciones_por_fecha(self, fecha_str):
        params = {
            "fecha": fecha_str,
            "ticket": self.ticket
        }
        response = requests.get(self.url_diaria, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def obtener_adjudicaciones_del_dia(self, fecha_str=None):
        if not self.ticket:
            print("⚠️ ADVERTENCIA: No hay Token de Mercado Público (MERCADO_PUBLICO_TICKET). Extracción omitida.")
            return []

        if not fecha_str:
            ayer = datetime.now() - timedelta(days=1)
            fecha_str = ayer.strftime("%d%m%Y")

        print(f"📄 Consultando adjudicaciones de Mercado Público para la fecha: {fecha_str}...")
        adjudicaciones_limpias = []

        try:
            data = self._fetch_licitaciones_por_fecha(fecha_str)
            cantidad_total = data.get("Cantidad", 0)
            listado = data.get("Listado", [])
            
            for licitacion in listado:
                if "Adjudicacion" in licitacion and licitacion["Adjudicacion"]:
                    rut_comprador_bruto = licitacion.get("Comprador", {}).get("RutUnidad", "")
                    rut_proveedor_bruto = licitacion.get("Adjudicacion", {}).get("RutProveedor", "")
                    
                    if rut_comprador_bruto and rut_proveedor_bruto:
                        rut_comprador = str(rut_comprador_bruto).replace(".", "").replace("-", "").upper()
                        rut_proveedor = str(rut_proveedor_bruto).replace(".", "").replace("-", "").upper()
                        monto = licitacion.get("Adjudicacion", {}).get("Monto", 0)
                        url_licitacion = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?qs={licitacion.get('CodigoExterno')}"

                        adjudicaciones_limpias.append({
                            "CodigoExterno": licitacion.get("CodigoExterno"),
                            "Nombre": licitacion.get("Nombre", "Sin Nombre"),
                            "Comprador": {
                                "RutUnidad": rut_comprador,
                                "NombreUnidad": licitacion.get("Comprador", {}).get("NombreUnidad", "")
                            },
                            "Adjudicacion": {
                                "RutProveedor": rut_proveedor,
                                "Monto": monto,
                                "UrlResolucion": url_licitacion
                            }
                        })

            print(f"✅ Se extrajeron {len(adjudicaciones_limpias)} contratos adjudicados válidos.")
            return adjudicaciones_limpias

        except Exception as e:
            print(f"❌ Error conectando con Mercado Público: {e}")
            return []