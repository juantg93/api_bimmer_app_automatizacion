"""Gestión del cifrado de contraseñas con Fernet"""
import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# Cargamos la clave maestra una sola vez al importar el módulo
FERNET_KEY = os.getenv("FERNET_KEY")

if FERNET_KEY is None:
    raise ValueError("FERNET_KEY no está definida en el archivo .env")

fernet = Fernet(FERNET_KEY.encode())


def cifrar_password(password: str) -> bytes:
    """Cifra una contraseña en texto plano y devuelve los bytes cifrados."""
    return fernet.encrypt(password.encode())


def descifrar_password(password_cifrada: bytes) -> str:
    """Descifra una contraseña y devuelve el texto plano original."""
    return fernet.decrypt(password_cifrada).decode()