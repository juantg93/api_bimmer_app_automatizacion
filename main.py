from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from config import id_email, id_password, btn_login, id_vin, btn_check
from coche import Coche
from bot_telegram import enviar_mensaje_sync
from utils.check_carplay import carplay_check
from dataBase.database import registrar_consulta
import logging

logger = logging.getLogger(__name__)

# Segundos máximos para carga de página y localización de elementos
PAGE_LOAD_TIMEOUT = 30
ELEMENT_WAIT_TIMEOUT = 15


def crear_driver():
    """Crea y devuelve un ChromeDriver en modo headless."""
    try:
        logger.info("Creando driver...")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        driver.set_script_timeout(PAGE_LOAD_TIMEOUT)
        driver.get('https://api.bimmer.help/index.php')
        logger.info("Driver creado correctamente")
        return driver
    except Exception as e:
        logger.error(f"Error creando driver: {e}")
        return None


def buscar_rellenar_campos_user_pass(driver, email, password):
    """Rellena los campos de email y contraseña. Retorna True si todo fue bien."""
    identificadores = [(id_email, email), (id_password, password)]
    for campo, valor in identificadores:
        try:
            box = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.ID, campo))
            )
            box.send_keys(valor)
        except TimeoutException:
            logger.error(f"Timeout esperando campo '{campo}'")
            return False
        except Exception as e:
            logger.error(f"Error rellenando campo '{campo}': {e}")
            return False
    return True


def login_click(driver) -> bool:
    """Hace click en el botón de login y verifica que el login fue exitoso.
    Retorna True si el login fue correcto."""
    try:
        logger.info("Haciendo click en botón de login...")
        btn = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
            EC.element_to_be_clickable((By.NAME, btn_login))
        )
        btn.click()

        # Verificar que el login fue exitoso esperando el campo VIN
        WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.NAME, id_vin))
        )
        logger.info("Login verificado correctamente")
        return True
    except TimeoutException:
        logger.error("Login fallido: timeout esperando el campo VIN tras el login")
        return False
    except Exception as e:
        logger.error(f"Error durante el login: {e}")
        return False


def introducir_vin(driver, vin) -> bool:
    """Introduce el VIN en el campo correspondiente. Retorna True si fue bien."""
    try:
        logger.info("Buscando casilla VIN...")
        casilla_vin = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.NAME, id_vin))
        )
        casilla_vin.send_keys(vin)
        logger.info("VIN introducido")
        return True
    except TimeoutException:
        logger.error("Timeout esperando el campo VIN")
        return False
    except Exception as e:
        logger.error(f"Error introduciendo VIN: {e}")
        return False


def click_check_vin(driver) -> bool:
    """Hace click en el botón de consulta y espera los resultados. Retorna True si fue bien."""
    try:
        logger.info("Consultando VIN...")
        btn = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
            EC.element_to_be_clickable((By.ID, btn_check))
        )
        btn.click()
        # Esperar a que aparezca el contenedor de resultados
        WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.mv_ci"))
        )
        logger.info("Resultados cargados")
        return True
    except TimeoutException:
        logger.error("Timeout esperando resultados del VIN")
        return False
    except Exception as e:
        logger.error(f"Error haciendo click en check VIN: {e}")
        return False


def obtener_datos_vehiculo(driver):
    """Extrae los datos del vehículo del DOM y retorna un objeto Coche."""
    logger.info("Obteniendo datos del vehículo...")
    contenedor = driver.find_element(By.CSS_SELECTOR, "div.mv_ci")
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
        elif label == "HEADUNIT:":
            coche.headunit = valor
        elif label == "HEADUNIT SERIAL:":
            coche.headunit_serial = valor

    logger.info("Objeto Coche construido")
    return coche


def consultar_vin(vin, chat_id, email, password):
    """Ejecuta el flujo completo de consulta de VIN."""
    enviar_mensaje_sync(f"✅ VIN recibido: <b>{vin}</b>\nIniciando proceso...", chat_id)

    driver = crear_driver()
    if driver is None:
        return "❌ Error: no se pudo iniciar el navegador."

    try:
        # Rellenar credenciales
        enviar_mensaje_sync("🔑 Rellenando credenciales de acceso...", chat_id)
        if not buscar_rellenar_campos_user_pass(driver, email, password):
            return "❌ Error: no se han podido rellenar los campos de login."

        # Hacer login y verificar
        enviar_mensaje_sync("🔓 Haciendo login...", chat_id)
        if not login_click(driver):
            return "❌ Error: login fallido. Comprueba tus credenciales con /actualizar."

        enviar_mensaje_sync("✅ Login correcto. Introduciendo VIN...", chat_id)

        # Introducir VIN
        if not introducir_vin(driver, vin):
            return "❌ Error: no se pudo introducir el VIN."

        # Consultar
        enviar_mensaje_sync("⏳ Consultando base de datos BMW...", chat_id)
        if not click_check_vin(driver):
            return "❌ Error: no se obtuvieron resultados. El VIN puede no existir o el sitio no respondió."

        # Obtener datos
        try:
            coche = obtener_datos_vehiculo(driver)
        except Exception as e:
            logger.error(f"Error obteniendo datos del coche: {e}")
            return "❌ Error obteniendo los datos del vehículo."

        mensaje = str(coche)

        if coche.headunit and carplay_check(coche.headunit):
            mensaje += "\n📱<b>CarPlay:</b> Si"

        registrar_consulta(chat_id, vin, exitosa=True)
        return mensaje

    finally:
        driver.quit()
