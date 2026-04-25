from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By

import logging

logger = logging.getLogger(__name__)

def extraer_fecha_km(contenedor, coche):
    """Extrae el timestamp de la última lectura de KM (atributo title del span)."""
    try:
        # Localizar el div.ci_l cuyo .pn dice "LAST KNOWN KM:" y dentro coger el span
        span = contenedor.find_element(
            By.XPATH,
            ".//div[@class='ci_l'][div[@class='pn' and normalize-space(text())='LAST KNOWN KM:']]//div[@class='pi']/span"
        )
        coche.fecha_km = span.get_attribute("title")
        logger.info(f"Fecha de KM extraída: {coche.fecha_km}")
    except NoSuchElementException:
        logger.info("Fecha de últimos KM no disponible")

def extraer_color_texto(contenedor, coche):
    """Extrae el nombre del color exterior en texto natural (segundo span del campo COLOR)."""
    try:
        spans = contenedor.find_elements(
            By.XPATH,
            ".//div[@class='ci_l'][div[@class='pn' and normalize-space(text())='UPHOLSTERY, COLOR:']]//div[@class='pi']/span"
        )
        if len(spans) >= 2:
            coche.color_texto = spans[1].get_attribute("title")
            logger.info(f"Color extraído: {coche.color_texto}")
        else:
            logger.info("Color exterior no disponible (solo hay un span)")
    except NoSuchElementException:
        logger.info("Campo UPHOLSTERY, COLOR no encontrado")

def extraer_archivos_software(contenedor, coche):
    """Extrae los archivos software de la ECU motor (BTLD, CAFD, HWAP, HWEL, SWFL).
    
    Vienen como atributo title del span del campo ENGINE, separados por <br>.
    """
    try:
        span = contenedor.find_element(
            By.XPATH,
            ".//div[@class='ci_l'][div[@class='pn' and normalize-space(text())='ENGINE:']]//div[@class='pi']/span"
        )
        title_raw = span.get_attribute("title")
        
        if not title_raw:
            logger.info("Archivos software: span sin title")
            return
        
        # Dividir por <br>, limpiar espacios, descartar vacíos
        archivos = [linea.strip() for linea in title_raw.split("<br>") if linea.strip()]
        
        if archivos:
            coche.archivos_software = archivos
            logger.info(f"Archivos software extraídos: {len(archivos)} entradas")
        else:
            logger.info("Archivos software: title vacío tras parsear")
            
    except NoSuchElementException:
        logger.info("Campo ENGINE no encontrado o sin span con archivos software")

def extraer_mapa_navegacion(driver, vin_solicitado, coche):
    """Extrae el mapa de navegación del título del DVI (div.vit, fuera de mv_ci).
    
    El título tiene formato: 'BMW <modelo> <variante> [<región>] [<mapa>]'.
    El mapa va entre los últimos corchetes. Puede ser 'No map detected' si no hay.
    """
    try:
        # Buscar el div.vit del DVI correcto: está dentro del mismo div.mv que contiene
        # un div.vii (cabecera con VIN completo) cuyo texto contiene el VIN solicitado.
        vit = driver.find_element(
            By.XPATH,
            f"//div[contains(@class, 'mv')][.//div[@class='vii' and contains(text(), '{vin_solicitado}')]]//div[@class='vit']"
        )
        texto = vit.text  # ej: "BMW G01 X3 xDrive20d [ECE] [Road Map EUROPE EVO]"
        
        # Extraer el último corchete
        if texto.count("[") >= 2 and texto.endswith("]"):
            ultimo_corchete = texto.rsplit("[", 1)[1].rstrip("]").strip()
            
            if ultimo_corchete.lower() == "no map detected":
                coche.mapa = "Sin mapa de navegación"
            else:
                coche.mapa = ultimo_corchete
            
            logger.info(f"Mapa extraído: {coche.mapa}")
        else:
            logger.info("Formato de título inesperado, no se pudo extraer el mapa")
            
    except NoSuchElementException:
        logger.info("Título del DVI (div.vit) no encontrado")