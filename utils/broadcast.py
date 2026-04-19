import logging
from dataBase.database import obtener_conexion
from bot_telegram import enviar_mensaje_sync

# Inicio de logger
logger = logging.getLogger(__name__)

# Función recuperadora de chat id para envio de broadcast.
def enviar_broadcast(mensaje):
    """Envía un mensaje a todos los usuarios registrados."""
    logger.info("Iniciando Broadcast")
    logger.info("Iniciando conexion con BD....")
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    logger.info("Conexión con BD OK")
    
    logger.info("Ejecutando query...")
    cursor.execute("SELECT chat_id FROM usuarios WHERE estado = 'registrado' AND activo = TRUE")
    logger.info("Query ejecutada.")
    chat_ids = cursor.fetchall()
    logger.info(f"Chat id recuperados: {chat_ids}")
    
    cursor.close()
    conexion.close()
    
    for (chat_id,) in chat_ids:
        try:
            enviar_mensaje_sync(mensaje, chat_id)
        except Exception as e:
            logger.error(f"Error enviando broadcast a {chat_id}: {e}")


enviar_broadcast("Texto de prueba: 2")