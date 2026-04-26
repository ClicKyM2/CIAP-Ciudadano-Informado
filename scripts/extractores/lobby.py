import os
import requests
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential
import traceback

class ExtractorLobby:
    def __init__(self):
        self.base_url = "https://api.leylobby.gob.cl/api/v1/audiencias"
        self.api_token = os.environ.get("LEY_LOBBY_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json"
        }

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _fetch_pagina_audiencias(self, pagina, fecha_inicio):
        params = {
            "fecha_inicio": fecha_inicio,
            "page": pagina
        }
        response = requests.get(self.base_url, headers=self.headers, params=params, timeout=15)
        response.raise_for_status() 
        return response.json()

    def obtener_reuniones_recientes(self, ruts_vigilados, dias_atras=7):
        if not self.api_token:
            print("⚠️ ADVERTENCIA: No hay Token de Ley de Lobby (LEY_LOBBY_TOKEN). Extracción omitida.")
            return []

        fecha_inicio = (datetime.now() - timedelta(days=dias_atras)).strftime("%Y-%m-%d")
        print(f"🤝 Buscando reuniones de Lobby desde el {fecha_inicio}...")
        
        audiencias_relevantes = []
        pagina = 1
        hay_mas_paginas = True

        try:
            while hay_mas_paginas:
                data = self._fetch_pagina_audiencias(pagina, fecha_inicio)
                resultados = data.get("data", [])
                
                if not resultados:
                    break

                for reunion in resultados:
                    sujeto_pasivo = reunion.get("sujeto_pasivo", {})
                    rut_autoridad = str(sujeto_pasivo.get("rut", "")).replace("-", "").replace(".", "").upper()

                    if rut_autoridad in ruts_vigilados:
                        asistentes = reunion.get("sujetos_activos", [])
                        empresas_representadas = []
                        
                        for asistente in asistentes:
                            if asistente.get("representa"):
                                rut_emp = str(asistente["representa"].get("rut", "")).replace("-", "").upper()
                                nom_emp = asistente["representa"].get("nombre", "")
                                empresas_representadas.append({"rut": rut_emp, "nombre": nom_emp})

                        audiencias_relevantes.append({
                            "rut_autoridad": rut_autoridad,
                            "nombre_autoridad": sujeto_pasivo.get("nombre_completo"),
                            "fecha": reunion.get("fecha_inicio"),
                            "materia": reunion.get("materia", "Sin especificar"),
                            "institucion": reunion.get("institucion", {}).get("nombre"),
                            "empresas_representadas": empresas_representadas,
                            "url_referencia": reunion.get("url")
                        })

                meta = data.get("meta", {})
                if pagina >= meta.get("last_page", 1):
                    hay_mas_paginas = False
                else:
                    pagina += 1

            print(f"✅ Se encontraron {len(audiencias_relevantes)} reuniones clave en los últimos {dias_atras} días.")
            return audiencias_relevantes

        except Exception as e:
            print(f"❌ Error extrayendo Ley de Lobby: {e}")
            return []