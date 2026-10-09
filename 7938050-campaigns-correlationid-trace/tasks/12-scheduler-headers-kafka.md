# T-12 — scheduler_Lambda: headers Kafka `CorrelationId` y `campaign_id`

- **Componente:** scheduler_Lambda
- **Ítems del plan:** S-2, S-3, S-6
- **Depende de:** T-11

## Objetivo

Publicar en cada registro Kafka los headers `CorrelationId = notification_id` y `campaign_id`, y registrarlos en los logs de publicación. Con esta task, platform_campaigns_ms deja de recibir `correlationId=null`.

## Archivos

| Archivo | Cambio |
|---|---|
| `src/classes/queue_class.py` | `send_messages` (l. 267-332). |
| `test/src/classes/test_queue_class.py` | Ajustar y ampliar. |

## Pasos

1. Definir constantes de módulo:
   ```python
   CORRELATION_ID_HEADER = "CorrelationId"   # Debe coincidir con EventHeadersDto en platform_campaigns_ms
   CAMPAIGN_ID_HEADER = "campaign_id"
   MESSAGE_ID_HEADER = "message_id"          # Se mantiene por compatibilidad
   ```
2. En el loop de `send_messages`:
   ```python
   message_id = message.get("Id", "")
   campaign_id = message.get("campaign_id", "")
   ...
   headers = [("content_type", b"application/json")]
   if message_id:
       encoded_id = message_id.encode("utf-8")
       headers.append((MESSAGE_ID_HEADER, encoded_id))
       headers.append((CORRELATION_ID_HEADER, encoded_id))
   if campaign_id:
       headers.append((CAMPAIGN_ID_HEADER, campaign_id.encode("utf-8")))
   ```
3. Guardar `campaign_id` en la tupla `pending` y agregar `Correlation Id` y `Campaign Id` a los logs de éxito, error y de body vacío o sin topic.
4. La key Kafka sigue siendo `message_id` (= `notification_id`).

## Pruebas (`test_queue_class.py`)

- Mock de `KafkaProducer`: verificar que `send` recibe headers que contienen
  `("CorrelationId", b"<notification_id>")`, `("message_id", b"<notification_id>")` y `("campaign_id", b"<campaign_id>")`.
- Mensaje sin `campaign_id` → no se envía ese header y no hay error.
- Mensaje sin `Id` → no se envían `message_id` ni `CorrelationId` (comportamiento actual).
- Los logs de éxito y error contienen `Campaign Id`.

## Criterios de terminado

- [x] Pruebas en verde (flujo de `make test` con `uv`): 162 pruebas, 0 fallos. `queue_class.py`: 93 %, las 8 líneas nuevas cubiertas; las 12 sin cubrir ya lo estaban. Total 98 % (2026-10-08).
- [ ] Commit (lo hace el desarrollador).
- [ ] Desplegado en dev: los logs de platform_campaigns_ms muestran `correlationId=<notification_id>` y `campaignId=<campaign_id>`.
