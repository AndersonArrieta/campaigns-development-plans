#!/usr/bin/env python3
"""Lee de DynamoDB (dev) el destino Kafka que usa queuer_ms para un applicationIdentifier.

Replica el algoritmo de SegmentRoutingAdapter: toma el primer segmento de "segments" cuya
lista contiene el applicationIdentifier y devuelve "segments_destinies.<segmento>.kafka".

Solo lectura (GetItem). Las credenciales de AWS se toman del entorno (variables, perfil o
sesion) o se piden por consola sin mostrarlas; nunca se guardan ni se imprimen.
"""

import argparse
import getpass
import json
import os
import sys

TABLA = "nu0284001-artemis-chatbots-platform-dev-config-data"
COMPONENTE = "platform-segments-destinies-config-map-v1"
CONFIG_NAME = "config.json"
REGION = "us-east-1"
APP_ID = "others-test"

# Segmentos que modela QueuerConfiguration; un appId en otro segmento no se resuelve
SEGMENTOS_QUEUER = ("clients", "employees", "client-countries", "employee-countries", "others", "prototype")
CLAVES_KAFKA = ("campaigns", "notifications", "secret_campaigns")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Muestra el segmento y el destino Kafka (topicos y nombre del secreto) que usa "
                    "queuer_ms para un applicationIdentifier. Solo lectura.")
    parser.add_argument("--app-id", default=APP_ID, help="applicationIdentifier a resolver (por defecto: %(default)s)")
    parser.add_argument("--table", default=TABLA, help="tabla de configuracion (por defecto: %(default)s)")
    parser.add_argument("--component", default=COMPONENTE, help="partition key 'component' (por defecto: %(default)s)")
    parser.add_argument("--config-name", default=CONFIG_NAME, help="sort key 'config_name' (por defecto: %(default)s)")
    parser.add_argument("--region", default=REGION, help="region de AWS (por defecto: %(default)s)")
    parser.add_argument("--desde-archivo", metavar="RUTA",
                        help="lee la configuracion de un JSON local (config o salida de get-item) en vez de AWS")
    parser.add_argument("--comparar", action="store_true",
                        help="compara el resultado con los valores usados en la suite de aceptacion")
    parser.add_argument("--kafka-batch-topic", help="valor de kafkaBatchTopic usado en la suite")
    parser.add_argument("--kafka-online-topic", help="valor de kafkaOnlineTopic usado en la suite")
    parser.add_argument("--kafka-secret-name", help="valor de kafkaSecretName usado en la suite")
    return parser.parse_args()


def fallar(mensaje, codigo=1):
    print("ERROR: " + mensaje, file=sys.stderr)
    sys.exit(codigo)


def crear_sesion(boto3, region):
    """Usa las credenciales del entorno si existen; si no, las pide por consola sin mostrarlas."""
    sesion = boto3.Session(region_name=region)
    if sesion.get_credentials() is not None:
        print("Credenciales: tomadas del entorno (variables AWS_*, perfil o sesion).")
        return sesion
    print("No hay credenciales de AWS en el entorno. Pegalas a continuacion (no se muestran al escribir).")
    access_key = getpass.getpass("AWS_ACCESS_KEY_ID: ").strip()
    secret_key = getpass.getpass("AWS_SECRET_ACCESS_KEY: ").strip()
    session_token = getpass.getpass("AWS_SESSION_TOKEN (Enter si no aplica): ").strip() or None
    if not access_key or not secret_key:
        fallar("se requieren AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY")
    return boto3.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                         aws_session_token=session_token, region_name=region)


def leer_item_dynamodb(args):
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    except ImportError:
        fallar("falta boto3. Instalalo con: py -m pip install boto3")

    sesion = crear_sesion(boto3, args.region)
    cliente = sesion.client("dynamodb")
    try:
        respuesta = cliente.get_item(
            TableName=args.table,
            Key={"component": {"S": args.component}, "config_name": {"S": args.config_name}},
            ConsistentRead=True,
        )
    except NoCredentialsError:
        fallar("no se encontraron credenciales de AWS")
    except ClientError as e:
        codigo = e.response.get("Error", {}).get("Code", "")
        if codigo in ("ExpiredTokenException", "ExpiredToken"):
            fallar("las credenciales de AWS expiraron; genera unas nuevas")
        if codigo in ("UnrecognizedClientException", "InvalidSignatureException"):
            fallar("las credenciales de AWS no son validas para esta cuenta o region")
        if codigo == "AccessDeniedException":
            fallar("sin permiso dynamodb:GetItem sobre la tabla " + args.table)
        if codigo == "ResourceNotFoundException":
            fallar("no existe la tabla " + args.table + " en " + args.region)
        fallar("DynamoDB respondio " + codigo + ": " + e.response.get("Error", {}).get("Message", ""))
    except BotoCoreError as e:
        fallar("no se pudo conectar con AWS: " + str(e))

    item = respuesta.get("Item")
    if not item:
        fallar("no existe el item component=" + args.component + ", config_name=" + args.config_name)
    from boto3.dynamodb.types import TypeDeserializer
    deserializador = TypeDeserializer()
    return {clave: deserializador.deserialize(valor) for clave, valor in item.items()}


