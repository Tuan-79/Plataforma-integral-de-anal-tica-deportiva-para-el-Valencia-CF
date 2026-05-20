import psycopg2 # type: ignore
import pandas as pd # type: ignore
import numpy as np # type: ignore

print(" Iniciando motor de cálculo de Métricas Avanzadas...")

# 1. LA CADENA DE CONEXIÓN MÁGICA
# Le damos a Pandas la dirección exacta con el formato de SQLAlchemy
conexion_url = 'postgresql+psycopg2://postgres:scadelantero4@localhost/TFG'

# 2. Extraer los Hechos Crudos
consulta_sql = """
    SELECT 
        h.jugador_id, h.club_id, h.temporada_id,
        h.edad, h.numero_lesiones_25_26,
        h.minutos, h.partidos, h.goles, h.asistencias, 
        h.amarillas, h.rojas, h.goles_encajados, h.a_cero,
        h.valor_mercado_€, h.sueldo_anual_€,
        j.posicion
    FROM hechos_jugadores h
    JOIN dim_jugador j ON h.jugador_id = j.id
"""

try:
    # Le pasamos la URL directamente a Pandas. Él usa SQLAlchemy por detrás automáticamente.
    df = pd.read_sql_query(consulta_sql, con=conexion_url)
    print(" Conexión a PostgreSQL establecida y datos extraídos.")
    print(f" Analizando el rendimiento de {len(df)} registros...")
except Exception as e:
    print(f" Error al conectar o extraer los datos: {e}")
    exit()

# 3. EL LABORATORIO (Feature Engineering)

# A. Base segura para no dividir por cero
minutos_seguros = np.where(df['minutos'] == 0, 1, df['minutos'])
partidos_seguros = np.where(df['partidos'] == 0, 1, df['partidos'])
aportacion_total = df['goles'] + df['asistencias']

# B. Producción Ofensiva Per 90 (Redondeo a 2 decimales explícito)
df['goles_por_90'] = np.round((df['goles'] / minutos_seguros) * 90, 2)
df['asist_por_90'] = np.round((df['asistencias'] / minutos_seguros) * 90, 2)
# Sumamos y volvemos a redondear para evitar decimales residuales tipo 0.30000001
df['produccion_90'] = (df['goles_por_90'] + df['asist_por_90']).round(2)

# C. Fiabilidad y Confianza del Entrenador
peso_tarjetas = df['amarillas'] + (df['rojas'] * 2)
df['minutos_por_tarjeta'] = np.where(peso_tarjetas > 0, np.round(df['minutos'] / peso_tarjetas, 0), df['minutos']).astype(int)

# ¿Qué porcentaje de los minutos posibles juega realmente?
df['porcentaje_titularidad'] = np.round((df['minutos'] / (partidos_seguros * 90)) * 100, 2)

#  CORRECCIÓN DE OUTLIERS: Topamos el porcentaje al 100% por los tiempos de descuento y prórrogas
df['porcentaje_titularidad'] = np.where(df['porcentaje_titularidad'] > 100.0, 100.0, df['porcentaje_titularidad'])

# D. Métricas Defensivas (Especialmente útiles para Porteros y Defensas)
df['minutos_por_gol_encajado'] = np.where(df['goles_encajados'] > 0, np.round(df['minutos'] / df['goles_encajados'], 0), df['minutos']).astype(int)
df['tasa_porteria_cero'] = np.round((df['a_cero'] / partidos_seguros) * 100, 2)

# E. Eficiencia Económica (ROI y Valor)
df['coste_por_produccion_€'] = np.where(aportacion_total > 0, np.round(df['valor_mercado_€'] / aportacion_total, 0), 0).astype(int)

# Retorno de inversión salarial (Sueldo que cuesta cada gol/asistencia)
# Si el sueldo_anual_€ fuera nulo o 0, evitamos errores
sueldo_seguro = df['sueldo_anual_€'].fillna(0)
df['roi_salarial_€'] = np.where(aportacion_total > 0, np.round(sueldo_seguro / aportacion_total, 0), 0).astype(int)

# Valor de Mercado por cada punto de Producción/90 (Gangas vs Sobrevalorados)
# Expresado en Millones de Euros (Ej: 2.5 Millones por cada 1.0 de produccion_90)
df['valor_por_produccion_m'] = np.where(df['produccion_90'] > 0, np.round((df['valor_mercado_€'] / 1000000) / df['produccion_90'], 2), 0.0)

