from selenium.webdriver.common.by import By # type: ignore
from selenium.webdriver.support.ui import WebDriverWait # type: ignore
from selenium.webdriver.support import expected_conditions as EC # type: ignore
from selenium.common.exceptions import TimeoutException # type: ignore
import undetected_chromedriver as uc # type: ignore
from bs4 import BeautifulSoup # type: ignore
import pandas as pd # type: ignore
import numpy as np # type: ignore
import psycopg2 # type: ignore
import time
import platform
import re
import random

def obtener_estadisticas(driver, url_profil, nombre_tag):
    stats = {
        "partidos": 0, "goles": 0, "asistencias": 0,
        "amarillas": 0, "seg_amarillas": 0, "rojas": 0,
        "minutos": 0, "goles_encajados": 0, "a_cero": 0,
        "numero_lesiones_25_26": 0,
        "ultima_lesion": "Ninguna registrada",
        "dias_recup_ultima_lesion": 0,
        "altura_cm": 0,
        "pie_bueno": "Desconocido",
        "fin_contrato": None,
        "canterano_valencia": False,
        "ultimo_club": "Desconocido",
        "segunda_posicion": "Ninguna",
        "agencia": "Sin agente",
        "sueldo_anual_€": 0
    }

    # EL GUARDAESPALDAS ANTI-CAPTCHA
    def cargar_pagina_segura(url, selector_esperado, tipo_selector=By.CSS_SELECTOR, tiempo_max=20):
        driver.get(url)
        try:
            # Primero intentamos una carga normal y rápida (5 segundos)
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((tipo_selector, selector_esperado)))
            return True
        except TimeoutException:
            # Si a los 5 segundos no está el contenido, asumimos que saltó Cloudflare
            print(f"\n ¡ALTO! Posible Captcha detectado en: {url}")
            print(f" Por favor, ve a la ventana de Chrome. Tienes {tiempo_max} segundos para hacer clic en 'Soy humano'...")

            # LA ALARMA SONORA
            try:
                if platform.system() == "Windows":
                    import winsound
                    winsound.Beep(2500, 300) # Frecuencia 2500Hz, 0.3 segundos
                    time.sleep(0.1)
                    winsound.Beep(2500, 300) # Segundo pitido
                else:
                    print('\a', end='', flush=True) # Pitido estándar en Mac/Linux
            except:
                pass # Si no hay altavoces o da error, que el código siga vivo
            
            try:
                # Damos el tiempo largo para resolver el Captcha
                WebDriverWait(driver, tiempo_max).until(EC.presence_of_element_located((tipo_selector, selector_esperado)))
                print(" ¡Captcha superado! Retomando la extracción automática...\n")
                return True
            except TimeoutException:
                print(" ERROR: El tiempo expiró. Saltando esta URL para que el script no muera.")
                return False
    
    try:
        # =========================================================
        # 0️- URL DEL PERFIL PRINCIPAL
        # =========================================================
        time.sleep(3) # Espera un poco para no ir a la velocidad de la luz

        # Usamos el guardaespaldas esperando ver la clase "data-header"
        if not cargar_pagina_segura(url_profil, "data-header", By.CLASS_NAME):
            return stats # Si falla y expira el tiempo, devolvemos stats a 0 y pasamos al siguiente
        
        soup_profil = BeautifulSoup(driver.page_source, "html.parser") # Leemos el HTML del Chrome real
        info_labels = soup_profil.find_all("span", class_="info-table__content--regular")
        
        print("Extrayendo datos del perfil principal...") # Solo para confirmar que entramos en esta sección
        for label in info_labels:
            texto_label = label.get_text(strip=True).lower()
            valor_tag = label.find_next_sibling("span", class_="info-table__content--bold")
            
            if valor_tag:
                valor_texto = valor_tag.get_text(strip=True)
                
                if "altura:" in texto_label:
                    match = re.search(r'(\d)[.,](\d{2})', valor_texto)
                    if match:
                        stats["altura_cm"] = int(match.group(1)) * 100 + int(match.group(2))
                        
                elif "pie:" in texto_label:
                    stats["pie_bueno"] = valor_texto
                    
                elif "contrato hasta:" in texto_label:
                    if valor_texto != "-" and "/" in valor_texto:
                        partes = valor_texto.split("/")
                        if len(partes) == 3:
                            stats["fin_contrato"] = f"{partes[2]}-{partes[1]}-{partes[0]}"
                        
                elif "agente:" in texto_label or "representación:" in texto_label:
                    stats["agencia"] = valor_texto

        # Segunda Posición
        otras_pos_dt = soup_profil.find("dt", string=re.compile("Otras posiciones|Posición secundaria", re.IGNORECASE))
        if otras_pos_dt:
            otras_pos_dd = otras_pos_dt.find_next_sibling("dd")
            if otras_pos_dd: stats["segunda_posicion"] = ", ".join(list(otras_pos_dd.stripped_strings))


        # =========================================================
        # 1️- URL DE RENDIMIENTO
        # =========================================================
        url_stats = url_profil.replace("/profil/", "/leistungsdaten/")
        time.sleep(3)
        
        if cargar_pagina_segura(url_stats, "data-header", By.CLASS_NAME):
            soup_stats = BeautifulSoup(driver.page_source, "html.parser")
            tablas = soup_stats.find_all("table", class_="items")

            print("Extrayendo estadísticas de rendimiento...") # Solo para confirmar que entramos en esta sección

            def limpiar_numero(texto):
                texto = texto.replace("'", "").replace(".", "").strip()
                return int(texto) if texto and texto != '-' else 0

            for tabla in tablas:
                filas = tabla.find_all("tr")
                for fila in filas:
                    if "total" in fila.get_text(" ", strip=True).lower():
                        columnas = fila.find_all(["td", "th"])
                        es_portero = len(columnas) >= 10

                        # nombre_debug = nombre_tag.text.strip() if nombre_tag else 'Jugador'
                        # print(f"DEBUG {url_profil.split('/')[4]} -> {nombre_debug}: {[c.text.strip() for c in columnas]}")
                        
                        try:
                            stats["partidos"] = limpiar_numero(columnas[2].text)
                            stats["goles"] = limpiar_numero(columnas[3].text)
                            stats["minutos"] = limpiar_numero(columnas[-1].text)
                            
                            if es_portero:
                                stats["amarillas"] = limpiar_numero(columnas[4].text)
                                stats["seg_amarillas"] = limpiar_numero(columnas[5].text)
                                stats["rojas"] = limpiar_numero(columnas[6].text)
                                stats["goles_encajados"] = limpiar_numero(columnas[7].text)
                                stats["a_cero"] = limpiar_numero(columnas[8].text)
                                stats["asistencias"] = 0 
                            else:
                                stats["asistencias"] = limpiar_numero(columnas[4].text)
                                stats["amarillas"] = limpiar_numero(columnas[5].text)
                                stats["seg_amarillas"] = limpiar_numero(columnas[6].text)
                                stats["rojas"] = limpiar_numero(columnas[7].text)
                                stats["goles_encajados"] = 0
                                stats["a_cero"] = 0
                                
                        except (ValueError, IndexError):
                            pass
                        break
        
        # =========================================================
        # 2️- NUEVA PETICIÓN: URL DE LESIONES
        # =========================================================
        url_lesiones = url_profil.replace("/profil/", "/verletzungen/")
        time.sleep(3)
        
        if cargar_pagina_segura(url_lesiones, "data-header", By.CLASS_NAME):
            soup_lesiones = BeautifulSoup(driver.page_source, "html.parser")
            tabla_lesiones = soup_lesiones.find("table", class_="items")
            print("Extrayendo estadísticas de lesiones...") # Solo para confirmar que entramos en esta sección
            
            if tabla_lesiones:
                cuerpo_tabla = tabla_lesiones.find("tbody")
                if cuerpo_tabla:
                    filas_lesiones = cuerpo_tabla.find_all("tr")
                    
                    if len(filas_lesiones) == 1 and ("sin lesiones" in filas_lesiones[0].text.lower() or "no hay datos" in filas_lesiones[0].text.lower()):
                        stats["numero_lesiones_25_26"] = 0
                        stats["ultima_lesion"] = "Ninguna registrada"
                        stats["dias_recup_ultima_lesion"] = 0
                    else:
                        contador_25_26 = 0
                        es_primera_fila = True

                        for fila_lesion in filas_lesiones:
                            columnas_lesion = fila_lesion.find_all("td")
                            
                            if len(columnas_lesion) >= 5: 
                                temporada = columnas_lesion[0].get_text(strip=True)
                                
                                if "25/26" in temporada:
                                    contador_25_26 += 1
                                
                                if es_primera_fila:
                                    celda_texto = fila_lesion.find("td", class_="hauptlink")
                                    if celda_texto:
                                        stats["ultima_lesion"] = celda_texto.get_text(separator=" ", strip=True) 
                                    else:
                                        texto_1 = columnas_lesion[1].get_text(separator=" ", strip=True)
                                        texto_2 = columnas_lesion[2].get_text(separator=" ", strip=True)
                                        stats["ultima_lesion"] = texto_1 if len(texto_1) > len(texto_2) else texto_2
                                    
                                    stats["dias_recup_ultima_lesion"] = 0 
                                    for celda in columnas_lesion:
                                        texto_celda = celda.get_text(strip=True).lower()
                                        if 'dias' in texto_celda or 'días' in texto_celda:
                                            match_dias = re.search(r'(\d+)', texto_celda)
                                            if match_dias:
                                                stats["dias_recup_ultima_lesion"] = int(match_dias.group(1))
                                            break 
                                            
                                    es_primera_fila = False
                        
                        stats["numero_lesiones_25_26"] = contador_25_26

        # =========================================================
        # =========================================================
        # =========================================================
        # =========================================================
        # 3️- NUEVA PETICIÓN: URL DE FICHAJES (Último Club)
        # =========================================================
        url_fichajes = url_profil.replace("/profil/", "/transfers/").split("/plus/0")[0]
        driver.get(url_fichajes)
        
        # ESPERA SEGURA CON ALARMA INTEGRADA
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "data-header")))
        except TimeoutException:
            print(f"\n ¡ALTO! Posible Captcha detectado en Fichajes: {url_fichajes}")
            try:
                import platform
                if platform.system() == "Windows":
                    import winsound; winsound.Beep(2500, 300); time.sleep(0.1); winsound.Beep(2500, 300)
                else: print('\a', end='', flush=True)
            except: pass
            
            print(" Tienes 30 segundos para resolverlo...")
            try:
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "data-header")))
                print(" ¡Captcha superado! Seguimos...")
            except:
                print(" Falló la carga tras el captcha. Saltando jugador.")
                pass

        print(f"Extrayendo historial de fichajes...")
        print(f"   Despertando a la web (haciendo Scroll)...")
        
        # Bajamos en 4 tramos simulando la rueda del ratón
        for i in range(1, 5):
            # Baja de 700 en 700 píxeles
            driver.execute_script(f"window.scrollTo(0, {i * 700});")
            time.sleep(1.5) # Pausa para que a la web le dé tiempo a hacer la petición

        # Subir un poco hacia arriba (activa el script de Transfermarkt)
        driver.execute_script("window.scrollBy(0, -300);")
        time.sleep(1)

        html_historial = ""
        
        # BUCLE DE ESPERA: Le damos tiempo a la web para que cargue los datos tras el scroll
        for intento in range(4):
            time.sleep(3) 
            
            # Sacamos el HTML (Shadow DOM) o de la tabla clásica
            html_historial = driver.execute_script('''
                var host = document.querySelector("tm-player-transfer-history");
                if (host && host.shadowRoot) {
                    var enlaces = host.shadowRoot.querySelectorAll("a");
                    if (enlaces.length > 0) return host.shadowRoot.innerHTML;
                }
                var tablas = document.querySelectorAll("table");
                for (var i=0; i<tablas.length; i++) {
                    if (tablas[i].innerText.toLowerCase().includes("temporada")) {
                        return tablas[i].innerHTML;
                    }
                }
                return "";
            ''')
            
            # Si el HTML ya no está vacío, rompemos el bucle y avanzamos
            if html_historial and len(html_historial) > 100:
                break
            else:
                print(f"    Intento {intento + 1}/4... La web sigue cargando...")
                driver.execute_script("window.scrollBy(0, 300);") # Un poco más de scroll por si acaso

        # --- ANÁLISIS DE LOS DATOS CON PYTHON ---
        if html_historial:
            soup_hist = BeautifulSoup(html_historial, "html.parser")
            
            # Buscamos cualquier contenedor que parezca una fila (Svelte usa section, HTML usa tr)
            filas = soup_hist.find_all(["section", "tr"])
            print(f"    ¡Datos capturados! Analizando {len(filas)} posibles movimientos...")
            
            encontrado = False
            for fila in filas:
                # Sacamos todo el texto para detectar cesiones
                texto_fila = fila.get_text(separator=" ", strip=True).lower()
                
                enlaces_equipos = fila.find_all("a", href=re.compile(r"/verein/|/vereins/"))
                nombres_equipos = [a.get_text(strip=True) for a in enlaces_equipos if a.get_text(strip=True)]
                
                if len(nombres_equipos) >= 2:
                    club_origen = nombres_equipos[0]
                    club_destino = nombres_equipos[1]
                    
                    # Buscamos cuando llega al Valencia CF
                    if any(v in club_destino.lower() for v in ["valencia", "v. mestalla"]):
                        
                        # ESCUDO ANTI-CESIONES
                        if "fin de cesión" in texto_fila or "end of loan" in texto_fila:
                            print(f"    Saltando retorno de cesión desde {club_origen}...")
                            continue 
                            
                        print(f"    ¡BINGO! Llegó al Valencia procedente de: {club_origen}")
                        
                        palabras_cantera = ["mestalla", "valencia b", "valencia juv", "fútbol base", "valencia"]
                        if any(p in club_origen.lower() for p in palabras_cantera):
                            stats["canterano_valencia"] = True
                            stats["ultimo_club"] = "Canterano"
                        else:
                            stats["canterano_valencia"] = False
                            stats["ultimo_club"] = club_origen
                            
                        encontrado = True
                        break # ¡Dato REAL cazado!
                        
            if not encontrado:
                print("   No se encontró un fichaje definitivo por el Valencia en esta tabla.")
        else:
            print("   Fallo crítico: El historial no cargó ni haciendo scroll.")
                        
        return stats

    except Exception as e:
        print(f"Error general extrayendo datos con Selenium: {e}")
        return stats


