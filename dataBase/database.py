"""Gestion de conexion con la base de datos MySQL"""
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


def obtener_conexion():
    """Crea y devuelve una conexion a la base de datos MySQL"""
    try:
        conexion = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        return conexion
    except Error as e:
        logger.error(f"Error conectando con MySQL: {e}")
        return None


# ----- FUNCIONES PARA LA CREACION DE UN USUARIO - 3 PASOS -------

def crear_usuario_inicial(chat_id):
    """Crea un usuario nuevo en estado 'esperando_email' cuando hace /start por primera vez."""
    conexion = obtener_conexion()
    if conexion is None:
        return False

    cursor = None
    try:
        cursor = conexion.cursor()
        query = """
            INSERT INTO usuarios (chat_id, estado)
            VALUES (%s, 'esperando_email')
        """
        cursor.execute(query, (chat_id,))
        conexion.commit()
        logger.info(f"Usuario {chat_id} creado, esperando email")
        return True
    except Error as e:
        logger.error(f"Error creando usuario inicial {chat_id}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        conexion.close()


def actualizar_email(chat_id, email):
    """Guarda el email del usuario y cambia el estado a 'esperando_password'."""
    conexion = obtener_conexion()
    if conexion is None:
        return False

    cursor = None
    try:
        cursor = conexion.cursor()
        query = """
            UPDATE usuarios
            SET email = %s, estado = 'esperando_password'
            WHERE chat_id = %s
        """
        cursor.execute(query, (email, chat_id))
        conexion.commit()
        return True
    except Error as e:
        logger.error(f"Error actualizando email de {chat_id}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        conexion.close()


def actualizar_password(chat_id, password_cifrada):
    """Guarda la contraseña cifrada y marca al usuario como 'registrado'."""
    conexion = obtener_conexion()
    if conexion is None:
        return False

    cursor = None
    try:
        cursor = conexion.cursor()
        query = """
            UPDATE usuarios
            SET password = %s, estado = 'registrado'
            WHERE chat_id = %s
        """
        cursor.execute(query, (password_cifrada, chat_id))
        conexion.commit()
        logger.info(f"Usuario {chat_id} registrado completamente")
        return True
    except Error as e:
        logger.error(f"Error actualizando password de {chat_id}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        conexion.close()


def resetear_usuario(chat_id):
    """Borra las credenciales del usuario y lo pone en estado 'esperando_email'."""
    conexion = obtener_conexion()
    if conexion is None:
        return False

    cursor = None
    try:
        cursor = conexion.cursor()
        query = """
            UPDATE usuarios
            SET email = NULL, password = NULL, estado = 'esperando_email'
            WHERE chat_id = %s
        """
        cursor.execute(query, (chat_id,))
        conexion.commit()
        logger.info(f"Credenciales de {chat_id} reseteadas")
        return True
    except Error as e:
        logger.error(f"Error reseteando usuario {chat_id}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        conexion.close()


def registrar_consulta(chat_id, vin, exitosa=True):
    """Registra una consulta de VIN en el historial."""
    conexion = obtener_conexion()
    if conexion is None:
        logger.error("Error creando conexion: None")
        return False

    cursor = None
    try:
        cursor = conexion.cursor()
        query = """
            INSERT INTO consultas_vin (chat_id, vin, exitosa)
            VALUES (%s, %s, %s)
        """
        cursor.execute(query, (chat_id, vin, exitosa))
        conexion.commit()
        logger.info(f"Registro exitoso para vin: {vin}, chat_id: {chat_id}")
        return True
    except Error as e:
        logger.error(f"Error registrando consulta: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        conexion.close()


def obtener_usuario(chat_id):
    """Obtiene los datos de un usuario por su chat_id."""
    conexion = obtener_conexion()
    if conexion is None:
        return None

    cursor = None
    try:
        cursor = conexion.cursor(dictionary=True)
        query = "SELECT * FROM usuarios WHERE chat_id = %s AND activo = TRUE"
        cursor.execute(query, (chat_id,))
        usuario = cursor.fetchone()
        return usuario
    except Error as e:
        logger.error(f"Error obteniendo usuario {chat_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        conexion.close()


def obtener_estado_usuario(chat_id):
    """Obtiene el estado de un usuario."""
    conexion = obtener_conexion()
    if conexion is None:
        return None

    cursor = None
    try:
        cursor = conexion.cursor()
        query = "SELECT estado FROM usuarios WHERE chat_id = %s AND activo = TRUE"
        cursor.execute(query, (chat_id,))
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None
    except Error as e:
        logger.error(f"Error obteniendo estado de {chat_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        conexion.close()
