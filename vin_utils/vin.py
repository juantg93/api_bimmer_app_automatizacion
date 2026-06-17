"""
Versión para SERVIDOR LINUX (Ubuntu Server, sin entorno gráfico) de la consulta
de campañas técnicas (llamadas a revisión) de vehículos BMW a partir del VIN.

Es un script AUTOCONTENIDO: copia solo este archivo al servidor y ejecútalo.

Por qué una pantalla virtual y no headless
-------------------------------------------
La web está protegida por hCaptcha. En modo *headless* hCaptcha asigna baja
confianza al token y BMW rechaza la consulta ("No es posible procesar su
solicitud"). Y Selenium/undetected-chromedriver son detectados por su conexión
DevTools. La solución que funciona:
  - `nodriver` controla Chrome sin la huella DevTools de Selenium.
  - El navegador se ejecuta EN MODO VENTANA (headless=False), pero dentro de una
    PANTALLA VIRTUAL (Xvfb). Como el servidor no tiene monitor, no se ve nada,
    pero para Chrome y para hCaptcha es una sesión "real" con ventana → el token
    se acepta.

================================================================================
INSTALACIÓN EN EL SERVIDOR (Ubuntu Server) — una sola vez
================================================================================

# 1) Chrome/Chromium y Xvfb + utilidades de pantalla virtual
sudo apt update
sudo apt install -y xvfb chromium-browser
#   (si 'chromium-browser' no existe en tu versión, instala Google Chrome:)
#   wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
#   sudo apt install -y ./google-chrome-stable_current_amd64.deb

# 2) Python y dependencias (idealmente en un venv)
sudo apt install -y python3-venv
python3 -m venv ~/bmw-venv
source ~/bmw-venv/bin/activate
pip install nodriver==0.46.1 pyvirtualdisplay

# 3) Ejecutar
python3 bmw_recall_server.py WBA1H31040V313422
python3 bmw_recall_server.py            # pregunta el VIN

Notas:
  - nodriver 0.50.x rompe el import en Python 3.14 (byte no UTF-8); usa 0.46.1.
  - Si Chrome no se encuentra solo, exporta la ruta del binario antes de ejecutar:
        export BMW_CHROME=/usr/bin/chromium-browser
    (o /usr/bin/google-chrome). El script la usará automáticamente.
  - Traza detallada de cada intento:  BMW_DEBUG=1 python3 bmw_recall_server.py VIN

Alternativa sin pyvirtualdisplay: puedes lanzar con xvfb-run en su lugar:
        xvfb-run -a python3 bmw_recall_server.py WBA1H31040V313422
  (en ese caso el script detecta que ya hay DISPLAY y no abre otro Xvfb).
"""

from __future__ import annotations

import os
import random
import re
import sys
import time
from dataclasses import dataclass, asdict

import nodriver as uc

_DEBUG = bool(os.environ.get("BMW_DEBUG"))


def _dbg(*args) -> None:
    if _DEBUG:
        print("[bmw]", *args, file=sys.stderr, flush=True)


URL = ("https://vehiclerecall.bmwgroup.com/index.html"
       "?brand=bmw&market=es&language=es")

# Formato de VIN: 17 caracteres alfanuméricos sin las letras I, O, Q.
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")

# Texto que muestra la web cuando rechaza el token (lo trata como bot).
BLOCK_MARKER = "no es posible procesar"
# Texto cuando el VIN enviado no es válido / no se introdujo.
NOVIN_MARKER = "número vin válido"
# Marcadores de que la consulta se ha resuelto (haya campaña o no).
RESULT_MARKERS = (
    "detalles del veh",
    "código de llamada a revisión",
    "codigo de llamada a revision",
    "no tiene pendiente",
    "no se ha encontrado",
)

# JS para leer el token que hCaptcha deja en el textarea de respuesta.
_TOKEN_JS = ("(function(){var t=document.querySelector("
             "'textarea[name=\"h-captcha-response\"]');return t?t.value:'';})()")


class BMWRecallError(Exception):
    """Error genérico de la consulta."""


class InvalidVinError(BMWRecallError):
    """El VIN no tiene un formato válido."""


class CaptchaError(BMWRecallError):
    """No se pudo superar el hCaptcha (pidió reto de imágenes o fue rechazado)."""


@dataclass
class RecallResult:
    vin: str
    marca: str | None
    modelo: str | None
    tiene_campana: bool
    codigos_campana: list[str]
    texto_completo: str

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_vin(vin: str) -> str:
    vin = (vin or "").strip().upper().replace(" ", "")
    if not VIN_RE.match(vin):
        raise InvalidVinError(
            f"VIN inválido: {vin!r}. Debe tener 17 caracteres alfanuméricos "
            "(sin las letras I, O, Q)."
        )
    return vin