# =========================================================================
# INICIO DEL SCRIPT PRINCIPAL (16 LALIGA)
# =========================================================================

options = uc.ChromeOptions()
options.add_argument('--disable-background-timer-throttling') 
options.add_argument('--disable-backgrounding-occluded-windows') 
options.add_argument('--disable-renderer-backgrounding') 
options.add_argument('--window-size=1920,1080') 

driver = uc.Chrome(options=options)

# 16 EQUIPOS DE COMPETENCIA DIRECTA
equipos_objetivo = {
    "Valencia CF": "https://www.transfermarkt.es/valencia-cf/startseite/verein/1049",
    "Villarreal CF": "https://www.transfermarkt.es/villarreal-cf/startseite/verein/1050",
    "Real Betis": "https://www.transfermarkt.es/real-betis-balompie/startseite/verein/150",
    "Sevilla FC": "https://www.transfermarkt.es/sevilla-fc/startseite/verein/368",
    "Real Sociedad": "https://www.transfermarkt.es/real-sociedad/startseite/verein/681",
    "Athletic Club": "https://www.transfermarkt.es/athletic-club/startseite/verein/621",
    "CA Osasuna": "https://www.transfermarkt.es/ca-osasuna/startseite/verein/331",
    "RC Celta de Vigo": "https://www.transfermarkt.es/rc-celta-de-vigo/startseite/verein/940",
    "RCD Mallorca": "https://www.transfermarkt.es/rcd-mallorca/startseite/verein/237",
    "Girona FC": "https://www.transfermarkt.es/girona-fc/startseite/verein/12321",
    "Getafe CF": "https://www.transfermarkt.es/getafe-cf/startseite/verein/3709",
    "RCD Espanyol": "https://www.transfermarkt.es/rcd-espanyol/startseite/verein/714",
    "Rayo Vallecano": "https://www.transfermarkt.es/rayo-vallecano/startseite/verein/367",
    "Deportivo Alavés": "https://www.transfermarkt.es/deportivo-alaves/startseite/verein/1108",
    "Elche CF": "https://www.transfermarkt.es/elche-cf/startseite/verein/1531",
    "Levante UD": "https://www.transfermarkt.es/levante-ud/startseite/verein/3368"
}


