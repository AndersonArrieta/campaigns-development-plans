---
id: T-025
aliases: [T-025]
title: "Datos y credenciales para validar en Kafka los mensajes de la suite de aceptación en dev"
status: done
priority: P1
epic: E-entorno
estimate: S
depends_on: []
type: task
created: 2026-10-26
---

# T-025 — Datos y credenciales para validar en Kafka los mensajes de la suite de aceptación en `dev`

## Objetivo
Para que la suite de aceptación lea de Kafka el mensaje que publicó el queuer ([[T-026-validar-mensaje-kafka-aceptacion|T-026]]), hacen falta datos que [[T-003-datos-prueba-kafka-dev|T-003]] dejó sin confirmar porque no había sesión de AWS:
- los tópicos `kafka.campaigns` y `kafka.notifications` del segmento al que pertenece `others-test` en `dev`;
- el nombre del secreto `secret_campaigns` de ese segmento y que tenga las claves `username`, `password` y `bootstrapserver`;
- permiso de **lectura** sobre esos tópicos para el usuario del secreto (el queuer solo necesita escritura);
- cómo recibe el release de aceptación las credenciales AWS (`aws.accessKeyId`, `aws.secretKey`, `aws.sessionToken`) y la contraseña del truststore, igual que el release de `transcribe_ms`;
- el truststore (`cacerts`) que acepta el certificado del broker de `dev`.

Esta tarjeta no cambia código. Solo reúne y confirma los datos.