# --------------------------------------------------------------------------- #
# Pantalla virtual (Xvfb) — solo en Linux sin DISPLAY
# --------------------------------------------------------------------------- #
def _start_virtual_display():
    """Arranca un Xvfb si estamos en Linux y no hay un DISPLAY ya disponible.

    Devuelve el objeto Display (para .stop()) o None si no hace falta / no se
    pudo. Si ya hay DISPLAY (p.ej. lanzado con xvfb-run o escritorio), no hace
    nada.
    """
    if not sys.platform.startswith("linux"):
        return None
    if os.environ.get("DISPLAY"):
        _dbg("DISPLAY ya presente:", os.environ["DISPLAY"])
        return None
    try:
        from pyvirtualdisplay import Display
    except ImportError:
        print(
            "AVISO: no hay DISPLAY ni pyvirtualdisplay instalado.\n"
            "       Instálalo:  pip install pyvirtualdisplay   (y apt install xvfb)\n"
            "       o lanza con: xvfb-run -a python3 bmw_recall_server.py VIN",
            file=sys.stderr,
        )
        return None
    disp = Display(visible=False, size=(1280, 900))
    disp.start()
    _dbg("Xvfb iniciado en DISPLAY", os.environ.get("DISPLAY"))
    return disp


def _chrome_path() -> str | None:
    """Ruta del binario de Chrome/Chromium. Respeta BMW_CHROME y, si no, prueba
    ubicaciones habituales en Ubuntu."""
    env = os.environ.get("BMW_CHROME")
    if env and os.path.exists(env):
        return env
    for cand in (
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/snap/bin/chromium",
    ):
        if os.path.exists(cand):
            return cand
    return None


# --------------------------------------------------------------------------- #
# Interacción "humana" con el navegador
# --------------------------------------------------------------------------- #
async def _wiggle(tab, moves: int = 8) -> None:
    """Movimiento de ratón aleatorio: aporta entropía para la puntuación de
    confianza de hCaptcha."""
    for _ in range(moves):
        await tab.mouse_move(random.randint(60, 1100), random.randint(120, 700))
        await tab.sleep(random.uniform(0.05, 0.2))


async def _human_move_to(tab, x: int, y: int) -> None:
    """Aproxima el ratón al punto (x, y) en varios pasos curvos."""
    for sx, sy in [(x - 120, y - 60), (x - 60, y - 25), (x - 25, y - 8), (x, y)]:
        await tab.mouse_move(sx + random.randint(-4, 4), sy + random.randint(-4, 4))
        await tab.sleep(random.uniform(0.08, 0.2))


async def _fill_vin(tab, vin: str) -> None:
    """Escribe el VIN en el campo, carácter a carácter.

    Se usa send_keys (pulsaciones reales) sobre el elemento enfocado con click,
    para que el formulario reactivo de Angular registre el valor como válido y
    habilite el botón. (Fijar el valor por JS NO valida el formulario.)
    """
    field = await tab.select("#vin", timeout=20)
    await field.click()
    await tab.sleep(0.3)
    for ch in vin:
        await field.send_keys(ch)
        await tab.sleep(random.uniform(0.08, 0.22))


async def _try_solve_captcha(tab, attempts: int = 4) -> str | None:
    """Marca la casilla del hCaptcha y devuelve el token, o None si no se logró
    el pase pasivo (p.ej. apareció un reto de imágenes)."""
    await _wiggle(tab)
    for _ in range(attempts):
        frame = await tab.select("iframe[src*='frame=checkbox']", timeout=15)
        pos = await frame.get_position()
        cx = int(pos.left + 30)
        cy = int(pos.top + pos.height / 2)
        await _human_move_to(tab, cx, cy)
        await tab.sleep(random.uniform(0.2, 0.5))
        await tab.mouse_click(cx, cy)
        for _ in range(10):
            await tab.sleep(1)
            token = await tab.evaluate(_TOKEN_JS)
            if token:
                return token
    return None


async def _submit_and_read(tab, timeout: int) -> tuple[str, str]:
    """Pulsa 'Comprobar vehículo' y espera el desenlace.

    El clic a veces no dispara la búsqueda, así que se re-pulsa periódicamente
    (por ratón y por JS) hasta que la página cambia o se agota el tiempo.
    Devuelve (estado, texto_body) donde estado ∈ {ok, block, novin, timeout}.
    """
    await tab.sleep(1.0)  # el botón valida el token antes de habilitarse
    btn = await tab.select("#btnSearch", timeout=15)
    bpos = await btn.get_position()
    bx = int(bpos.left + bpos.width / 2)
    by = int(bpos.top + bpos.height / 2)

    body = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        await tab.mouse_move(bx - 30, by - 10)
        await tab.sleep(0.15)
        await tab.mouse_click(bx, by)
        await tab.evaluate("document.getElementById('btnSearch').click()")
        for _ in range(4):  # espera la respuesta tras pulsar
            await tab.sleep(1)
            body = await tab.evaluate("document.body.innerText") or ""
            low = body.lower()
            if BLOCK_MARKER in low:
                return "block", body
            if NOVIN_MARKER in low:
                return "novin", body
            if any(m in low for m in RESULT_MARKERS):
                return "ok", body
    _dbg("timeout; body:", repr(body[:300]))
    return "timeout", body