jugadores = [] # Lista global para los ~400 jugadores

for nombre_equipo, url_equipo in equipos_objetivo.items():
    print(f"\n{'='*60}")
    print(f"VIAJANDO A LA CIUDAD DEL: {nombre_equipo}")
    print(f"{'='*60}")
    
    driver.get(url_equipo)
    time.sleep(random.uniform(2, 4)) # Comportamiento humano

    # ALARMA Y ESPERA PARA LA PÁGINA PRINCIPAL
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.items tbody tr")))
    except:
        print(f"\n ¡ALTO! Captcha detectado en la plantilla del {nombre_equipo}.")
        import platform
        if platform.system() == "Windows":
            import winsound; winsound.Beep(2500, 300); time.sleep(0.1); winsound.Beep(2500, 300)
        else:
            print('\a', end='', flush=True)
        print("Tienes 30 segundos para resolverlo...")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.items tbody tr")))

    # AUTOMATIZACIÓN DE COOKIES
    try:
        boton_cookies = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Aceptar y continuar')] | //button[contains(@class, 'accept')]")))
        boton_cookies.click()
    except:
        pass

    soup = BeautifulSoup(driver.page_source, "html.parser")
    filas = soup.select("table.items tbody tr")

    print(f"¡ÉXITO! Se encontraron {int(len(filas)/3)} jugadores en el {nombre_equipo}. Iniciando extracción...")

    for fila in filas:
        nombre_tag = fila.select_one("td.hauptlink a")
        posicion_tag = fila.select_one("td.posrela")
        celdas = fila.select("td")
        valor_tag = fila.select_one("td.rechts.hauptlink")

        if nombre_tag and valor_tag:
            nombre = nombre_tag.text.strip()

            if not nombre or nombre == "":
                continue
            
            link = "https://www.transfermarkt.es" + nombre_tag["href"] + "/plus/0?saison=2025"

        posicion = ""
        if posicion_tag:
            texto_pos = posicion_tag.get_text(separator=" ").strip()
            texto_pos = " ".join(texto_pos.split())
            if nombre in texto_pos:
                texto_pos = texto_pos.replace(nombre, "").strip()
            posicion = texto_pos

        edad = ""
        if len(celdas) > 5:
            edad_text = celdas[5].text.strip()
            if "(" in edad_text:
                edad = edad_text.split("(")[-1].replace(")", "")
            else:
                edad = edad_text

        valor_numerico = 0
        if valor_tag:
            valor_texto = valor_tag.text.strip().lower()
            valor_limpio = valor_texto.replace("€", "").strip()
            if valor_limpio != "-" and valor_limpio != "":
                try:
                    if "mill." in valor_limpio:
                        numero_str = valor_limpio.replace("mill.", "").replace(",", ".").strip()
                        valor_numerico = int(float(numero_str) * 1000000)
                    elif "mil" in valor_limpio:
                        numero_str = valor_limpio.replace("mil", "").replace(",", ".").strip()
                        valor_numerico = int(float(numero_str) * 1000)
                except ValueError:
                    valor_numerico = 0

        if not edad or edad == "":
            continue

        print(f"--------------------------------------------------")
        print(f" [{nombre_equipo}] Procesando a: {nombre} | Edad: {edad} | Valor: {valor_numerico}")

        stats = obtener_estadisticas(driver, link, nombre_tag)

        jugadores.append({
            "club_actual": nombre_equipo,
            "nombre": nombre,
            "posicion": posicion,
            "edad": edad,
            "valor_mercado_€": valor_numerico,
            "link": link,
            "goles": stats["goles"],
            "asistencias": stats["asistencias"],
            "minutos": stats["minutos"],
            "partidos": stats["partidos"],
            "amarillas": stats["amarillas"],
            "seg_amarillas": stats["seg_amarillas"],
            "rojas": stats["rojas"],
            "goles_encajados": stats["goles_encajados"],
            "a_cero": stats["a_cero"],
            "ultima_lesion": stats["ultima_lesion"],
            "numero_lesiones_25_26": stats["numero_lesiones_25_26"],
            "dias_recup_ultima_lesion": stats["dias_recup_ultima_lesion"],
            "altura_cm": stats["altura_cm"],
            "pie_bueno": stats["pie_bueno"],
            "fin_contrato": stats["fin_contrato"],
            "canterano_valencia": stats["canterano_valencia"],
            "ultimo_club": stats["ultimo_club"],
            "segunda_posicion": stats["segunda_posicion"],
            "agencia": stats["agencia"],
            "sueldo_anual_€": stats["sueldo_anual_€"]
        })

