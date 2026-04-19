from telegram import Bot
from config import TOKEN_TELEGRAM
import requests
import logging



# Configuración de logging
logger = logging.getLogger(__name__)


def crear_bot():
    try:
        bot = Bot(TOKEN_TELEGRAM)
        return bot

    except Exception as e:
        logger.error("Error creando bot")
        logger.error(f"Error: {e}")
        


def enviar_mensaje_sync(mensaje, chat_id):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    try:
        logger.info("Iniciando envio de notificación por telegram...")
        requests.post(url, json={"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"})
    except Exception as e:
        logger.error(f"Error enviando notificación por Telegram al chat id: {chat_id} ")
        


