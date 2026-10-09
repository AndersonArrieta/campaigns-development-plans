# T-13 — scheduler_Lambda: documentación

- **Componente:** scheduler_Lambda
- **Ítems del plan:** S-5, S-7
- **Depende de:** T-12

## Objetivo

Documentar los headers que publica el scheduler y dejar registrada la decisión sobre `metadata.Id`. Con esta task se cierra el PR del scheduler.

## Archivos

| Archivo | Cambio |
|---|---|
| `docs/docs/asyncapi.yaml` | Headers del mensaje publicado. |
| `docs/docs/Functionalities.md` / `SequenceDiagrams.md` | Mención a la trazabilidad. |
| `src/models/scheduler_model.py` → `build_event_message` | Solo docstring (S-5). |

## Pasos

1. `asyncapi.yaml`: en el mensaje publicado al topic de campañas, documentar los headers:
   - `content_type` = `application/json`
   - `message_id` = `notification_id` (compatibilidad)
   - `CorrelationId` = `notification_id` (trazabilidad extremo a extremo)
   - `campaign_id` = `campaign_id` de la campaña
   - Key del registro = `notification_id`
2. Docstring de `build_event_message`: aclarar que `metadata.Id` es un UUID por publicación (id del evento) y que la correlación viaja en el header `CorrelationId` (decisión D-1).
3. `Functionalities.md`: un párrafo sobre cómo rastrear una notificación por `notification_id`.

## Criterios de terminado

- [x] Documentación coherente con el código: `@asyncapi/cli validate` da 0 errores (4 warnings de estilo que ya existían), el diagrama del caso de uso 2 se renderiza con `mermaid-cli` y las pruebas siguen pasando (162) tras el cambio de docstring (2026-10-08).
- [ ] PR del scheduler (T-11 … T-13) listo para revisión (falta el commit, lo hace el desarrollador).
