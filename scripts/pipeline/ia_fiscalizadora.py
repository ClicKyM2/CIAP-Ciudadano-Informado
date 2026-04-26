import psycopg2
import os
import unicodedata
from dotenv import load_dotenv

load_dotenv()

# Umbral de similitud de texto para considerar que dos nombres de empresa son el mismo
SIMILITUD_MIN = 0.75

# Longitud mínima de nombre para aplicar similitud (evita falsos positivos con nombres cortos)
LONGITUD_MIN_NOMBRE = 6

# Longitud mínima de apellido para búsqueda familiar (evita DIAZ, VERA, MORA, etc.)
APELLIDO_MIN_LEN = 6

# Apellidos muy comunes en Chile — excluidos para reducir falsos positivos
APELLIDOS_COMUNES = {
    # Top 100+ por frecuencia en la tabla candidato (medido empiricamente)
    'GONZALEZ','CONTRERAS','MARTINEZ','VARGAS','HERNANDEZ','VALENZUELA',
    'MORALES','RAMIREZ','RODRIGUEZ','FLORES','CASTRO','SEPULVEDA','FERNANDEZ',
    'CASTILLO','ESPINOZA','ALVAREZ','GARCIA','FUENTES','CORTES','GUTIERREZ',
    'VASQUEZ','TORRES','HERRERA','FIGUEROA','RIVERA','SANCHEZ','VERGARA',
    'CARRASCO','SANDOVAL','GALLARDO','CARDENAS','ALARCON','CARVAJAL',
    'RIQUELME','MIRANDA','SANHUEZA','SAAVEDRA','NAVARRO','SALAZAR','GARRIDO',
    'ZUNIGA','GUZMAN','URRUTIA','ORELLANA','OLIVARES','CACERES','JIMENEZ',
    'VELASQUEZ','PIZARRO','ROMERO','TAPIA','MOLINA','ARAYA','VALDES','MUNOZ',
    'ROJAS','DIAZ','REYES','ORTIZ','SILVA','SOTO','RAMOS','VEGA','NUNEZ',
    'RUIZ','MEDINA','MENDOZA','PAREDES','CAMPOS','RIOS','LEON','PENA','VERA',
    'CORNEJO','LAGOS','BRAVO','MARIN','POBLETE','HENRIQUEZ','GUERRERO',
    'OSORIO','MEDEL','CUEVAS','PINTO','VIDAL','GALVEZ','LEAL','BARRERA',
    'ACOSTA','ALVARADO','CORREA','ESPEJO','GAJARDO','INOSTROZA','JARA',
    'LABRA','LEIVA','LIRA','LLANOS','MENA','MEZA','MORA','NAVARRETE',
    'NEIRA','NOVOA','OJEDA','PALMA','PAVEZ','PEREIRA','PRADO','QUIROZ',
    'RECABARREN','REYES','RIOS','SALGADO','SOLIS','SUAREZ','TORO','TRONCOSO',
    'URIBE','VALLEJOS','VENEGAS','VILLALOBOS','VILLARROEL','ZAPATA',
}

# Nombres de pila comunes — para no confundirlos con apellidos
NOMBRES_PILA = {
    'JOSE','JUAN','LUIS','CARLOS','PEDRO','JORGE','MANUEL','FRANCISCO','MIGUEL',
    'ANDRES','SERGIO','PABLO','MARIO','RICARDO','RAFAEL','ANTONIO','ALBERTO',
    'DIEGO','GONZALO','ALEJANDRO','DANIEL','CRISTIAN','CHRISTIAN','ROBERTO',
    'CLAUDIO','RODRIGO','MAURICIO','VICTOR','EDUARDO','HERNAN','GABRIEL',
    'IGNACIO','NICOLAS','SEBASTIAN','PATRICIO','MARCELO','FELIPE','AGUSTIN',
    'MARIA','ANA','PATRICIA','CAROLINA','CLAUDIA','ANDREA','DANIELA','PAOLA',
    'VERONICA','CAROLA','JESSICA','MONICA','LORENA','JACQUELINE','ALEJANDRA',
    'VIVIANA','MARCELA','SANDRA','KAREN','KATHLEEN','VALERIA','NATALIA',
    'CAMILA','JAVIERA','FRANCISCA','CATALINA','CONSTANZA','FERNANDA','BARBARA',
    'ISABEL','ROSA','ELENA','TERESA','BEATRIZ','ANDREA','XIMENA','PILAR',
    'CRISTINA','GLORIA','JANET','EVELYN','ELIZABETH','MACARENA','PAULINA',
    'KARINA','LILIANA','SILVIA','ADRIANA','INGRID','REBECA','IRENE',
    'LAUTARO','BORIC','JAMES','JAMES',
}


