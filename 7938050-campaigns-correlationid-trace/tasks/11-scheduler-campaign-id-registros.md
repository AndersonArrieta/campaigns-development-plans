# T-11 — scheduler_Lambda: `campaign_id` en los registros formateados

- **Componente:** scheduler_Lambda
- **Ítems del plan:** S-1, S-4
- **Depende de:** T-10 (platform_campaigns_ms desplegado en dev)

## Objetivo

Que cada mensaje que arma `format_records` tenga `campaign_id` disponible para los headers (T-12) y los logs de enrutamiento.

## Archivos

| Archivo | Cambio |
|---|---|
| `src/models/scheduler_model.py` | `format_records` (l. 118-128) y `build_delivery_plan` (l. 246). |
| `test/src/models/test_scheduler_model.py` | Ajustar y ampliar. |

## Pasos

1. En `format_records`, agregar el campo al dict:
   ```python
   messages.append({
       "Id": message_id,
       "campaign_id": notification["campaign_id"],
       "app_id": notification["app_id"],
       "has_context": bool(notification.get("context")),
       "MessageBody": json.dumps(event_message, separators=(',', ':'), cls=DecimalEncoder)
   })
   ```
   (`campaign_id` ya es obligatorio en `validate_notification_schema`.)
2. Corregir el comentario `# Create a unique ID` (l. 118) por `# notification_id is the end-to-end correlation id`.
3. En `build_delivery_plan`, incluir `campaign_id` en el warning:
   `f"Notification '{notification.get('Id')}' (campaign '{notification.get('campaign_id')}') skipped: {error}"`.
4. Incluir `campaign_id` en el log de notificaciones expiradas (l. 114).

## Pruebas

- `format_records` devuelve `campaign_id` igual al del registro de Dynamo.
- `build_delivery_plan` conserva `campaign_id` en el mensaje enrutado (`dict(notification)` lo copia).
- Las pruebas existentes en verde.

## Criterios de terminado

- [x] Pruebas en verde (`uv sync --dev` + `uv run pytest -x --cov`, igual que `make test`): 159 pruebas, 0 fallos; cobertura total 98 %, `scheduler_model.py` 95 % (2026-10-08).
- [x] Sin cambios en el body Kafka (contrato intacto): `campaign_id` solo se agrega al dict interno del mensaje.
- [ ] Commit (lo hace el desarrollador).
