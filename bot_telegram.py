import requests
from config import TOKEN_TELEGRAM
import logging

logger = logging.getLogger(__name__)


def enviar_mensaje_sync(mensaje, chat_id):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    try:
        logger.info(f"Enviando mensaje a chat_id: {chat_id}")
        requests.post(
            url,
            json={"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"Error enviando mensaje a chat_id {chat_id}: {e}")
