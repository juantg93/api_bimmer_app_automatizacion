import re
import os
import time
from flask import Flask, request, jsonify
from main import consultar_vin
from bot_telegram import enviar_mensaje_sync
from dataBase.database import (
    crear_usuario_inicial,
    obtener_estado_usuario,
    actualizar_email,
    actualizar_password,
    obtener_usuario,
    resetear_usuario,
)
from dataBase.crypto import cifrar_password, descifrar_password
from messages.strings import (
    welcome_message,
    email_message,
    password_message,
    finish_message,
)
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Token secreto para validar que los webhooks vienen realmente de Telegram.
# Debe coincidir con el secret_token usado al registrar el webhook.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET_TOKEN", "")

# Rate limiting: máximo de consultas VIN por usuario en una ventana de tiempo
RATE_LIMIT_MAX = 3          # máximo de consultas permitidas
RATE_LIMIT_WINDOW = 60      # ventana de segundos
_rate_limit_store: dict[int, list[float]] = {}

# Patrón VIN: 7 o 17 caracteres alfanuméricos (sin I, O, Q según estándar ISO 3779)
VIN_PATTERN = re.compile(r'^[A-HJ-NPR-Z0-9]{7}$|^[A-HJ-NPR-Z0-9]{17}$')
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


# --------------------- FUNCIONES AUXILIARES -----------------------------

def _verificar_webhook_token():
    """Retorna True si el header de secreto de Telegram es correcto."""
    if not WEBHOOK_SECRET:
        return True  # Sin secreto configurado, se omite la comprobación
    return request.headers.get("X-Telegram-Bot-Api-Secret-Token") == WEBHOOK_SECRET


def comprobar_vin(vin: str) -> bool:
    return bool(VIN_PATTERN.match(vin))


def comprobar_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(email))


def _rate_limit_ok(chat_id: int) -> bool:
    """Devuelve False si el usuario ha superado el límite de consultas."""
    ahora = time.time()
    ventana = _rate_limit_store.get(chat_id, [])
    ventana = [t for t in ventana if ahora - t < RATE_LIMIT_WINDOW]
    if len(ventana) >= RATE_LIMIT_MAX:
        _rate_limit_store[chat_id] = ventana
        return False
    ventana.append(ahora)
    _rate_limit_store[chat_id] = ventana
    return True


# ------------------------- HANDLERS POR ESTADO -----------------------------

def handler_start(chat_id):
    estado = obtener_estado_usuario(chat_id)

    if estado is None:
        crear_usuario_inicial(chat_id)
        enviar_mensaje_sync(welcome_message, chat_id)
        enviar_mensaje_sync(email_message, chat_id)
    elif estado == "registrado":
        enviar_mensaje_sync("✅ Ya estás registrado. Puedes enviarme VINs directamente.", chat_id)
    elif estado == 'esperando_email':
        enviar_mensaje_sync(email_message, chat_id)
    elif estado == 'esperando_password':
        enviar_mensaje_sync(password_message, chat_id)


def handler_esperando_email(chat_id, texto):
    if not comprobar_email(texto):
        enviar_mensaje_sync("⚠️ El email no parece válido. Inténtalo de nuevo:", chat_id)
        return
    actualizar_email(chat_id, texto)
    enviar_mensaje_sync(password_message, chat_id)


def handler_esperando_password(chat_id, texto):
    password_cifrada = cifrar_password(texto)
    actualizar_password(chat_id, password_cifrada)
    enviar_mensaje_sync(finish_message, chat_id)


def handler_registrado(chat_id, texto):
    vin = texto.upper()

    if not comprobar_vin(vin):
        enviar_mensaje_sync(
            f"⚠️ VIN no válido: '{vin}'. Debe tener 7 o 17 caracteres alfanuméricos (sin I, O ni Q).",
            chat_id
        )
        return

    if not _rate_limit_ok(chat_id):
        enviar_mensaje_sync(
            f"⚠️ Has superado el límite de {RATE_LIMIT_MAX} consultas por minuto. Espera un momento.",
            chat_id
        )
        return

    usuario = obtener_usuario(chat_id)
    if usuario is None:
        enviar_mensaje_sync("❌ Error recuperando tu perfil. Contacta con el administrador.", chat_id)
        return

    email = usuario['email']
    password = descifrar_password(usuario['password'])

    mensaje = consultar_vin(vin, chat_id, email, password)
    enviar_mensaje_sync(mensaje, chat_id)


def handler_actualizar(chat_id):
    """Permite al usuario registrado actualizar sus credenciales."""
    estado = obtener_estado_usuario(chat_id)
    if estado is None:
        enviar_mensaje_sync("⚠️ Escribe /start primero para registrarte.", chat_id)
        return
    resetear_usuario(chat_id)
    enviar_mensaje_sync(
        "🔄 Tus credenciales han sido eliminadas. Introduce tu nuevo email:",
        chat_id
    )


# ---------------------------- WEBHOOK PRINCIPAL -------------------------

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("Solicitud en webhook")

    if not _verificar_webhook_token():
        logger.warning("Webhook rechazado: token secreto inválido")
        return jsonify({"ok": False}), 403

    try:
        data = request.get_json()

        if not data or 'message' not in data or 'text' not in data['message']:
            return jsonify({"ok": True}), 200

        chat_id = data['message']['chat']['id']
        texto = data['message']['text'].strip()

        estado_actual = obtener_estado_usuario(chat_id)
        # No loggear el texto cuando el usuario está enviando su contraseña
        if estado_actual == 'esperando_password':
            logger.info(f'Mensaje recibido - chat_id: {chat_id}, texto: [REDACTED]')
        else:
            logger.info(f'Mensaje recibido - chat_id: {chat_id}, texto: {texto}')

        if texto == '/start':
            handler_start(chat_id)
        elif texto == '/actualizar':
            handler_actualizar(chat_id)
        else:
            if estado_actual is None:
                enviar_mensaje_sync("⚠️ Escribe /start primero para registrarte.", chat_id)
            elif estado_actual == "esperando_email":
                handler_esperando_email(chat_id, texto)
            elif estado_actual == "esperando_password":
                handler_esperando_password(chat_id, texto)
            elif estado_actual == "registrado":
                handler_registrado(chat_id, texto)

        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.error(f"Error de excepcion en webhook: {e}")
        return jsonify({"ok": False}), 400


if __name__ == "__main__":
    app.run(port=5001)