def leer_item_archivo(ruta):
    try:
        with open(ruta, encoding="utf-8") as archivo:
            contenido = json.load(archivo)
    except (OSError, ValueError) as e:
        fallar("no se pudo leer " + ruta + ": " + str(e))
    # Acepta la salida de `aws dynamodb get-item` (formato tipado) o la configuracion directa
    if isinstance(contenido, dict) and "Item" in contenido:
        item = contenido["Item"]
        data = item.get("data", {})
        if isinstance(data, dict) and "S" in data:
            return {"data": data["S"]}
        return {"data": data}
    return {"data": contenido}


def extraer_configuracion(item):
    if "data" not in item:
        fallar("el item no tiene el atributo 'data'; atributos presentes: " + ", ".join(sorted(item)))
    data = item["data"]
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError as e:
            fallar("el atributo 'data' no es un JSON valido: " + str(e))
    if not isinstance(data, dict):
        fallar("el atributo 'data' no tiene la estructura esperada")
    return data


def resolver_destino(config, app_id):
    segmentos = config.get("segments") or {}
    encontrados = [nombre for nombre, apps in segmentos.items()
                   if isinstance(apps, list) and app_id in apps]
    reconocidos = [nombre for nombre in encontrados if nombre in SEGMENTOS_QUEUER]
    ignorados = [nombre for nombre in encontrados if nombre not in SEGMENTOS_QUEUER]
    segmento = reconocidos[0] if reconocidos else None
    kafka = {}
    if segmento:
        destino = (config.get("segments_destinies") or {}).get(segmento) or {}
        kafka = destino.get("kafka") or {}
    return segmento, reconocidos, ignorados, kafka


def imprimir_resultado(app_id, segmento, reconocidos, ignorados, kafka):
    print()
    print("applicationIdentifier : " + app_id)
    if ignorados:
        print("Aviso                 : tambien aparece en segmentos que el queuer no reconoce: " + ", ".join(ignorados))
    if not segmento:
        print("Segmento              : (ninguno) -> el queuer responderia 422 'No existe segmento configurado'")
        return False
    if len(reconocidos) > 1:
        print("Aviso                 : aparece en varios segmentos " + ", ".join(reconocidos)
              + "; se toma el primero, como el queuer")
    print("Segmento              : " + segmento)
    completo = True
    for clave in CLAVES_KAFKA:
        valor = kafka.get(clave)
        if valor:
            print("kafka.{:<16}: {}".format(clave, valor))
        else:
            completo = False
            print("kafka.{:<16}: (falta) -> el queuer responderia 422".format(clave))
    return completo


def comparar(kafka, args):
    esperados = (
        ("kafkaBatchTopic", args.kafka_batch_topic, "campaigns"),
        ("kafkaOnlineTopic", args.kafka_online_topic, "notifications"),
        ("kafkaSecretName", args.kafka_secret_name, "secret_campaigns"),
    )
    print()
    print("Comparacion con la suite de aceptacion:")
    todo_coincide = True
    for propiedad, usado, clave in esperados:
        real = kafka.get(clave)
        if usado is None:
            print("  {:<17} (no indicado)".format(propiedad))
            continue
        coincide = usado == real
        todo_coincide = todo_coincide and coincide
        print("  {:<17} {}  usado={}  queuer={}".format(
            propiedad, "OK      " if coincide else "DISTINTO", usado, real or "(falta)"))
    return todo_coincide


def main():
    args = parse_args()
    item = leer_item_archivo(args.desde_archivo) if args.desde_archivo else leer_item_dynamodb(args)
    config = extraer_configuracion(item)
    segmento, reconocidos, ignorados, kafka = resolver_destino(config, args.app_id)
    completo = imprimir_resultado(args.app_id, segmento, reconocidos, ignorados, kafka)
    if args.comparar:
        coincide = comparar(kafka, args)
        sys.exit(0 if completo and coincide else 2)
    sys.exit(0 if completo else 2)


if __name__ == "__main__":
    main()