## Documentación relacionada
- [Enrutamiento por segmento](../../docs/publicacion-kafka.md#1-enrutamiento-por-segmento-segmentroutingadapter)
- [Credenciales](../../docs/publicacion-kafka.md#2-credenciales-kafkasecretprovider)
- [Datos de prueba en dev](../../docs/pruebas.md#datos-de-prueba-en-dev)
- Referencia: `transcribe_ms/deployment/acceptanceTest` (`SecretManager.java`, `KafkaManager.java`, `karate-config.js`, `src/test/resources/certificates/cacerts`)

## Archivos a crear/modificar
- `pruebas-queuer/docs/pruebas.md` (sección "Datos de prueba en dev")
- Ninguno en el repo de `queuer_ms`.

## Tareas
- [x] ~~Con sesión de AWS en `dev` (solo lectura), leer el item de segmentos en DynamoDB y anotar el segmento de `others-test`, los nombres de `kafka.campaigns`, `kafka.notifications` y `secret_campaigns`.~~ No hace falta: los valores se toman de las variables del release `kafkaBatchTopic`, `kafkaOnlineTopic` y `kafkaSecretName` (decisión del usuario).
- [x] Confirmar que el secreto tiene `username`, `password` y `bootstrapserver` (anotar solo los **nombres** de las claves, nunca los valores).
- [x] Confirmar con el equipo dueño de los tópicos que el usuario del secreto puede leer, o qué otro secreto/usuario usar para consumir. Se usa el secreto de `kafkaSecretName`, con el que `platform_campaigns_ms` ya publica y consume en esos tópicos.
- [x] Confirmar el truststore: el `cacerts` de `transcribe_ms` y `platform_campaigns_ms` es el mismo y se pasa con `-DtruststorePassword`. Alternativa sin archivo: CA de `certificate.cer` del secreto en formato PEM, como `Platform_test`.
- [x] Confirmar qué variables de AWS tiene o puede tener el release de aceptación de `queuer_ms` (las del release de `transcribe_ms` como referencia).
- [x] Registrar los datos en `docs/pruebas.md` sin secretos.

## Criterios de aceptación
- [x] ~~Anotados el segmento de `others-test`, los nombres de los dos tópicos y del secreto en `docs/pruebas.md`.~~ Sustituido por: anotadas en `docs/pruebas.md` las variables del release de las que salen esos valores.
- [x] Confirmado el permiso de lectura sobre los dos tópicos para el usuario elegido (lo usa `platform_campaigns_ms` para consumir en sus pruebas de aceptación).
- [x] Definidas las propiedades que tendrá que recibir la suite (nombres de tópicos, secreto, credenciales AWS, contraseña del truststore) y cuáles son secretas en el release.

## Verificación
```bash
# Solo lectura. Requiere sesion de AWS en dev.
aws dynamodb scan --table-name <tabla-config> --region us-east-1 \
  --query 'Items[?contains(to_string(@), `others-test`)]' > /tmp/segmentos.json
aws secretsmanager describe-secret --secret-id <secret_campaigns> --region us-east-1 --query Name
aws secretsmanager get-secret-value --secret-id <secret_campaigns> --region us-east-1 \
  --query SecretString --output text | jq 'keys'   # solo nombres de claves
```

## Notas
- Acciones de solo lectura. Si para leer hace falta crear usuarios, permisos o secretos, **detenerse** y pedir confirmación al usuario.
- La lectura no debe usar el consumer group de `platform_campaigns_ms` para no mover sus offsets (ver el mismo criterio en [[T-013-validacion-kafka-modular|T-013]]).
- 2026-10-26 — Ejecución parcial. Sin sesión de AWS en WSL (`aws sts get-caller-identity` → `NoCredentials`; solo existe el perfil `default`, sin credenciales). No se leyó DynamoDB ni Secrets Manager.
- **Encontrado sin AWS:**
  - El queuer en `dev` lee la configuración de la tabla `nu0284001-artemis-chatbots-platform-dev-config-data`, `component` = `platform-segments-destinies-config-map-v1`, `config_name` = `config.json` (`application-dev.yaml`). En la plantilla `segments_destinies_Conf/segments-destinies.yaml`, los tópicos y el secreto son variables del release (`#{campaigns-kafka-<segmento>}#`, `#{notifications-kafka-<segmento>}#`, `#{campaigns-secret-kafka-<segmento>}#`), así que sus valores no están en el repo.
  - `platform_campaigns_ms/deployment/acceptanceTest` ya publica y consume en `dev` con `applicationIdentifier` = `others-test` en estos mismos tópicos. Su release recibe `kafkaBatchTopic` (campañas, mensaje con `data.campaign`), `kafkaOnlineTopic` (notificaciones, mensaje con `data.notification`), `kafkaSecretName`, `truststorePassword` y `aws.accessKeyId`, `aws.secretKey`, `aws.sessionToken`. Lee del secreto las claves `bootstrapserver`, `username`, `password` (y `certificate.cer`). Como ese usuario publica y consume en los dos tópicos, es el candidato para que la suite del queuer lea.
  - Consume con `assign()` + `offsetsForTimes()` y `enable.auto.commit=false`, pero con `group.id` por defecto `campaigns-batch-consumer-group` y `campaigns-online-consumer-group`. No copiar esos valores: hay que confirmar que no son el consumer group real de `platform_campaigns_ms` y usar uno propio.
  - Truststore: el `cacerts` de `transcribe_ms` y el de `platform_campaigns_ms` son idénticos (md5 `d8b6a2194ec18c8a8f080df84928f3ab`). Sirve el mismo archivo, con `truststorePassword` como variable secreta del release.
- **Falta (pide intervención del usuario):**
  1. Los valores en `dev` de `kafkaBatchTopic`, `kafkaOnlineTopic` y `kafkaSecretName` de la library del release de aceptación de `platform_campaigns_ms` (solo nombres, no secretos), o una sesión de AWS de solo lectura para leer el item de DynamoDB y confirmar que coinciden con `campaigns`, `notifications` y `secret_campaigns` del segmento de `others-test`.
  2. Confirmar si el release de aceptación de `queuer_ms` puede usar las mismas variables secretas que `platform_campaigns_ms` (`aws.*`, `truststorePassword`) o si hay que crearlas.
  3. Confirmar el consumer group real de `platform_campaigns_ms` en `dev`, para que la suite del queuer nunca lo use.
- 2026-10-26 — Revisado `NU0284001_Artemis_Chatbots_Platform_MR_Test/Platform_test` (`utils/aws/service/Kafka.java`, `interactions/PublishNotificationEvent.java`). Publica en el tópico de notificaciones con `-DonlineNotificationTopic` y `-DkafkaSecretName`; los valores tampoco están en el repo (vienen del release, igual que `queuer_ms_test`).
  - **Truststore sin `cacerts`:** arma el truststore con `ssl.truststore.type=PEM` y `ssl.truststore.certificates` a partir de la clave `certificate.cer` del propio secreto (normaliza PEM o base64). Con esto la suite del queuer no necesita `cacerts` ni `truststorePassword`, y desaparece una variable secreta del release.
  - Credenciales AWS con `SystemPropertyCredentialsProvider` (`-Daws.accessKeyId`, `-Daws.secretAccessKey`, `-Daws.sessionToken`). Ojo: `transcribe_ms` y `platform_campaigns_ms` usan `aws.secretKey`; hay que elegir un nombre y documentarlo.
  - Lee `mechanism`/`sasl_mechanism` del secreto con `SCRAM-SHA-512` por defecto, y en el log enmascara el usuario (`LogMasker`) sin imprimir la contraseña.
- Sigue faltando: nombres reales de los dos tópicos y del secreto en `dev`, si el release de aceptación del queuer puede usar credenciales AWS y el consumer group real de `platform_campaigns_ms`.
- 2026-10-26 — **Decisión del usuario:** los nombres de tópicos y secreto no se fijan en la documentación. La suite del queuer los recibe de las mismas variables del release que ya usa la aceptación de `platform_campaigns_ms`: `kafkaBatchTopic` (campañas), `kafkaOnlineTopic` (notificaciones) y `kafkaSecretName`. Se cierra en `done` sin sesión de AWS.
- Propiedades que recibirá la suite (se implementan en T-026):

  | Propiedad | Origen | Secreta |
  |---|---|---|
  | `kafkaBatchTopic` | variable del release (misma que `platform_campaigns_ms`) | No |
  | `kafkaOnlineTopic` | variable del release (misma que `platform_campaigns_ms`) | No |
  | `kafkaSecretName` | variable del release (misma que `platform_campaigns_ms`) | No |
  | `aws.accessKeyId`, `aws.secretKey` o `aws.secretAccessKey`, `aws.sessionToken` | variables del release | Sí |
  | `truststorePassword` | variable del release (solo si se usa `cacerts`) | Sí |

- Queda para T-026: usar un `group.id` propio (`queuer-acceptance-<uuid>`) para no tocar el consumer group de `platform_campaigns_ms`, sin necesidad de conocer su nombre; confirmar al configurar el release que puede enlazar esas variables (library compartida o nuevas variables); y validarlo todo en `dev`.
