---
id: T-030
aliases: [T-030]
title: "Script de Python para leer de DynamoDB el destino Kafka de un applicationIdentifier en dev"
status: done
priority: P1
epic: E-entorno
estimate: S
depends_on: []
type: task
created: 2026-10-26
---

# T-030 — Script de Python para leer de DynamoDB el destino Kafka de un `applicationIdentifier` en `dev`

## Objetivo
Para resolver [[B-003-topico-kafka-queuer-no-coincide|B-003]] hay que saber en qué tópicos y con qué secreto publica el queuer para `others-test`. El usuario pidió un script de Python que haga, de forma guiada, la lectura equivalente a:

```bash
aws dynamodb get-item --region us-east-1 \
  --table-name nu0284001-artemis-chatbots-platform-dev-config-data \
  --key '{"component":{"S":"platform-segments-destinies-config-map-v1"},"config_name":{"S":"config.json"}}'
```

y que muestre solo lo necesario: el segmento al que pertenece el `applicationIdentifier` y su bloque `kafka` (`campaigns`, `notifications`, `secret_campaigns`), aplicando el mismo algoritmo que `SegmentRoutingAdapter` ([publicación en Kafka §1](../../docs/publicacion-kafka.md#1-enrutamiento-por-segmento-segmentroutingadapter)).

## Documentación relacionada
- [Enrutamiento por segmento](../../docs/publicacion-kafka.md#1-enrutamiento-por-segmento-segmentroutingadapter): tabla, claves, atributo `data` con el JSON, estructura `segments` y `segments_destinies`.
- [[B-003-topico-kafka-queuer-no-coincide|B-003]]

## Archivos a crear/modificar
- `pruebas-queuer/scripts/leer_segmento_kafka.py` (nuevo)
- `pruebas-queuer/scripts/README.md` (nuevo: requisitos y cómo ejecutarlo en Windows)

## Tareas
- [x] Script con `boto3`, solo lectura (`GetItem`). Parámetros con valores por defecto de `dev`: `--app-id` (`others-test`), `--table`, `--component`, `--config-name`, `--region` (`us-east-1`).
- [x] **Credenciales sin quedar en archivos ni en el historial:**
  - si existen `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_SESSION_TOKEN` (o un perfil o sesión), usarlas;
  - si no, pedirlas por consola con `getpass` (no se muestran al escribir);
  - nunca escribirlas en disco ni imprimirlas, y no aceptarlas como argumentos de línea de comandos.
- [x] Leer el atributo `data` (JSON en texto; soportar también que venga como mapa) y aplicar el algoritmo del queuer: primer segmento de `segments` cuya lista contiene el `app-id` (comparación exacta), luego `segments_destinies.<segmento>.kafka`.
- [x] Imprimir solo: segmento, `campaigns`, `notifications`, `secret_campaigns` (nombre del secreto, no su valor), y si alguno falta (el queuer respondería `422`). No volcar el JSON completo.
- [x] Opción `--comparar` que reciba los valores usados en la suite (`kafkaBatchTopic`, `kafkaOnlineTopic`, `kafkaSecretName`) e indique cuáles coinciden y cuáles no.
- [x] Errores claros: credenciales inválidas o expiradas, `AccessDenied`, ítem no encontrado, `app-id` sin segmento.
- [x] README: instalar `boto3` (`py -m pip install boto3`), ejecutar en PowerShell, ejemplo de salida y recordatorio de no pegar credenciales en archivos ni en chats.
- [x] Revisar que el script corre con Python 3.8 o superior y que `--help` funciona sin credenciales.

## Criterios de aceptación
- [x] `py scripts\leer_segmento_kafka.py --help` funciona sin credenciales ni red.
- [x] Con credenciales válidas de `dev`, muestra el segmento de `others-test` y sus tres valores Kafka.
- [x] Las credenciales no quedan en archivos, en la salida ni en el historial de PowerShell (se piden con `getpass` o se toman del entorno).
- [x] Solo hace `GetItem`: ninguna operación de escritura.

## Verificación
```bash
# Local (sin credenciales): ayuda y validacion de sintaxis
python3 -m py_compile scripts/leer_segmento_kafka.py
python3 scripts/leer_segmento_kafka.py --help
# Prueba del algoritmo con un JSON de ejemplo (sin AWS), si el script expone --desde-archivo
python3 scripts/leer_segmento_kafka.py --desde-archivo <ejemplo.json> --app-id others-test

# Usuario, en Windows con credenciales de dev
py scripts\leer_segmento_kafka.py --app-id others-test --comparar `
  --kafka-batch-topic customerforeignsubsidiarycampaignexecution.initiatecampaignv1 `
  --kafka-online-topic customerforeignsubsidiarycampaignmanagement.executenotificationv1 `
  --kafka-secret-name nu0284001-artemis-dev-secret-operative-eda-composicion-nmt
```

## Notas
- Herramienta de apoyo del backlog: vive en el vault (`pruebas-queuer/scripts/`), no en el repo de `queuer_ms`.
- El usuario ejecuta el script con sus credenciales y comparte solo la salida (nombres de segmento, tópicos y secreto), que no incluye valores sensibles.
- Para probar la lógica sin AWS conviene una opción `--desde-archivo` que lea un JSON local con la misma estructura.
- 2026-10-26 — Creados `scripts/leer_segmento_kafka.py` y `scripts/README.md`. `boto3` se importa solo al ir a AWS, así que `--help` y `--desde-archivo` funcionan sin `boto3` ni credenciales.
- Verificación local (WSL, Python 3.12, sin `boto3`): `py_compile` OK; sintaxis válida para Python 3.8 (`ast.parse(..., feature_version=(3,8))`); `--help` OK. Con un JSON de ejemplo:
  - salida de `get-item` + `--comparar`: resuelve el segmento `others`, avisa que el app también está en un segmento no reconocido (`pilots`), marca `kafkaBatchTopic` como `DISTINTO` y sale con código 2;
  - configuración directa con claves faltantes: marca `(falta) -> 422`, código 2;
  - app sin segmento: `(ninguno) -> 422`, código 2;
  - sin `boto3` contra AWS: `ERROR: falta boto3. Instalalo con: py -m pip install boto3`, código 1.
- `grep` confirma que no hay operaciones de escritura en DynamoDB ni impresión o escritura de credenciales.
- Orden de segmentos: se toma el primero en el orden del JSON entre los que reconoce el queuer, y se avisa si hay más de uno.
- **blocked:** falta que el usuario lo ejecute con credenciales de `dev` (criterio "muestra el segmento de `others-test` y sus tres valores Kafka"). La salida alimenta [[B-003-topico-kafka-queuer-no-coincide|B-003]].
- 2026-10-26 — El usuario obtuvo con sus credenciales el contenido real del componente en `dev`. Pasado por el script con `--desde-archivo` (segmentos relevantes): `others-test` → segmento `others`, `campaigns` = `thirdpartycampaignexecution.initiatecampaignv1`, `notifications` = `thirdpartycampaignmanagement.executenotificationv1`, `secret_campaigns` = `nu0284001-artemis-dev-secret-operative-eda-experiencia-trv`; los 3 valores `DISTINTO` frente a la suite. Con `--app-id client-countries-test` los 3 coinciden (`OK`). Se cierra en `done`; el hallazgo alimenta B-003.