def _normalizar(texto):
    """Quita tildes y pasa a uppercase para comparaciones."""
    txt = unicodedata.normalize("NFD", str(texto).upper())
    return "".join(c for c in txt if unicodedata.category(c) != "Mn").strip()


class IAFiscalizadora:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "ciudadano_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", "5432"),
            client_encoding='utf-8'
        )

    def detectar_conflictos_lobby(self):
        """
        Detecta el patrón AUTOLOBBY: un político tiene participación en una empresa
        Y esa empresa (o alguien que la representa) le hizo lobby.

        Cadena de joins:
          candidato
            -> participacion_societaria           (empresas donde tiene acciones/actividad)
            -> match_candidato_lobby              (sus registros en el sistema de lobby)
            -> temp_asistencia_pasivo             (audiencias en las que fue sujeto pasivo)
            -> temp_representaciones              (entidades que lo lobbied en cada audiencia)
            -> temp_audiencia                     (fecha y URL de referencia)

        Match empresa: por RUT exacto (cuando codigo_representado termina en 'r')
                       o por similitud de nombre (> 0.6) como fallback.
        """
        print("[IA] IA Fiscalizadora: Analizando cruces AUTOLOBBY...")
        print(f"   Umbral similitud: {SIMILITUD_MIN} | Longitud mínima nombre: {LONGITUD_MIN_NOMBRE}")

        query = f"""
            SELECT DISTINCT ON (c.id, ps.empresa_nombre, tr.representado)
                c.id                AS candidato_id,
                c.nombres,
                c.apellidos,
                ps.empresa_nombre   AS empresa_accionista,
                ps.empresa_rut,
                tr.representado     AS empresa_lobbied,
                tr.codigo_representado,
                ta.fechaevento,
                ta.uriaudiencia     AS url_referencia,
                CASE
                    WHEN tr.codigo_representado LIKE '%r'
                         AND RTRIM(tr.codigo_representado, 'r') = ps.empresa_rut
                    THEN 'RUT_EXACTO'
                    ELSE 'SIMILITUD_NOMBRE'
                END AS tipo_match
            FROM candidato c
            JOIN participacion_societaria ps
                ON ps.candidato_id = c.id
            JOIN match_candidato_lobby m
                ON m.rut = c.rut
            JOIN temp_asistencia_pasivo tap
                ON tap.codigopasivo = m.codigo_pasivo
            JOIN temp_representaciones tr
                ON tr.codigo_audiencia = tap.codigoaudiencia
            JOIN temp_audiencia ta
                ON ta.codigouri = tap.codigoaudiencia
            WHERE
                c.rut NOT LIKE 'CPLT-%%' AND c.rut NOT LIKE 'SERVEL-%%'
                AND length(tr.representado) >= {LONGITUD_MIN_NOMBRE}
                AND (
                    -- Match por RUT exacto (codigo termina en 'r' = es un RUT)
                    (
                        tr.codigo_representado LIKE '%%r'
                        AND RTRIM(tr.codigo_representado, 'r') = ps.empresa_rut
                    )
                    OR
                    -- Match por similitud de nombre
                    (
                        length(ps.empresa_nombre) >= {LONGITUD_MIN_NOMBRE}
                        AND similarity(ps.empresa_nombre, tr.representado) >= {SIMILITUD_MIN}
                    )
                )
            ORDER BY c.id, ps.empresa_nombre, tr.representado, ta.fechaevento DESC
        """

        try:
            with self.conn.cursor() as cur:
                print("   Ejecutando consulta (puede tardar 1-2 min)...")
                cur.execute(query)
                conflictos = cur.fetchall()

                if not conflictos:
                    print("[OK] No se detectaron conflictos de interés con los datos disponibles.")
                    return

                print(f"[!] {len(conflictos)} conflicto(s) detectado(s). Guardando alertas...")

                alertas_insertadas = 0
                for row in conflictos:
                    (cand_id, nombres, apellidos, empresa_accionista, empresa_rut,
                     empresa_lobbied, codigo_repr, fechaevento, url, tipo_match) = row

                    fecha_str = str(fechaevento)[:10] if fechaevento else 'fecha desconocida'
                    match_info = f"[{tipo_match}]"

                    detalle = (
                        f"El político {nombres} {apellidos} tiene participación en "
                        f"'{empresa_accionista}' (RUT: {empresa_rut or 'N/A'}) "
                        f"y el {fecha_str} recibió lobby de '{empresa_lobbied}' "
                        f"(código: {codigo_repr}). Match: {match_info}"
                    )

                    print(f"   [ALERTA] {nombres} {apellidos} | {empresa_accionista} <-> {empresa_lobbied} [{tipo_match}]")

                    cur.execute(
                        """INSERT INTO alerta_probidad
                           (candidato_id, tipo, gravedad, detalle, fuente_url, match_tipo)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT DO NOTHING""",
                        (cand_id, 'AUTOLOBBY_DETECTADO', 'ALTA', detalle, url, tipo_match)
                    )
                    alertas_insertadas += 1

            self.conn.commit()
            print(f"\n[OK] Análisis finalizado. {alertas_insertadas} alerta(s) guardada(s) en alerta_probidad.")

        except Exception as e:
            self.conn.rollback()
            print(f"[ERROR] Error en análisis de IA: {e}")
            raise

        finally:
            self.conn.close()


    def detectar_conflictos_familiares(self):
        """
        Detecta el patrón CONFLICTO_FAMILIAR_POSIBLE:
        Una persona con el mismo apellido que un funcionario le hizo lobby.

        Ejemplos reales:
          - Ministro KAST recibe lobby de alguien llamado KAST → posible familiar.
          - Diputado BORIC recibe lobby de empresa "SOCIEDAD BORIC HNOS" → señal.

        Lógica:
          1. Para cada candidato, extrae su apellido paterno (palabra 2 o 3 de nombre_limpio).
          2. En las audiencias donde fue sujeto pasivo, busca representados (personas o
             empresas en temp_representaciones) cuyo nombre contenga ese apellido.
          3. Filtra apellidos comunes y demasiado cortos.
          4. Distingue gravedad: MEDIA si el lobbista es persona natural,
             BAJA si es persona jurídica (empresa con apellido en el nombre).
        """
        print("\n[IA] Detector de conflictos familiares posibles...")
        print(f"    Apellido min {APELLIDO_MIN_LEN} chars | Excluidos {len(APELLIDOS_COMUNES)} apellidos comunes")

        # --- Cargar candidatos con apellido extraíble ---
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, rut, nombre_limpio
                FROM candidato
                WHERE rut NOT LIKE 'CPLT-%%' AND rut NOT LIKE 'SERVEL-%%'
                  AND nombre_limpio IS NOT NULL
                  AND nombre_limpio NOT IN ('NaN', 'NAN', '')
                  AND array_length(string_to_array(trim(nombre_limpio), ' '), 1) >= 3
            """)
            candidatos = cur.fetchall()

        print(f"    {len(candidatos):,} candidatos con nombre analizable.")

        # Extraer apellidos candidatos a revisar.
        # En Chile: NOMBRE [SEGUNDO_NOMBRE] APELLIDO_PATERNO APELLIDO_MATERNO
        # Los apellidos siempre van AL FINAL → tomamos penúltima y última palabra.
        candidatos_con_apellido = []
        for cid, rut, nombre in candidatos:
            partes = nombre.split()
            if len(partes) < 3:
                continue
            apellidos_candidato = []
            # Tomar las últimas 2 palabras (apellido_pat y apellido_mat)
            for ap_raw in partes[-2:]:
                ap = _normalizar(ap_raw)
                if (len(ap) >= APELLIDO_MIN_LEN
                        and ap not in APELLIDOS_COMUNES
                        and ap not in NOMBRES_PILA
                        and ap.isalpha()):
                    apellidos_candidato.append(ap)
            if apellidos_candidato:
                candidatos_con_apellido.append((cid, rut, nombre, apellidos_candidato))

        print(f"    {len(candidatos_con_apellido):,} candidatos con apellido filtrable.")

        # --- Agrupar por apellido y filtrar los muy frecuentes ---
        # Si un apellido aparece en > MAX_CANDIDATOS_POR_APELLIDO candidatos,
        # es demasiado común en la política chilena y genera ruido.
        # Solo apellidos que aparecen en MUY pocos candidatos son señal real.
        # >= 10 candidatos con el mismo apellido → apellido demasiado común.
        MAX_CANDIDATOS_POR_APELLIDO = 10
        from collections import defaultdict
        apellido_a_candidatos = defaultdict(list)
        for cid, rut, nombre, apellidos in candidatos_con_apellido:
            for ap in apellidos:
                apellido_a_candidatos[ap].append((cid, rut, nombre))

        apellido_a_candidatos = {
            ap: cands for ap, cands in apellido_a_candidatos.items()
            if len(cands) <= MAX_CANDIDATOS_POR_APELLIDO
        }

        print(f"    {len(apellido_a_candidatos):,} apellidos únicos (frecuencia <= {MAX_CANDIDATOS_POR_APELLIDO}) a buscar.")

        alertas_familiares = []

        with self.conn.cursor() as cur:
            for apellido, candidatos_ap in apellido_a_candidatos.items():
                # Para cada apellido, buscar en temp_representaciones
                # las audiencias donde ese apellido aparece en el representado
                cur.execute("""
                    SELECT DISTINCT
                        m.rut                   AS candidato_rut,
                        tr.representado         AS lobbista,
                        tr.personalidad,
                        ta.fechaevento,
                        ta.uriaudiencia
                    FROM match_candidato_lobby m
                    JOIN temp_asistencia_pasivo tap ON tap.codigopasivo = m.codigo_pasivo
                    JOIN temp_representaciones tr   ON tr.codigo_audiencia = tap.codigoaudiencia
                    JOIN temp_audiencia ta          ON ta.codigouri = tap.codigoaudiencia
                    WHERE unaccent(upper(tr.representado)) ILIKE %s
                      AND m.rut = ANY(%s)
                      -- Excluir si el lobbista tiene exactamente el mismo nombre (ya cubierto por AUTOLOBBY)
                      AND length(tr.representado) > %s
                    ORDER BY ta.fechaevento DESC
                """, (
                    f'%{apellido}%',
                    [rut for _, rut, _ in candidatos_ap],
                    len(apellido) + 2,  # el nombre del lobbista debe tener más chars que solo el apellido
                ))
                rows = cur.fetchall()

                # Cruzar resultados con candidatos que tienen ese apellido
                rut_to_candidato = {rut: (cid, nombre) for cid, rut, nombre in candidatos_ap}
                for candidato_rut, lobbista, personalidad, fechaevento, url in rows:
                    if candidato_rut not in rut_to_candidato:
                        continue
                    cid, nombre_funcionario = rut_to_candidato[candidato_rut]

                    # Verificar que el lobbista NO sea el mismo funcionario
                    if _normalizar(lobbista)[:20] == _normalizar(nombre_funcionario)[:20]:
                        continue

                    # Gravedad según tipo de lobbista
                    es_persona = personalidad and 'natural' in personalidad.lower()
                    gravedad = 'MEDIA' if es_persona else 'BAJA'

                    fecha_str = str(fechaevento)[:10] if fechaevento else 'fecha desconocida'
                    tipo_lobbista = 'persona natural' if es_persona else 'entidad/empresa'

                    detalle = (
                        f"El funcionario {nombre_funcionario} (apellido: {apellido}) "
                        f"recibio lobby el {fecha_str} de '{lobbista}' ({tipo_lobbista}), "
                        f"que comparte el mismo apellido. Posible vinculo familiar."
                    )

                    alertas_familiares.append((
                        cid, 'CONFLICTO_FAMILIAR_POSIBLE', gravedad,
                        detalle, url, 'APELLIDO_COMPARTIDO',
                        nombre_funcionario, lobbista, apellido,
                    ))

        if not alertas_familiares:
            print("    Sin conflictos familiares detectados con los datos actuales.")
            return 0

        # Deduplicar: un candidato puede aparecer múltiples veces con el mismo lobbista
        vistos = set()
        alertas_unicas = []
        for a in alertas_familiares:
            key = (a[0], a[6][:30], a[7][:30])  # (candidato_id, nombre[:30], lobbista[:30])
            if key not in vistos:
                vistos.add(key)
                alertas_unicas.append(a)

        print(f"\n    {len(alertas_unicas)} conflicto(s) familiar(es) único(s) detectado(s).")

        insertados = 0
        with self.conn.cursor() as cur:
            for (cid, tipo, gravedad, detalle, url, match_tipo,
                 nombre_func, lobbista, apellido) in alertas_unicas:
                print(f"    [FAMILIAR-{gravedad}] {nombre_func} <- {lobbista} ('{apellido}')")
                cur.execute("""
                    INSERT INTO alerta_probidad
                        (candidato_id, tipo, gravedad, detalle, fuente_url, match_tipo)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (cid, tipo, gravedad, detalle, url, match_tipo))
                insertados += cur.rowcount

        self.conn.commit()
        print(f"\n    [OK] {insertados} alerta(s) familiar(es) guardada(s).")
        return insertados


    def detectar_donante_proveedor(self):
        """
        Detecta el patron DONANTE_PROVEEDOR:
        Una empresa o persona que donó dinero a la campaña de un candidato
        TAMBIÉN recibió órdenes de compra del estado (tabla orden_compra).

        Logica:
          donante_electoral.rut_donante = orden_compra.rut_proveedor
          → el donante financió la campaña Y cobró contratos públicos.

        Gravedad:
          ALTA  si monto_ocs > 10.000.000 (diez millones CLP)
          MEDIA si monto_ocs <= 10.000.000
        """
        print("\n[IA] Detector DONANTE_PROVEEDOR...")

        tabla_existe = False
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name IN ('donante_electoral', 'orden_compra')
                HAVING COUNT(*) = 2
            """)
            tabla_existe = cur.fetchone() is not None

        if not tabla_existe:
            print("    Tablas donante_electoral u orden_compra no existen. Saltando.")
            return 0

        query = """
            SELECT
                de.candidato_id,
                de.rut_donante,
                MAX(de.nombre_donante)          AS nombre_donante,
                SUM(de.monto) FILTER (WHERE de.tipo = 'INGRESOS') AS monto_aportado,
                COUNT(DISTINCT oc.id)           AS n_ocs,
                SUM(oc.monto_pesos)             AS monto_ocs,
                STRING_AGG(DISTINCT oc.nombre_organismo, ' | ' ORDER BY oc.nombre_organismo)
                                                AS organismos
            FROM donante_electoral de
            JOIN orden_compra oc ON oc.rut_proveedor = de.rut_donante
            WHERE de.candidato_id IS NOT NULL
              AND de.tipo = 'INGRESOS'
              AND de.rut_donante IS NOT NULL
              AND length(de.rut_donante) >= 7
              -- Excluir referencias a formularios como nombre de donante
              AND de.nombre_donante NOT ILIKE 'Formulario%%'
              AND de.nombre_donante NOT ILIKE 'Form.%%'
              AND de.nombre_donante IS NOT NULL
              AND length(trim(de.nombre_donante)) > 4
              -- Excluir OCs con montos claramente corruptos (> 100 mil millones CLP)
              AND oc.monto_pesos BETWEEN 1 AND 100000000000
            GROUP BY de.candidato_id, de.rut_donante
            HAVING SUM(de.monto) FILTER (WHERE de.tipo = 'INGRESOS') > 0
            ORDER BY monto_ocs DESC
        """

        with self.conn.cursor() as cur:
            print("    Ejecutando cruce donante x orden_compra...")
            cur.execute(query)
            resultados = cur.fetchall()

            if not resultados:
                print("    Sin cruces DONANTE_PROVEEDOR detectados.")
                return 0

            print(f"    {len(resultados)} cruce(s) encontrado(s). Guardando alertas...")
            insertados = 0

            for (cand_id, rut_donante, nombre_donante,
                 monto_aportado, n_ocs, monto_ocs, organismos) in resultados:

                monto_ocs      = monto_ocs or 0
                monto_aportado = monto_aportado or 0
                gravedad = 'ALTA' if monto_ocs >= 10_000_000 else 'MEDIA'

                def fmt(n):
                    return f"${int(n):,}".replace(',', '.')

                detalle = (
                    f"El donante '{nombre_donante}' (RUT: {rut_donante}) "
                    f"aportó {fmt(monto_aportado)} CLP a la campaña de este candidato "
                    f"Y recibió {n_ocs} orden(es) de compra del estado "
                    f"por un total de {fmt(monto_ocs)} CLP. "
                    f"Organismos: {organismos or '—'}."
                )

                print(f"    [{gravedad}] cand_id={cand_id} | {nombre_donante} | OCs: {fmt(monto_ocs)}")

                cur.execute("""
                    INSERT INTO alerta_probidad
                        (candidato_id, tipo, gravedad, detalle, fuente_url, match_tipo)
                    VALUES (%s, 'DONANTE_PROVEEDOR', %s, %s, NULL, 'RUT_EXACTO')
                    ON CONFLICT DO NOTHING
                """, (cand_id, gravedad, detalle))
                insertados += cur.rowcount

        self.conn.commit()
        print(f"\n    [OK] {insertados} alerta(s) DONANTE_PROVEEDOR guardada(s).")
        return insertados


if __name__ == "__main__":
    ia = IAFiscalizadora()
    ia.detectar_conflictos_lobby()

    ia2 = IAFiscalizadora()
    ia2.detectar_conflictos_familiares()

    ia3 = IAFiscalizadora()
    ia3.detectar_donante_proveedor()
