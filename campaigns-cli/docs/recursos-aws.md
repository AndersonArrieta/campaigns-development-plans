# Recursos AWS y patrones de acceso

Esquemas confirmados en el código de `ingester_Lambda`, `scheduler_Lambda` y `Platform_test`
(fuentes: `ingester_Lambda/src/models/notification.py`, `src/controllers/processor.py`,
`scheduler_Lambda/test/config/config.json`, `Platform_test/.../ValidateCampaignDynamo.java`).
El docstring de `src/campaigns_cli/services/dynamo_service.py` es la referencia en el código.

## Tabla de campañas (`CAMPAIGNS_TABLE_NAME`)

La escribe el ingester (una fila por usuario y fecha/hora) y la lee el scheduler cada hora.

| Atributo | Clave | Contenido |
|---|---|---|
| `datetime` | PK | Hora programada `YYYY-MM-DD HH:00:00`, hora Colombia. |
| `notification_id` | SK | UUID por usuario y fecha/hora; es el `CorrelationId` del flujo (HU 7938050). |
| `campaign_id` | — | UUID por archivo CSV. |
| `app_id`, `channel`, `user`, `notification_node`, `retries` | — | Datos de la notificación. |
| `context` | — | Mapa con los parámetros. |
| `expiration_date` | — | TTL (epoch). |

Sin índices secundarios ([ADR-0004](adr/0004-busquedas-sin-gsi.md)). Cómo la consulta la CLI:

| Necesidad | Acceso | Coste |
|---|---|---|
| Un registro con su hora | `get_item` | 1 lectura |
| Un registro sin su hora | `scan` con filtro, se detiene en el primero | Recorre la tabla |
| Registros de un rango horario | Un `query` por hora (máx. 744) | Proporcional al rango |
| Por `campaign_id` / `user` / `app_id` | `scan` filtrado (o `query` al GSI si se configura) | Recorre la tabla |

Las expresiones usan alias (`#f0`) porque `user` y `datetime` son palabras reservadas.
Los `Decimal` se convierten a `int`/`float` al serializar JSON.

## Tabla de logs del ingester (`CAMPAIGNS_LOGS_TABLE_NAME`)

Una fila por archivo procesado.

| Atributo | Clave | Contenido |
|---|---|---|
| `app_id` | PK | `UNKNOWN` si el archivo no se pudo leer. |
| `datetime` | SK | `str(datetime.now())` de la Lambda, con microsegundos; se asume UTC. |
| `result` | — | JSON en texto: `status`, `stats` (`total_processed`, `successful`, `omitted`, `errors`) y `body_result`. |

`parse_log_entry` tolera `result` vacío o inválido y extrae:
- de un `body_result` en texto: `campaign_id` (`[Campaign <id>]`) y archivo (`with file <key>`);
- de un `body_result` objeto: `log_errors` y `field_validation_errors` (y el `campaign_id` que traigan).

Consultas: por `app_id` es un `query` (descendente, con `BETWEEN` sobre `datetime`; el sufijo
`~` incluye los microsegundos del último segundo); sin `app_id` es un `scan` filtrado.
`--follow` vuelve a pedir desde la última fecha vista y descarta duplicados por `(app_id, datetime)`.

## CloudWatch Logs

- Log groups de las lambdas: `/aws/lambda/<nombre>`. El nombre corto que muestra la CLI quita
  el prefijo `nu0284001-...-campaigns-` (`campaigns-ingester-lambda`).
- `logs search` usa Logs Insights:
  ```
  fields @timestamp, @log, @logStream, @message
  | filter @message like "<texto literal>"
  | sort @timestamp asc
  | limit <n>
  ```
- `logs tail` usa `filter_log_events` con `filterPattern` entre comillas (texto literal).
- Log groups de `platform_campaigns_ms` y `engine_nlp_ms`: pendientes ([T-013](../backlog/tasks/T-013-trace-aguas-abajo.md)).

## Bucket de entrada (pendiente: [T-005](../backlog/tasks/T-005-s3-commands.md))

`nu0284001-artemis-chatbots-platform-{env}-campaigns-data`. `Platform_test` sube el CSV a la raíz
del bucket y la subida dispara `ingester_Lambda`: **subir un archivo produce envíos reales** si la
fecha/hora es próxima. Por eso `s3 upload` estará bloqueado en prod.

## Lambdas (pendiente: [T-007](../backlog/tasks/T-007-lambda-invoke.md))

`ingester_Lambda` (trigger S3, por confirmar) y `scheduler_Lambda` (programado cada hora). La
invocación directa está prevista en [ADR-0005](adr/0005-ingesta-por-s3-y-por-invocacion.md).

## Fake channel y Cognito (fuera de AWS SDK)

No son recursos que la CLI consulte con boto3, sino servicios HTTP ([ADR-0008](adr/0008-cliente-http.md)):

| Servicio | Petición | Respuesta |
|---|---|---|
| Cognito | `POST <COGNITO_TOKEN_URL>/oauth2/token`, form-urlencoded `grant_type=client_credentials&client_id=…&client_secret=…` | `{"access_token": "...", "expires_in": 3600, ...}` |
| Fake channel WhatsApp | `GET <FAKE_CHANNEL_BASE_URL>/whatsapp/get-messages/{teléfono}` con `Authorization: Bearer <token>` | `[{"messaging_product":"whatsapp","text":{"body":"…"},"to":"…","type":"text"}]` |
| Fake channel Teams | `GET <FAKE_CHANNEL_BASE_URL>/teams/get-messages/{recipient.id}` | `[{"channelId":"msteams","recipient":{"id":"…"},"text":"…","type":"message"}]` |
| Sin mensajes | — | `404 {"error":"No messages found for user <id>"}` |

El fake channel solo expone esas consultas: no hay endpoint para enviar ni para borrar mensajes, así
que los mensajes de corridas anteriores siguen ahí.

## EKS: pods de `platform_campaigns_ms` y `engine_nlp_ms`

| Dato | Valor en dev |
|---|---|
| Clúster | `eks-informacion-dev` |
| Namespace | `artemis-dev` |
| Selector campaigns | `app=platform-campaigns-others-v2` |
| Contenedores campaigns | `platform-campaigns-others-v2` (principal) e `istio-proxy` |
| Selector engine | `app=platform-engine-nlp-others-campaigns` |
| Contenedores engine | `platform-engine-nlp-others-campaigns` (principal) e `istio-proxy` |

En el engine, el `notification_id` aparece dentro del body JSON del mensaje recibido de RabbitMQ
(`"data":{…,"notification_id":"…"}`), en una línea `GenericMessageListener … Body:`.

La CLI usa estos endpoints de la API de Kubernetes ([ADR-0009](adr/0009-acceso-a-kubernetes.md)):

| Uso | Petición |
|---|---|
| Listar pods | `GET /api/v1/namespaces/{ns}/pods?labelSelector=...` |
| Un pod | `GET /api/v1/namespaces/{ns}/pods/{pod}` |
| Logs | `GET .../pods/{pod}/log?container=&tailLines=&sinceSeconds=&timestamps=true[&follow=true]` |
| Reconexión del seguimiento | Igual, con `sinceTime=<última línea, RFC3339>` |

Container Insights (`/aws/containerinsights/eks-informacion-dev/*`) existe pero no recibe eventos
desde 2024: no sirve como fuente de estos logs.