# --------------------------------------------------------------------------- #
# Parseo del resultado
# --------------------------------------------------------------------------- #
def _extract(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def _parse(body: str, vin: str) -> RecallResult:
    marca = _extract(r"Marca:\s*([^\n]+)", body)
    modelo = _extract(r"Modelo:\s*([^\n]+)", body)
    codigos = re.findall(r"[Cc]ódigo de llamada a revisi[óo]n\s*([0-9]+)", body)
    codigos = list(dict.fromkeys(codigos))  # únicos, en orden
    low = body.lower()
    tiene = bool(codigos) or "pendiente una llamada a revisión" in low

    # Extrae el bloque de "Detalles del vehículo" como texto legible.
    m = re.search(r"(DETALLES DEL VEH[IÍ]CULO.*?)(?:Nueva b[úu]squeda|$)",
                  body, re.IGNORECASE | re.DOTALL)
    texto = (m.group(1).strip() if m else body.strip())

    return RecallResult(
        vin=vin,
        marca=marca,
        modelo=modelo,
        tiene_campana=tiene,
        codigos_campana=codigos,
        texto_completo=texto,
    )


# --------------------------------------------------------------------------- #
# Función principal
# --------------------------------------------------------------------------- #
async def check_vin_async(vin: str, timeout: int = 40, attempts: int = 3) -> dict:
    """Consulta el VIN en la web de BMW y devuelve los datos como dict.

    Arranca una pantalla virtual (Xvfb) si hace falta y ejecuta Chrome en modo
    ventana dentro de ella. Reintenta la consulta completa hasta `attempts`
    veces. Lanza InvalidVinError, CaptchaError o BMWRecallError.
    """
    vin = normalize_vin(vin)

    kwargs = {"headless": False, "lang": "es-ES"}
    chrome = _chrome_path()
    if chrome:
        kwargs["browser_executable_path"] = chrome
        _dbg("usando Chrome en", chrome)

    browser = await uc.start(**kwargs)
    last_error = "desconocido"
    try:
        for intento in range(attempts):
            _dbg(f"intento {intento}: cargando página")
            tab = await browser.get(URL)
            await tab.sleep(random.uniform(4.5, 6.0))  # dejar cargar la página

            await _fill_vin(tab, vin)
            _dbg("VIN introducido; resolviendo captcha")

            token = await _try_solve_captcha(tab)
            _dbg(f"token len={len(token) if token else 0}")
            if not token:
                last_error = "hCaptcha no concedió el pase pasivo"
                continue

            estado, body = await _submit_and_read(tab, timeout)
            _dbg(f"estado={estado}")
            if estado == "ok":
                return _parse(body, vin).to_dict()
            if estado == "block":
                last_error = ("BMW rechazó el token (sesión marcada como bot)")
                continue
            if estado == "novin":
                raise InvalidVinError(
                    f"La web rechazó el VIN {vin!r} como no válido.")
            last_error = "tiempo de espera agotado esperando el resultado"
        raise CaptchaError(
            f"No se pudo completar la consulta tras {attempts} intentos "
            f"({last_error})."
        )
    finally:
        try:
            browser.stop()
        except Exception:
            pass


def check_vin(vin: str, timeout: int = 40, attempts: int = 3) -> dict:
    """Envoltura síncrona de check_vin_async (para uso desde scripts)."""
    return uc.loop().run_until_complete(
        check_vin_async(vin, timeout=timeout, attempts=attempts)
    )


def _format_for_console(data: dict) -> str:
    lines = [
        "─" * 55,
        f"VIN:    {data['vin']}",
        f"Marca:  {data.get('marca') or '-'}",
        f"Modelo: {data.get('modelo') or '-'}",
    ]
    if data["tiene_campana"]:
        lines.append("Campañas pendientes: SÍ  (código(s): "
                     f"{', '.join(data['codigos_campana']) or '?'})")
    else:
        lines.append("Campañas pendientes: NO")
    lines += ["─" * 55, data["texto_completo"], "─" * 55]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    # Forzamos UTF-8 en la salida para que se vean bien los acentos.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if len(argv) > 1:
        vin = argv[1]
    else:
        vin = input("Introduce el VIN (17 caracteres): ").strip()

    display = _start_virtual_display()
    try:
        data = check_vin(vin)
    except BMWRecallError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if display is not None:
            try:
                display.stop()
            except Exception:
                pass

    print(_format_for_console(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
