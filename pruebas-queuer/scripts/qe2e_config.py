"""Carga de las variables de conexion de las pruebas E2E de rendimiento por el queuer.

Lo usan scripts/e2e_rendimiento_queuer.py (T-039) y scripts/jmeter_e2e_rendimiento_queuer.py (T-040).

Prioridad de cada variable: argumento de la linea de comandos -> variable de entorno
QE2E_<NOMBRE> -> archivo --env-file (mismos nombres que queuer-qa.env) -> se pide por consola.
Los secretos no se aceptan como argumento y se piden sin mostrarlos; nunca se imprimen.
"""

import getpass
import os
import sys
from urllib.parse import urlsplit

PREFIJO_ENTORNO = "QE2E_"
DIRECTORIO_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE_POR_DEFECTO = os.path.join(DIRECTORIO_BASE, "queuer-qa.env")

# (nombre, opcion de linea de comandos o None si es secreto, descripcion)
VARIABLES = (
    ("HOST", "--host", "URL base del queuer, p. ej. https://informacion-ext-qa.apps.ambientesbc.com"),
    ("PREFIX", "--prefix", "prefijo de las rutas del queuer, p. ej. /artemis/platform/queuer/v1"),
    ("COGNITO_URL", "--cognito-url", "URL del token de Cognito (termina en /oauth2/token)"),
    ("CLIENT_ID", "--client-id", "client_id del cliente client_credentials"),
    ("CLIENT_SECRET", None, "client_secret del cliente client_credentials"),
    ("ENDPOINT_GET_MESSAGE_FAKE", "--fakechannel-url",
     "URL base del fakechannel, sin /whatsapp/get-messages"),
)
SECRETOS = tuple(nombre for nombre, opcion, _ in VARIABLES if opcion is None)
URLS = ("HOST", "COGNITO_URL", "ENDPOINT_GET_MESSAGE_FAKE")


class ErrorConfiguracion(Exception):
    pass


def agregar_argumentos(parser):
    """Agrega al parser el --env-file y una opcion por cada variable que no es secreta."""
    grupo = parser.add_argument_group(
        "conexion",
        "Cada valor se toma, en orden, de la opcion, de la variable de entorno " + PREFIJO_ENTORNO
        + "<NOMBRE>, del --env-file o se pide por consola. CLIENT_SECRET no se acepta como opcion.")
    grupo.add_argument("--env-file", metavar="RUTA",
                       help="archivo KEY=VALUE con las variables (por defecto: queuer-qa.env si existe)")
    for nombre, opcion, descripcion in VARIABLES:
        if opcion:
            grupo.add_argument(opcion, dest=nombre.lower(), metavar=nombre, help=descripcion)


def leer_env_file(ruta):
    valores = {}
    with open(ruta, encoding="utf-8") as archivo:
        for numero, linea in enumerate(archivo, start=1):
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            if linea.startswith("export "):
                linea = linea[len("export "):].strip()
            if "=" not in linea:
                raise ErrorConfiguracion("linea {} de {} sin '=': no es KEY=VALUE".format(numero, ruta))
            clave, valor = linea.split("=", 1)
            valor = valor.strip()
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
                valor = valor[1:-1]
            valores[clave.strip()] = valor
    return valores


def _origen_archivo(args):
    if args.env_file:
        if not os.path.isfile(args.env_file):
            raise ErrorConfiguracion("no existe el --env-file " + args.env_file)
        return args.env_file
    return ENV_FILE_POR_DEFECTO if os.path.isfile(ENV_FILE_POR_DEFECTO) else None


def _pedir(nombre, descripcion):
    if not sys.stdin.isatty():
        raise ErrorConfiguracion("falta " + nombre + " (" + descripcion + ") y la consola no es interactiva")
    if nombre in SECRETOS:
        return getpass.getpass(nombre + " (no se muestra): ").strip()
    return input(nombre + " (" + descripcion + "): ").strip()


def resolver(args, pedir_faltantes=True, requeridas=None):
    """Devuelve (config, origenes). origenes indica de donde salio cada variable, sin valores."""
    ruta = _origen_archivo(args)
    archivo = leer_env_file(ruta) if ruta else {}
    config, origenes = {}, {}
    for nombre, opcion, descripcion in VARIABLES:
        if requeridas is not None and nombre not in requeridas:
            continue
        valor_arg = getattr(args, nombre.lower(), None) if opcion else None
        valor_env = os.environ.get(PREFIJO_ENTORNO + nombre)
        if valor_arg:
            config[nombre], origenes[nombre] = valor_arg, "opcion " + opcion
        elif valor_env:
            config[nombre], origenes[nombre] = valor_env, "entorno " + PREFIJO_ENTORNO + nombre
        elif archivo.get(nombre):
            config[nombre], origenes[nombre] = archivo[nombre], "archivo " + os.path.basename(ruta)
        elif pedir_faltantes:
            config[nombre], origenes[nombre] = _pedir(nombre, descripcion), "consola"
            if not config[nombre]:
                raise ErrorConfiguracion("se requiere " + nombre)
        else:
            config[nombre], origenes[nombre] = None, "(sin definir)"
    _normalizar(config)
    return config, origenes


def _normalizar(config):
    for nombre in URLS:
        valor = config.get(nombre)
        if not valor:
            continue
        partes = urlsplit(valor)
        if partes.scheme not in ("http", "https") or not partes.netloc:
            raise ErrorConfiguracion(nombre + " debe ser una URL http(s) completa")
        config[nombre] = valor.rstrip("/")
    if config.get("PREFIX"):
        config["PREFIX"] = "/" + config["PREFIX"].strip("/")


def ocultar(config):
    """Copia de la configuracion apta para imprimir: los secretos se reemplazan."""
    return {clave: ("****" if clave in SECRETOS and valor else valor) for clave, valor in config.items()}
