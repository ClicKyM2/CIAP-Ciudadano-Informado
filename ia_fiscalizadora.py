import psycopg2
import os

class IAFiscalizadora:
    def __init__(self):
        self.conn = psycopg2.connect(
            host="127.0.0.1",
            database="ciudadano_db",
            user="postgres",
            password="Canelo123_", 
            port="5432",
            client_encoding='utf-8'
        )

    def detectar_conflictos_lobby(self):
        print("🧠 IA Fiscalizadora: Analizando cruces de Lobby y Patrimonio...")
        
        # Busca políticos que se reunieron con empresas donde ellos mismos tienen participación
        query = """
            SELECT c.id, c.nombres, c.apellidos, rl.empresa_nombre, rl.fecha, rl.url_referencia
            FROM candidato c
            JOIN participacion_societaria ps ON c.id = ps.candidato_id
            JOIN reunion_lobby rl ON c.id = rl.candidato_id AND ps.empresa_rut = rl.empresa_rut
        """
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                conflictos = cur.fetchall()
                
                for conflicto in conflictos:
                    candidato_id, nombres, apellidos, empresa, fecha, url = conflicto
                    detalle = f"El político {nombres} {apellidos} registró reunión de lobby el {fecha} con la empresa {empresa}, en la cual tiene participación societaria."
                    
                    print(f"🚨 ALERTA DETECTADA: {detalle}")
                    
                    # Insertar alerta
                    cur.execute("""
                        INSERT INTO alerta_probidad (candidato_id, tipo, gravedad, detalle, fuente_url)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (candidato_id, 'AUTOLOBBY_DETECTADO', 'ALTA', detalle, url))
            
            self.conn.commit()
            print("✅ Análisis finalizado.")
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error en análisis de IA: {e}")
        finally:
            self.conn.close()

if __name__ == "__main__":
    ia = IAFiscalizadora()
    ia.detectar_conflictos_lobby()