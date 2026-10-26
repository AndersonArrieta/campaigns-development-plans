---
id: T-025
aliases: [T-025]
title: "Datos y credenciales para validar en Kafka los mensajes de la suite de aceptación en dev"
status: backlog
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
- [ ] Con sesión de AWS en `dev` (solo lectura), leer el item de segmentos en DynamoDB y anotar el segmento de `others-test`, los nombres de `kafka.campaigns`, `kafka.notifications` y `secret_campaigns`.
- [ ] Confirmar que el secreto tiene `username`, `password` y `bootstrapserver` (anotar solo los **nombres** de las claves, nunca los valores).
- [ ] Confirmar con el equipo dueño de los tópicos que el usuario del secreto puede leer, o qué otro secreto/usuario usar para consumir.
- [ ] Confirmar el truststore: si sirve el `cacerts` de `transcribe_ms` para el broker de `dev` y cómo se pasa su contraseña (`-DtruststorePassword`, variable secreta del release).
- [ ] Confirmar qué variables de AWS tiene o puede tener el release de aceptación de `queuer_ms` (las del release de `transcribe_ms` como referencia).
- [ ] Registrar los datos en `docs/pruebas.md` sin secretos.

## Criterios de aceptación
- [ ] Anotados el segmento de `others-test`, los nombres de los dos tópicos y del secreto en `docs/pruebas.md`.
- [ ] Confirmado el permiso de lectura sobre los dos tópicos para el usuario elegido.
- [ ] Definidas las propiedades que tendrá que recibir la suite (nombres de tópicos, secreto, credenciales AWS, contraseña del truststore) y cuáles son secretas en el release.

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