driver.quit()
print(" Extracción de los 16 clubes completada. Guardando datos en PostgreSQL...")

# =========================================================
# ETL: PANDAS Y POSTGRESQL
# =========================================================

df = pd.DataFrame(jugadores)
df = df.drop_duplicates(subset=["nombre"])
df = df.replace({np.nan: None})  # Convierte los 'NaN' en 'NULL' para evitar errores en la base de datos

# Guardamos el CSV como copia de seguridad
df.to_csv("16_equipos_laliga_jugadores.csv", sep=";", index=False)
print(" CSV de seguridad guardado correctamente.")

try:
    print(" Conectando a PostgreSQL...")
    conn = psycopg2.connect(
        host="localhost", database="TFG", user="postgres", password="scadelantero4"
    )
    cursor = conn.cursor()

    # 0. INSERTAR CLUBES NUEVOS SI NO EXISTEN
    equipos_unicos = df["club_actual"].unique()
    for equipo in equipos_unicos:
        cursor.execute("INSERT INTO dim_club (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING", (equipo,))
    conn.commit() # Aseguramos que los clubes se guarden antes de seguir

    # 1. STAGING
    print(" Volcando datos en Staging...")
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO jugadores (nombre, posicion, edad, valor_mercado_€, goles, asistencias, minutos, partidos, amarillas, seg_amarillas, rojas, goles_encajados, a_cero, ultima_lesion, numero_lesiones_25_26, dias_recup_ultima_lesion, altura_cm, pie_bueno, fin_contrato, canterano_valencia, ultimo_club, segunda_posicion, agencia, sueldo_anual_€, club_actual)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (nombre)
            DO UPDATE SET
            posicion = EXCLUDED.posicion, edad = EXCLUDED.edad, valor_mercado_€ = EXCLUDED.valor_mercado_€,
            goles = EXCLUDED.goles, asistencias = EXCLUDED.asistencias, minutos = EXCLUDED.minutos,
            partidos = EXCLUDED.partidos, amarillas = EXCLUDED.amarillas, seg_amarillas = EXCLUDED.seg_amarillas,
            rojas = EXCLUDED.rojas, goles_encajados = EXCLUDED.goles_encajados, a_cero = EXCLUDED.a_cero,
            ultima_lesion = EXCLUDED.ultima_lesion, numero_lesiones_25_26 = EXCLUDED.numero_lesiones_25_26,
            dias_recup_ultima_lesion = EXCLUDED.dias_recup_ultima_lesion, altura_cm = EXCLUDED.altura_cm,
            pie_bueno = EXCLUDED.pie_bueno, fin_contrato = EXCLUDED.fin_contrato, canterano_valencia = EXCLUDED.canterano_valencia,
            ultimo_club = EXCLUDED.ultimo_club, segunda_posicion = EXCLUDED.segunda_posicion, agencia = EXCLUDED.agencia,
            sueldo_anual_€ = COALESCE(NULLIF(EXCLUDED.sueldo_anual_€, 0), jugadores.sueldo_anual_€),
            club_actual = EXCLUDED.club_actual
        """, (row["nombre"], row["posicion"], row["edad"], row["valor_mercado_€"], row["goles"], row["asistencias"], row["minutos"], row["partidos"], row["amarillas"], row["seg_amarillas"], row["rojas"], row["goles_encajados"], row["a_cero"],row["ultima_lesion"], row["numero_lesiones_25_26"], row["dias_recup_ultima_lesion"], row["altura_cm"], row["pie_bueno"], row["fin_contrato"], row["canterano_valencia"], row["ultimo_club"], row["segunda_posicion"], row["agencia"], row["sueldo_anual_€"], row["club_actual"]))

    # OBTENER IDs
    
    cursor.execute("SELECT id FROM dim_temporada WHERE temporada = '2025-2026'")
    resultado_temp = cursor.fetchone()
    if not resultado_temp:
        raise ValueError("La temporada '2025-2026' no existe en la tabla dim_temporada. Verifica pgAdmin.")
    temporada_id = resultado_temp[0]

    cursor.execute("SELECT nombre, id FROM dim_club")
    mapa_clubes = dict(cursor.fetchall())

    cursor.execute("SELECT nombre, posicion, edad, valor_mercado_€, goles, asistencias, minutos, partidos, amarillas, seg_amarillas, rojas, goles_encajados, a_cero, ultima_lesion, numero_lesiones_25_26, dias_recup_ultima_lesion, altura_cm, pie_bueno, fin_contrato, canterano_valencia, ultimo_club, segunda_posicion, agencia, sueldo_anual_€, club_actual FROM jugadores")
    filas_staging = cursor.fetchall()

    print(" Modelando dimensiones y hechos...")
    for fila in filas_staging:
        nombre, posicion, edad, valor_numerico, goles, asistencias, minutos, partidos, amarillas, seg_amarillas, rojas, goles_encajados, a_cero, ultima_lesion, numero_lesiones_25_26, dias_recup_ultima_lesion, altura_cm, pie_bueno, fin_contrato, canterano_valencia, ultimo_club, segunda_posicion, agencia, sueldo_anual, club_actual = fila
        
        if club_actual not in mapa_clubes:
            raise KeyError(f"El club {club_actual} no se encuentra en dim_club.")
        club_id_dinamico = mapa_clubes[club_actual]

        # 2. DIMENSIÓN JUGADOR
        cursor.execute("""
            INSERT INTO dim_jugador (nombre, posicion, altura_cm, pie_bueno, canterano_valencia, agencia, segunda_posicion)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (nombre)
            DO UPDATE SET 
            posicion = EXCLUDED.posicion, altura_cm = EXCLUDED.altura_cm, pie_bueno = EXCLUDED.pie_bueno,
            canterano_valencia = EXCLUDED.canterano_valencia, agencia = EXCLUDED.agencia, segunda_posicion = EXCLUDED.segunda_posicion
            RETURNING id
        """, (nombre, posicion, altura_cm, pie_bueno, canterano_valencia, agencia, segunda_posicion))
        jugador_id = cursor.fetchone()[0]

        # 3. HECHOS
        cursor.execute("""
            INSERT INTO hechos_jugadores (
                jugador_id, club_id, temporada_id, edad, valor_mercado_€, goles, asistencias, minutos, partidos, amarillas, seg_amarillas, rojas, goles_encajados, a_cero, ultima_lesion, numero_lesiones_25_26, dias_recup_ultima_lesion, fin_contrato, ultimo_club, sueldo_anual_€
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (jugador_id, club_id, temporada_id)
            DO UPDATE SET
            edad = EXCLUDED.edad, valor_mercado_€ = EXCLUDED.valor_mercado_€, goles = EXCLUDED.goles,
            asistencias = EXCLUDED.asistencias, minutos = EXCLUDED.minutos, partidos = EXCLUDED.partidos,
            amarillas = EXCLUDED.amarillas, seg_amarillas = EXCLUDED.seg_amarillas, rojas = EXCLUDED.rojas,
            goles_encajados = EXCLUDED.goles_encajados, a_cero = EXCLUDED.a_cero, ultima_lesion = EXCLUDED.ultima_lesion,
            numero_lesiones_25_26 = EXCLUDED.numero_lesiones_25_26, dias_recup_ultima_lesion = EXCLUDED.dias_recup_ultima_lesion,
            fin_contrato = EXCLUDED.fin_contrato, ultimo_club = EXCLUDED.ultimo_club,
            sueldo_anual_€ = COALESCE(NULLIF(EXCLUDED.sueldo_anual_€, 0), hechos_jugadores.sueldo_anual_€)
        """, (jugador_id, club_id_dinamico, temporada_id, edad, valor_numerico, goles, asistencias, minutos, partidos, amarillas, seg_amarillas, rojas, goles_encajados, a_cero, ultima_lesion, numero_lesiones_25_26, dias_recup_ultima_lesion, fin_contrato, ultimo_club, sueldo_anual))

    conn.commit()
    print(" Base de datos actualizada con los 16 equipos.")

except Exception as e:
    print("\n ¡ERROR CRÍTICO AL GUARDAR EN POSTGRESQL!")
    print(f"Detalle del error: {e}")
    if 'conn' in locals() and conn:
        conn.rollback() # Si hay error, deshacemos a medias para no corromper la BD
finally:
    if 'cursor' in locals() and cursor: cursor.close()
    if 'conn' in locals() and conn: conn.close()
    print("Cerrando navegador y limpiando procesos...")
    driver.quit() # Esto cierra la ventana de Google Chrome