# F. Limpieza de métricas fantasma (Jugadores que realmente tienen 0 minutos)
df.loc[df['minutos'] == 0, ['goles_por_90', 'asist_por_90', 'produccion_90', 'minutos_por_tarjeta', 'porcentaje_titularidad', 'minutos_por_gol_encajado', 'tasa_porteria_cero', 'valor_por_produccion_m']] = 0

# --- NUEVAS MÉTRICAS DE ÉLITE (DIRECTOR DEPORTIVO) ---

# 1. Costo Operativo por Minuto (€/min)
# ¿A cómo sale el minuto que este jugador está en el campo?
df['costo_por_minuto_€'] = np.where(df['minutos'] > 0, np.round(sueldo_seguro / df['minutos'], 2), sueldo_seguro)

# 2. Dependencia Ofensiva (%) adaptada a MULTICLUB
# Agrupamos por club_id para saber los goles y asistencias totales de CADA EQUIPO
df_goles_equipo = df.groupby('club_id')[['goles', 'asistencias']].sum()
df_goles_equipo['produccion_total_equipo'] = df_goles_equipo['goles'] + df_goles_equipo['asistencias']

# Mapeamos (asignamos) ese total del equipo a cada jugador según a qué club_id pertenece
df['produccion_total_equipo'] = df['club_id'].map(df_goles_equipo['produccion_total_equipo'])

# Evitamos dividir por cero si un equipo llevara 0 goles
produccion_equipo_segura = np.where(df['produccion_total_equipo'] > 0, df['produccion_total_equipo'], 1)

# Calculamos el porcentaje
df['dependencia_ofensiva_pct'] = np.round((aportacion_total / produccion_equipo_segura) * 100, 2)

# 3. Ratio de Revalorización (Juventud vs Valor)
# Extraemos la edad de la otra tabla (asegúrate de traer j.edad en tu SELECT si no la tienes, o calcularla con h.edad)
# Como la edad la tenemos en hechos_jugadores (h.edad), la usamos directo:
edad_segura = np.where(df['edad'].astype(float) > 0, df['edad'].astype(float), 25.0) # Por si hay algún 0, asumimos 25
df['ratio_revalorizacion'] = np.round(df['valor_mercado_€'] / edad_segura, 0).astype(int)

# 4. Índice de Fragilidad (Lesiones por cada 10 Partidos)
# ¿Cuántas lesiones sufre el jugador estadísticamente por cada 10 partidos jugados?
df['lesiones_por_10_partidos'] = np.round((df['numero_lesiones_25_26'] / partidos_seguros) * 10, 2)

# 4. Actualizar la Base de Datos (Volvemos a psycopg2 solo para ejecutar el UPDATE directo)
print(" Guardando 14 métricas avanzadas para cada jugador en la Base de Datos...")

conn = psycopg2.connect(host="localhost", database="TFG", user="postgres", password="scadelantero4")
cursor = conn.cursor()

query_update = """
    UPDATE hechos_jugadores 
    SET 
        goles_por_90 = %s,
        asist_por_90 = %s,
        produccion_90 = %s,
        minutos_por_tarjeta = %s,
        coste_por_produccion_€ = %s,
        porcentaje_titularidad = %s,
        minutos_por_gol_encajado = %s,
        tasa_porteria_cero = %s,
        roi_salarial_€ = %s,
        valor_por_produccion_m = %s,
        costo_por_minuto_€ = %s,
        dependencia_ofensiva_pct = %s,
        ratio_revalorizacion = %s,
        lesiones_por_10_partidos = %s
    WHERE jugador_id = %s AND club_id = %s AND temporada_id = %s
"""

for _, row in df.iterrows():
    cursor.execute(query_update, (
        row['goles_por_90'], row['asist_por_90'], row['produccion_90'],
        row['minutos_por_tarjeta'], row['coste_por_produccion_€'],
        row['porcentaje_titularidad'], row['minutos_por_gol_encajado'],
        row['tasa_porteria_cero'], row['roi_salarial_€'], row['valor_por_produccion_m'],
        row['costo_por_minuto_€'], row['dependencia_ofensiva_pct'], row['ratio_revalorizacion'], row['lesiones_por_10_partidos'],
        row['jugador_id'], row['club_id'], row['temporada_id']
    ))

conn.commit()
cursor.close()
conn.close()

print(" ¡Análisis completado! Data Warehouse listo para Power BI.")