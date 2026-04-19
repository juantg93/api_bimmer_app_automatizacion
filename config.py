import os
from dotenv import load_dotenv

# Cargar las variables del archivo .env
load_dotenv()

"""Constantes de configuración"""

# Pagina web de inicio donde se introducirá login
WEBSITE_LOGIN = "https://api.bimmer.help/index.php"

# Variables extraidas de WebSite Login
id_email = "user_email"
id_password = "user_password"
btn_login = "commit"

# Variables después de hacer login
id_vin = "vin" #name
btn_check = "commit" #id


# INFORMACIÓN BOT TELEGRAM (desde .env)
TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")

if TELEGRAM_SECRET_TOKEN is None:
    raise ValueError("TELEGRAM_SECRET_TOKEN no está definido en el archivo .env")