#!/usr/bin/env python3
"""Prueba E2E de rendimiento por el queuer con llamadas HTTP directas (T-039).

Replica los grupos GH_campaignsQueuer / GH_notificationsQueuer de SC_whatsappJMeterTest.jmx:
token client_credentials de Cognito -> POST /campaigns y /notifications del queuer (exige 202 y
status=accepted) -> verificacion de la entrega en get-messages del fakechannel de WhatsApp.

Cada 202 genera un mensaje real en el ambiente: pide confirmacion antes de enviar y limita la
carga a 1 TPS y 60 s salvo --forzar. Solo usa la libreria estandar de Python. El token y el
client_secret nunca se imprimen.
"""

import argparse
import csv
import json
import logging
import random
import ssl
import sys
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import qe2e_config

FLUJOS = ("campaigns", "notifications")
TPS_MAXIMO = 1.0
DURACION_MAXIMA = 60
RENOVAR_TOKEN_ANTES = 60

log = logging.getLogger("qe2e")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Envia campanas y notificaciones por el queuer y verifica su entrega en el "
                    "fakechannel de WhatsApp. Cada 202 es un mensaje real en el ambiente.")
    qe2e_config.agregar_argumentos(parser)
    prueba = parser.add_argument_group("prueba")
    prueba.add_argument("--flujo", choices=FLUJOS + ("ambos",), default="ambos",
                        help="flujo a probar (por defecto: %(default)s)")
    prueba.add_argument("--tps", type=float, default=1.0,
                        help="peticiones por segundo de cada flujo (por defecto: %(default)s)")
    prueba.add_argument("--duracion", type=int, default=10,
                        help="segundos de envio de cada flujo (por defecto: %(default)s)")
    prueba.add_argument("--hilos", type=int, default=10,
                        help="peticiones en curso a la vez, envio + verificacion (por defecto: %(default)s)")
    prueba.add_argument("--app-id", default="performance_test",
                        help="data.applicationIdentifier (por defecto: %(default)s)")
    prueba.add_argument("--canal", default="WhatsApp", help="data.sourceChannel (por defecto: %(default)s)")
    prueba.add_argument("--nodo", default="N-03-99-10",
                        help="data.campaign.notification.node (por defecto: %(default)s)")
    prueba.add_argument("--mensaje-esperado", default="Campaig_e2e_test_delivered_successfully",
                        help="texto que debe llegar al fakechannel; en notificaciones tambien es el "
                             "mensaje enviado (por defecto: %(default)s)")
    prueba.add_argument("--retries", default="3", help="data.campaign.retries (por defecto: %(default)s)")
    prueba.add_argument("--intentos", type=int, default=20,
                        help="consultas a get-messages por peticion (por defecto: %(default)s)")
    prueba.add_argument("--intervalo", type=float, default=1.0,
                        help="segundos entre consultas a get-messages (por defecto: %(default)s)")
    prueba.add_argument("--timeout", type=float, default=10.0,
                        help="timeout de cada llamada HTTP en segundos (por defecto: %(default)s)")
    prueba.add_argument("--insecure", action="store_true",
                        help="no valida el certificado TLS (hosts int-* con CA interna)")
    control = parser.add_argument_group("control")
    control.add_argument("--dry-run", action="store_true",
                         help="muestra la configuracion y un body por flujo; no pide token ni envia")
    control.add_argument("--si", action="store_true", help="no pide confirmacion antes de enviar")
    control.add_argument("--forzar", action="store_true",
                         help="permite superar 1 TPS o 60 s (requiere los limites acordados en T-033)")
    control.add_argument("--salida", metavar="CSV", help="guarda una fila por peticion en este CSV")
    control.add_argument("--verbose", action="store_true", help="detalle por peticion")
    return parser.parse_args()


def validar_args(args):
    if args.tps <= 0 or args.duracion <= 0 or args.hilos <= 0 or args.intentos <= 0:
        raise qe2e_config.ErrorConfiguracion("--tps, --duracion, --hilos e --intentos deben ser mayores que 0")
    if not args.forzar and (args.tps > TPS_MAXIMO or args.duracion > DURACION_MAXIMA):
        raise qe2e_config.ErrorConfiguracion(
            "la carga supera {} TPS o {} s; usa --forzar solo con los limites acordados (T-033)".format(
                TPS_MAXIMO, DURACION_MAXIMA))


def flujos_de(args):
    return FLUJOS if args.flujo == "ambos" else (args.flujo,)


# ---------------------------------------------------------------- bodies

def ahora_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def nuevo_usuario():
    return "57" + "".join(random.choice("0123456789") for _ in range(10))


