from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from config import id_email, id_password, btn_login, id_vin, btn_check
from coche import Coche
from bot_telegram import enviar_mensaje_sync
from utils.check_carplay import carplay_check
from dataBase.database import registrar_consulta
import logging


# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def crear_driver():
    """Creación del driver"""
    try:
        print("Creando driver...")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver_chrome = webdriver.Chrome(options=options)

        # Timeouts globales del navegador
        driver_chrome.set_page_load_timeout(30)
        driver_chrome.set_script_timeout(30)

        driver_chrome.get('https://api.bimmer.help/index.php')
        print("Driver creado")
        return driver_chrome
    except Exception as e:
        print("Error creando Driver: ", e)
        return None

def buscar_rellenar_campos_user_pass(driver, email, password):
    identificadores = [(id_email, email), (id_password, password)]
    campos_rellenados = True

    for campo, valor in identificadores:
        try:
            box = driver.find_element(By.ID, campo)
            box.send_keys(valor)
            #time.sleep(2)
        except Exception as e:
            logger.error(f"Error buscando identificadores: {e}")
            campos_rellenados = False

    return campos_rellenados

def login_click(driver):
    try:
        logger.info("Iniciando login..")
        btn = driver.find_element(By.NAME, btn_login)
        btn.click()

        # Espera hasta que aparezca el campo vin, esto indicará que el login fue exitoso.
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, id_vin))
        )
        logger.info("Login OK")
        return True
    except TimeoutException:
        logger.error("Login fallido: el campo VIN no aparecio tras 15s. Credenciales incorrectas o sitio caido.")
        return False
    except Exception as e:
        logger.error(f"Error haciendo login: {e}")
        return False

def introducir_vin(driver, vin):
    try:
        print("Buscando casilla vin...")
        casilla_vin = driver.find_element(By.NAME, id_vin)
        casilla_vin.send_keys(vin)
        print("VIN escrito")
        return True
    except Exception as e:
        print("Error introduciendo VIN: ", e)
        return False

def click_check_vin(driver):
    try:
        print("Consultando VIN...")
        btn = driver.find_element(By.ID, btn_check)
        btn.click()

        logger.info("Esperando resultados...")
        # Esperando a que aparezca el contenedor con los datos del vehiculo para continuar
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.mv_ci"))
        )
        logger.info("Resultados cargados.")
        return True
    except TimeoutException:
        logger.error("Timeout esperando resultados de la consulta VIN (20s)")
        return False
    except Exception as e:
        logger.error(f"Error haciendo click en check VIN:{e}")
        return False

def obtener_datos_vehiculo(driver):
    print("Obteniendo datos del vehículo...")
    contenedor = driver.find_element(By.CSS_SELECTOR, "div.mv_ci")
    print("Texto contenedor: ", contenedor.text[:200])
    campos = contenedor.find_elements(By.CSS_SELECTOR, "div.ci_l")

    coche = Coche()
    for campo in campos:
        label = campo.find_element(By.CSS_SELECTOR, "div.pn").text.strip()
        valor = campo.find_element(By.CSS_SELECTOR, "div.pi").text.strip()

        if label == "VIN:":
            coche.vin = valor
        elif label == "PRODUCTION DATE:":
            coche.production_date = valor
        elif label == "DELIVERY DATE:":
            coche.delivery_date = valor
        elif label == "LAST KNOWN KM:":
            coche.last_know_km = valor
        elif label == "ENGINE NR:":
            coche.engine_nr = valor
        elif label == "TRANSMISSION NR:":
            coche.transmision_nr = valor
        elif label == "PRODUCTION iLEVEL:":
            coche.production_ilevel = valor
        elif label == "LAST KNOWN iLEVEL:":
            coche.last_know_ilevel = valor
        elif label == "ENGINE:":
            coche.engine = valor
        elif label == "DRIVE, STEERING:":
            coche.drive_steering = valor
        elif label == "BODY, DOORS:":
            coche.body_doors = valor
        elif label == "UPHOLSTERY, COLOR:":
            coche.upholstery_color = valor
        elif label == "KEY SYSTEM:":
            coche.key_system = valor
        elif label == "LEARNED KEYS:":
            pass
        elif label == "HEADUNIT:":
            coche.headunit = valor
        elif label == "HEADUNIT SERIAL:":
            coche.headunit_serial = valor

    print("Coche construido.")
    return coche


def consultar_vin(vin, chat_id, email, password):
    """Ejecuta el flujo completo de consulta de VIN."""
    mensaje = "❌ Error desconocido procesando el VIN." 
    # 1. Confirmación de recepción
    enviar_mensaje_sync(f"✅ VIN recibido: <b>{vin}</b>\nIniciando proceso...",chat_id)

    # 2. Crear driver
    driver = crear_driver()

    if driver is None:
        logger.error("No se pudo crear ChromeDriver: None")
        return "❌ Error: no se pudo iniciar el navegador."

    try:
        # 3. Rellenar credenciales
        enviar_mensaje_sync("🔑 Rellenando credenciales de acceso...",chat_id)
        cubrir_campos = buscar_rellenar_campos_user_pass(driver, email, password)

        if not cubrir_campos:
            return "❌ Error: no se han podido rellenar los campos de login."

        # 4. Hacer login
        enviar_mensaje_sync("🔓 Haciendo login...", chat_id)
        if not login_click(driver):
                return "❌ Error al iniciar sesión. Verifica que tus credenciales de api.bimmer.help sean correctas."

        enviar_mensaje_sync("✅ Login correcto. Introduciendo VIN...", chat_id)

        # 5. Introducir VIN y consultar
        if introducir_vin(driver, vin):
            enviar_mensaje_sync("⏳ Consultando base de datos BMW...", chat_id)
            if not click_check_vin(driver):
                return "❌ Error al consultar el VIN en la base de datos."

        # 6. Obtener datos del vehículo
        try:
            logger.info("Obteniendo datos del vehículo...")
            coche = obtener_datos_vehiculo(driver)
            logger.info("Datos vehiculo OK")
        except Exception as e:
            logger.error(f"Error obteniendo datos del coche: {e}")
            return "❌ Error obteniendo los datos del vehículo."

        

        # 7. Construir mensaje con la informacion del coche
        mensaje = str(coche)

        # 8. Verificacion carplay
        if carplay_check(coche.headunit):
            mensaje += f"\n📱<b>CarPlay:</b> Si"

        

        # 8. Registro de consulta en la Base de Datos
        registrar_consulta(chat_id,vin,exitosa=True)
    
    finally:
    # 8. Cerrar Driver para que no ocupe recursos
        driver.quit()

    # 9. Retornamos mensaje
    return mensaje
