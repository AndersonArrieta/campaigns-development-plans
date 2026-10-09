# T-14 — ingester_Lambda: logs de trazabilidad

- **Componente:** ingester_Lambda
- **Ítems del plan:** I-1, I-2, I-3
- **Depende de:** — (se puede hacer en paralelo; solo observabilidad)

## Objetivo

Que el origen de los identificadores quede registrado: qué `campaign_id` se generó para cada archivo y qué `notification_id` se creó para cada registro.

## Archivos

| Archivo | Cambio |
|---|---|
| `src/controllers/processor.py` | Resumen al final del procesamiento (I-1). |
| `src/models/notification.py` | Log DEBUG por registro en `_add_to_list` (I-2). |
| `test/src/models/test_notification.py`, `test/src/controllers/test_processor.py` | Pruebas (I-3). |

## Pasos

1. `processor.py`: después de `dbm.put_registries(ready_registries)` exitoso, registrar:
   ```python
   logger.info(f"[Campaign {campaign_id}] Stored {len(ready_registries)} notification(s) "
               f"for app_id={app_id} from file {file_route}")
   ```
2. `notification.py` → `_add_to_list`, después de asignar `notification_id`:
   ```python
   self.logger.debug(f"[Campaign {self._campaign_id}] notification_id={reg_copy['notification_id']} "
                     f"datetime={formatted_date} app_id={reg_copy['app_id']}")
   ```
   (En DEBUG para no saturar los logs INFO en campañas grandes.)
3. No cambiar el esquema de DynamoDB, el CSV ni la generación de los IDs.

## Pruebas

- `test_notification.py`:
  - Varios días u horas para un mismo usuario → cada registro tiene un `notification_id` UUID válido y **distinto**.
  - Todos los registros comparten el mismo `campaign_id`.
- `test_processor.py`: el log de resumen se emite con `campaign_id` (usar `caplog` o un mock de logger).

## Criterios de terminado

- [x] Pruebas en verde (flujo de `make test` con `uv`): 142 pruebas, 0 fallos. `notification.py` 100 %, `processor.py` 96 % (las líneas sin cubrir son las del bloque de excepción general, que ya existía); total 98 % (2026-10-08).
- [ ] PR del ingester listo para revisión (falta el commit, lo hace el desarrollador).
