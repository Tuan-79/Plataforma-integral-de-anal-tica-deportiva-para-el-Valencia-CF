import pandas as pd # type: ignore
import psycopg2 # type: ignore
from sklearn.ensemble import RandomForestRegressor # type: ignore
from sklearn.model_selection import train_test_split # type: ignore
from sklearn.metrics import mean_absolute_error # type: ignore
import numpy as np # type: ignore

print("=============================================")
print(" INICIANDO MOTOR DE IA: RANDOM FOREST")
print("=============================================")

try:
    # 1. CONEXIÓN Y EXTRACCIÓN (Leyendo el pasado)
    print(" Conectando a PostgreSQL y extrayendo datos...")
    conn = psycopg2.connect(
        host="localhost", database="TFG", user="postgres", password="scadelantero4"
    )
    
    # Extraemos todos los datos relevantes para entrenar a la IA
    query = """
        SELECT h.jugador_id, h.club_id, h.temporada_id, j.nombre, 
               h.edad, h.minutos, h.goles, h.asistencias, h.partidos, 
               h.amarillas, h.rojas, h.numero_lesiones_25_26, h.valor_mercado_€
        FROM hechos_jugadores h
        JOIN dim_jugador j ON h.jugador_id = j.id
        WHERE h.valor_mercado_€ > 0 -- Solo entrenamos con jugadores que tienen valor
    """
    df = pd.read_sql_query(query, conn)
    
    # 2. PREPARACIÓN DE DATOS (Feature Engineering)
    print(f" Datos cargados: {len(df)} jugadores encontrados.")
    print("  Preparando variables para el entrenamiento...")
    
    # Seleccionamos qué variables va a mirar la IA para aprender (Features)
    features = ['edad', 'minutos', 'goles', 'asistencias', 'partidos', 
                'amarillas', 'rojas', 'numero_lesiones_25_26']
    
    X = df[features].fillna(0) # Variables predictoras (X)
    y = df['valor_mercado_€']  # Lo que queremos adivinar (Y)

    # 3. ENTRENAMIENTO DEL MODELO (Machine Learning)
    # Dividimos: 80% para estudiar y aprender, 20% para hacerle un examen
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(" Entrenando el modelo Random Forest (100 árboles de decisión)...")
    modelo = RandomForestRegressor(n_estimators=100, random_state=42)
    modelo.fit(X_train, y_train) # ¡Aquí ocurre la magia matemática!
    
    # Evaluamos qué tan bueno es el modelo en el examen
    predicciones_test = modelo.predict(X_test)
    mae = mean_absolute_error(y_test, predicciones_test)
    print(f" Error Absoluto Medio del modelo: {mae:,.0f} €")
    
    # 4. PREDICCIÓN GLOBAL Y CÁLCULO DE OPORTUNIDADES
    print(" Prediciendo el valor justo para toda LaLiga...")
    df['valor_predictivo_€'] = modelo.predict(X)
    
    # Métrica CLAVE de negocio: ¿Está barato o caro?
    # Si la IA dice que vale 10M y cuesta 2M, el desfase es +8M (Gema Oculta)
    df['desfase_mercado_€'] = df['valor_predictivo_€'] - df['valor_mercado_€']

    # 5. CARGA EN BASE DE DATOS (Modificando PostgreSQL)
    print(" Guardando predicciones en la base de datos...")
    cursor = conn.cursor()
    
    # Creamos las columnas si no existen de ejecuciones anteriores
    cursor.execute("""
        ALTER TABLE hechos_jugadores 
        ADD COLUMN IF NOT EXISTS valor_predictivo_€ NUMERIC,
        ADD COLUMN IF NOT EXISTS desfase_mercado_€ NUMERIC;
    """)
    
    # Actualizamos jugador a jugador con su nueva predicción
    for _, row in df.iterrows():
        cursor.execute("""
            UPDATE hechos_jugadores 
            SET valor_predictivo_€ = %s, desfase_mercado_€ = %s
            WHERE jugador_id = %s AND club_id = %s AND temporada_id = %s
        """, (row['valor_predictivo_€'], row['desfase_mercado_€'], 
              row['jugador_id'], row['club_id'], row['temporada_id']))
        
    conn.commit()
    print(" ¡IA EJECUTADA CON ÉXITO! Predicciones guardadas.")

except Exception as e:
    print(f" ERROR EN EL MOTOR DE IA: {e}")
    if 'conn' in locals() and conn:
        conn.rollback()
finally:
    if 'cursor' in locals() and cursor: cursor.close()
    if 'conn' in locals() and conn: conn.close()