def metadata(message_id, source):
    return {
        "Id": message_id,
        "Source": source,
        "SpecVersion": "1.0.2",
        "Type": "incoming.message",
        "DataContentType": "application/json",
        "DataSchema": "https://schema-registry.com",
        "Time": ahora_iso(),
    }


def body_campaign(args, message_id, usuario):
    return {
        "metadata": metadata(message_id, "platform:campaigns"),
        "data": {
            "applicationIdentifier": args.app_id,
            "sourceChannel": args.canal,
            "userIdentifier": usuario,
            "campaign": {
                "identifier": str(uuid.uuid4()),
                "retries": args.retries,
                "notification": {
                    "identifier": str(uuid.uuid4()),
                    "node": args.nodo,
                    # Mismo formato que ${__time(yyyy-MM-dd HH:mm:ss)} del .jmx
                    "dataTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            },
        },
    }


def body_notification(args, message_id, usuario):
    return {
        "metadata": metadata(message_id, "mapper:whatsapp"),
        "data": {
            "userIdentifier": usuario,
            "sourceChannel": args.canal,
            "applicationIdentifier": args.app_id,
            "notification": {
                "dataTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "identifier": str(uuid.uuid4()),
                "message": args.mensaje_esperado,
                "messageContext": {"agent_id": "1234"},
            },
        },
    }


BODIES = {"campaigns": body_campaign, "notifications": body_notification}


# ---------------------------------------------------------------- HTTP

class Http:
    def __init__(self, timeout, insecure):
        self.timeout = timeout
        self.contexto = ssl._create_unverified_context() if insecure else ssl.create_default_context()

    def llamar(self, metodo, url, headers, datos=None):
        """Devuelve (codigo o None, texto, segundos). codigo None = error de conexion en texto."""
        inicio = time.monotonic()
        peticion = Request(url, data=datos, headers=headers, method=metodo)
        try:
            with urlopen(peticion, timeout=self.timeout, context=self.contexto) as respuesta:
                texto = respuesta.read().decode("utf-8", "replace")
                return respuesta.status, texto, time.monotonic() - inicio
        except HTTPError as e:
            texto = e.read().decode("utf-8", "replace") if e.fp else ""
            return e.code, texto, time.monotonic() - inicio
        except (URLError, OSError) as e:
            motivo = getattr(e, "reason", e)
            return None, type(motivo).__name__ + ": " + str(motivo), time.monotonic() - inicio


class Token:
    """Token client_credentials compartido entre hilos; se renueva antes de vencer."""

    def __init__(self, http, config):
        self.http = http
        self.url = config["COGNITO_URL"]
        self.client_id = config["CLIENT_ID"]
        self.client_secret = config["CLIENT_SECRET"]
        self.valor = None
        self.vence = 0.0
        self.lock = threading.Lock()

    def obtener(self):
        with self.lock:
            if self.valor and time.monotonic() < self.vence - RENOVAR_TOKEN_ANTES:
                return self.valor
            datos = urlencode({"client_id": self.client_id, "client_secret": self.client_secret,
                               "grant_type": "client_credentials"}).encode("utf-8")
            codigo, texto, _ = self.http.llamar("POST", self.url, {
                "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}, datos)
            if codigo is None:
                raise RuntimeError("no se pudo conectar con Cognito: " + texto)
            if codigo != 200:
                raise RuntimeError("Cognito respondio {}: {}".format(codigo, texto[:200]))
            try:
                respuesta = json.loads(texto)
                self.valor = respuesta["access_token"]
            except (ValueError, KeyError):
                raise RuntimeError("la respuesta de Cognito no trae access_token")
            self.vence = time.monotonic() + float(respuesta.get("expires_in", 3600))
            log.debug("Token renovado; vence en %s s", respuesta.get("expires_in"))
            return self.valor


# ---------------------------------------------------------------- prueba

class Resultado:
    __slots__ = ("flujo", "message_id", "usuario", "inicio", "codigo", "aceptada", "post_ms",
                 "entregada", "intentos", "tx_ms", "motivo")

    def __init__(self, flujo, message_id, usuario):
        self.flujo, self.message_id, self.usuario = flujo, message_id, usuario
        self.inicio = time.monotonic()
        self.codigo, self.aceptada, self.post_ms = None, False, None
        self.entregada, self.intentos, self.tx_ms, self.motivo = False, 0, None, ""


def es_aceptada(texto):
    try:
        return json.loads(texto).get("status") == "accepted"
    except (ValueError, AttributeError):
        return False


def mensaje_entregado(texto, usuario, esperado):
    """Mismas comprobaciones que ReqInteraction2*: primer elemento con to, type=text y text.body."""
    try:
        mensajes = json.loads(texto)
    except ValueError:
        return False, "get-messages no devolvio JSON"
    if not isinstance(mensajes, list) or not mensajes:
        return False, "get-messages sin mensajes"
    primero = mensajes[0] if isinstance(mensajes[0], dict) else {}
    to = str(primero.get("to", "")).strip()
    tipo = str(primero.get("type", "")).strip()
    cuerpo = str((primero.get("text") or {}).get("body", "")).strip()
    if to == usuario and tipo == "text" and cuerpo == esperado:
        return True, ""
    return False, "mensaje distinto (to={}, type={}, body={})".format(to, tipo, cuerpo[:60])


def ejecutar_peticion(flujo, args, config, http, token, run_id):
    message_id = "qe2e-{}-{}".format(run_id, uuid.uuid4())
    usuario = nuevo_usuario()
    r = Resultado(flujo, message_id, usuario)
    try:
        bearer = {"Authorization": "Bearer " + token.obtener()}
    except RuntimeError as e:
        r.motivo = "token: " + str(e)
        return r
    url = config["HOST"] + config["PREFIX"] + "/" + flujo
    datos = json.dumps(BODIES[flujo](args, message_id, usuario)).encode("utf-8")
    r.codigo, texto, segundos = http.llamar("POST", url, dict(bearer, **{"Content-Type": "application/json"}), datos)
    r.post_ms = segundos * 1000
    if r.codigo is None:
        r.motivo = "POST sin respuesta: " + texto
    elif r.codigo != 202:
        r.motivo = "POST {}: {}".format(r.codigo, texto[:120])
    elif not es_aceptada(texto):
        r.motivo = "POST 202 sin status=accepted"
    else:
        r.aceptada = True
        verificar_entrega(r, args, config, http, token)
    r.tx_ms = (time.monotonic() - r.inicio) * 1000
    log.debug("%s %s usuario=%s codigo=%s post=%.0f ms entregada=%s intentos=%d %s", flujo, message_id,
              usuario, r.codigo, r.post_ms or 0, r.entregada, r.intentos, r.motivo)
    return r


def verificar_entrega(r, args, config, http, token):
    url = config["ENDPOINT_GET_MESSAGE_FAKE"] + "/whatsapp/get-messages/" + r.usuario
    for intento in range(1, args.intentos + 1):
        r.intentos = intento
        try:
            headers = {"Authorization": "Bearer " + token.obtener(), "Content-Type": "application/json"}
        except RuntimeError as e:
            r.motivo = "token: " + str(e)
            return
        codigo, texto, _ = http.llamar("GET", url, headers)
        if codigo == 200:
            r.entregada, motivo = mensaje_entregado(texto, r.usuario, args.mensaje_esperado)
            if r.entregada:
                r.motivo = ""
                return
            r.motivo = motivo
        elif codigo is None:
            r.motivo = "get-messages sin respuesta: " + texto
        else:
            r.motivo = "get-messages {}".format(codigo)
        if intento < args.intentos:
            time.sleep(args.intervalo)
    r.motivo = "no entregada tras {} intentos ({})".format(args.intentos, r.motivo)


def plan_de_envios(args):
    """Lista ordenada de (segundo de envio, flujo): cada flujo a --tps durante --duracion."""
    total = max(1, int(round(args.tps * args.duracion)))
    plan = [(i / args.tps, flujo) for flujo in flujos_de(args) for i in range(total)]
    return sorted(plan)


def correr(args, config, run_id):
    http = Http(args.timeout, args.insecure)
    token = Token(http, config)
    token.obtener()  # falla antes de enviar si las credenciales no sirven
    plan = plan_de_envios(args)
    futuros = []
    log.info("Run %s: %d peticiones en %d s", run_id, len(plan), args.duracion)
    inicio = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.hilos) as pool:
        for segundo, flujo in plan:
            espera = inicio + segundo - time.monotonic()
            if espera > 0:
                time.sleep(espera)
            futuros.append(pool.submit(ejecutar_peticion, flujo, args, config, http, token, run_id))
        log.info("Envios programados; esperando la verificacion de las entregas...")
    resultados = [f.result() for f in futuros]
    return resultados


# ---------------------------------------------------------------- resumen

def percentil(valores, p):
    if not valores:
        return None
    ordenados = sorted(valores)
    indice = max(0, int(-(-p * len(ordenados) // 100)) - 1)  # rango mas cercano
    return ordenados[min(indice, len(ordenados) - 1)]


def formato_ms(valor):
    return "-" if valor is None else "{:.0f} ms".format(valor)


def imprimir_resumen(resultados, args):
    print()
    print("Resumen")
    todo_ok = True
    for flujo in flujos_de(args):
        propios = [r for r in resultados if r.flujo == flujo]
        aceptadas = [r for r in propios if r.aceptada]
        entregadas = [r for r in propios if r.entregada]
        post = [r.post_ms for r in propios if r.post_ms is not None and r.codigo is not None]
        tx = [r.tx_ms for r in entregadas]
        inicios = [r.inicio for r in propios]
        ventana = max(inicios) - min(inicios) if len(inicios) > 1 else 0
        tps = (len(propios) - 1) / ventana if ventana > 0 else float(len(propios))
        print("  {}".format(flujo))
        print("    peticiones          : {}".format(len(propios)))
        print("    202 accepted        : {}".format(len(aceptadas)))
        print("    entregas verificadas: {}".format(len(entregadas)))
        print("    POST p50/p95/p99    : {} / {} / {}".format(*(formato_ms(percentil(post, p)) for p in (50, 95, 99))))
        print("    Tx   p50/p95/p99    : {} / {} / {}".format(*(formato_ms(percentil(tx, p)) for p in (50, 95, 99))))
        print("    TPS efectivos       : {:.2f}".format(tps))
        fallos = Counter(r.motivo for r in propios if not r.entregada)
        if fallos:
            todo_ok = False
            print("    fallos:")
            for motivo, cantidad in fallos.most_common():
                print("      {:>4}  {}".format(cantidad, motivo))
    ids = [r.message_id for r in resultados]
    if len(ids) != len(set(ids)):
        todo_ok = False
        print("  ERROR: hay metadata.Id repetidos")
    return todo_ok


def guardar_csv(ruta, resultados):
    columnas = ("flujo", "metadata_id", "user_identifier", "codigo", "accepted", "post_ms",
                "entregada", "intentos", "tx_ms", "motivo")
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(columnas)
        for r in resultados:
            escritor.writerow((r.flujo, r.message_id, r.usuario, r.codigo if r.codigo is not None else "",
                               r.aceptada, "" if r.post_ms is None else round(r.post_ms),
                               r.entregada, r.intentos, "" if r.tx_ms is None else round(r.tx_ms), r.motivo))
    print("CSV: " + ruta)


# ---------------------------------------------------------------- main

def imprimir_configuracion(config, origenes, args, run_id):
    visible = qe2e_config.ocultar(config)
    print("Configuracion (run {}):".format(run_id))
    for nombre, _, _ in qe2e_config.VARIABLES:
        print("  {:<26}: {}  [{}]".format(nombre, visible.get(nombre) or "(sin definir)", origenes.get(nombre)))
    total = max(1, int(round(args.tps * args.duracion)))
    print("  Ambiente                  : " + urlsplit(config.get("HOST") or "").netloc)
    print("  Flujos                    : {} | {} TPS x {} s = {} peticion(es) por flujo, {} en total".format(
        ", ".join(flujos_de(args)), args.tps, args.duracion, total, total * len(flujos_de(args))))
    print("  appId / canal / nodo      : {} / {} / {}".format(args.app_id, args.canal, args.nodo))
    print("  Mensaje esperado          : " + args.mensaje_esperado)


def confirmar(args):
    if args.si:
        return
    if not sys.stdin.isatty():
        raise qe2e_config.ErrorConfiguracion("sin consola interactiva: usa --si para confirmar el envio")
    respuesta = input("\nCada 202 es un mensaje real en este ambiente. Escribe 'si' para enviar: ")
    if respuesta.strip().lower() not in ("si", "s\u00ed"):
        print("Cancelado; no se envio nada.")
        sys.exit(0)


def main():
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    try:
        validar_args(args)
        config, origenes = qe2e_config.resolver(args, pedir_faltantes=not args.dry_run)
    except (qe2e_config.ErrorConfiguracion, OSError) as e:
        print("ERROR: " + str(e), file=sys.stderr)
        return 1
    imprimir_configuracion(config, origenes, args, run_id)

    if args.dry_run:
        for flujo in flujos_de(args):
            message_id = "qe2e-{}-{}".format(run_id, uuid.uuid4())
            print("\nPOST {}{}/{}".format(config.get("HOST") or "<HOST>", config.get("PREFIX") or "<PREFIX>", flujo))
            print(json.dumps(BODIES[flujo](args, message_id, nuevo_usuario()), indent=2, ensure_ascii=False))
        print("\n--dry-run: no se pidio token ni se envio nada.")
        return 0

    try:
        confirmar(args)
        resultados = correr(args, config, run_id)
    except qe2e_config.ErrorConfiguracion as e:
        print("ERROR: " + str(e), file=sys.stderr)
        return 1
    except RuntimeError as e:
        print("ERROR: " + str(e), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrumpido; las peticiones ya enviadas siguen en el ambiente.", file=sys.stderr)
        return 1
    todo_ok = imprimir_resumen(resultados, args)
    if args.salida:
        guardar_csv(args.salida, resultados)
    if not any(r.codigo is not None for r in resultados):
        return 1
    return 0 if todo_ok else 2


if __name__ == "__main__":
    sys.exit(main())
