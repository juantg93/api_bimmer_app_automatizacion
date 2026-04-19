import logging
from dataBase.database import obtener_conexion
from bot_telegram import enviar_mensaje_sync

logger = logging.getLogger(__name__)

def enviar_broadcast(mensaje):
    """Envía un mensaje a todos los usuarios registrados."""
    logger.info("Iniciando Broadcast")
    conexion = obtener_conexion()
    if conexion is None:
        logger.error("Broadcast abortado: sin conexión a la base de datos")
        return

    cursor = None
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT chat_id FROM usuarios WHERE estado = 'registrado' AND activo = TRUE")
        chat_ids = cursor.fetchall()
        logger.info(f"Usuarios a notificar: {len(chat_ids)}")
    finally:
        if cursor:
            cursor.close()
        conexion.close()

    for (chat_id,) in chat_ids:
        try:
            enviar_mensaje_sync(mensaje, chat_id)
        except Exception as e:
            logger.error(f"Error enviando broadcast a {chat_id}: {e}")


if __name__ == "__main__":
    enviar_broadcast("Texto de prueba")
