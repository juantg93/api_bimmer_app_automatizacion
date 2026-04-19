from flask import Flask, request, jsonify
from main import consultar_vin
from bot_telegram import enviar_mensaje_sync
from dataBase.database import (
    crear_usuario_inicial,
    obtener_estado_usuario,
    actualizar_email,
    actualizar_password,
    obtener_usuario
)
from dataBase.crypto import cifrar_password, descifrar_password
from messages.strings import (
    welcome_message,
    email_message,
    password_message,
    finish_message,
    error_message
)
import logging
# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Creación App Flask
app = Flask(__name__)

# --------------------- FUNCIONES AUXILIARES -----------------------------

# Función para comprobar longitud del vin introducido
def comprobar_longitud_vin(vin):
    """Esta función comprueba la longitud del vin introducido. Si no es valido retorna mensaje de error en telegram."""
    longitudes_validas = [7, 17]
    if len(vin) not in longitudes_validas:
        return False
    else:
        return True

# ------------------------- HANDLERS POR ESTADO -----------------------------
def handler_start(chat_id):
    "Gestiona el comando /start segun si el usuario existe o no."
    estado = obtener_estado_usuario(chat_id)

    if estado is None:
        # Usuario Nuevo -> Crearlo y pedir email
        crear_usuario_inicial(chat_id)
        enviar_mensaje_sync(welcome_message, chat_id)
        enviar_mensaje_sync(email_message, chat_id)
    
    elif estado == "registrado":
        # Usuario ya registrado
        enviar_mensaje_sync("✅ Ya estás registrado. Puedes enviarme VINs directamente.", chat_id)
    
    elif estado == 'esperando_email':
        enviar_mensaje_sync(email_message, chat_id)
    
    elif estado == 'esperando_password':
        enviar_mensaje_sync(password_message, chat_id)


def handler_esperando_email(chat_id, texto):
    "El usuario debería estar enviando su email"
    # Validación basica del email
    if "@" not in texto or "." not in texto:
        enviar_mensaje_sync("⚠️ El email no parece válido. Inténtalo de nuevo:", chat_id)
        return
    
    actualizar_email(chat_id, texto)
    enviar_mensaje_sync(password_message, chat_id)

def handler_esperando_password(chat_id, texto):
    """El usuario deberia estar enviando su contraseña"""
    password_cifrada = cifrar_password(texto)
    actualizar_password(chat_id, password_cifrada)
    enviar_mensaje_sync(finish_message, chat_id)

def handler_registrado(chat_id, texto):
    """El usuario registrado envia un vin"""
    vin = texto.upper()

    if not comprobar_longitud_vin(vin):
        enviar_mensaje_sync(f"⚠️ VIN no válido. Longitud: {len(vin)} caracteres. Debe ser 7 o 17.",
            chat_id
        )
        return
    
    usuario = obtener_usuario(chat_id)
    email = usuario['email']
    password = descifrar_password(usuario['password'])
    
    mensaje = consultar_vin(vin, chat_id, email, password)
    enviar_mensaje_sync(mensaje, chat_id)



# ---------------------------- WEBHOOK PRINCIPAL -------------------------

# Endpoint que recibe mensaje
@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("Solicitud en webhook")
    try:
        logger.info("Recuperando data...")
        data = request.get_json()
        logger.info("Data recuperado")

        if 'message' not in data or 'text' not in data['message']:
            logger.info("No se ha encontrado message o text en: data")
            return jsonify({"ok": True}), 200

        logger.info("Inicio de guardado de chatid y texto en variables")
        chat_id = data['message']['chat']['id']
        texto = data['message']['text'].strip()
        logger.info("Variables guardadas.")

        logger.info(f'Mensaje recibido - chat_id: {chat_id}, texto: {texto}')

        # Enrutamiento segun el contenido  el estado del usuario
        if texto == '/start':
            handler_start(chat_id)
        else:
            estado = obtener_estado_usuario(chat_id)
            
            if estado is None:
                enviar_mensaje_sync("⚠️ Escribe /start primero para registrarte.", chat_id)
            elif estado == "esperando_email":
                handler_esperando_email(chat_id, texto)
            elif estado == "esperando_password":
                handler_esperando_password(chat_id, texto)
            elif estado == "registrado":
                handler_registrado(chat_id, texto)
        
        return jsonify({"ok": True}), 200


    
    except Exception as e:
        logger.error(f"Error de excepcion en webhook: {e}")
        return jsonify({"ok":False}), 400
    

if __name__ == "__main__":
    app.run(port=5001)