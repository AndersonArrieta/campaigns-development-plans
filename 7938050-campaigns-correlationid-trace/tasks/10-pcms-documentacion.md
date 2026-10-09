# T-10 — platform_campaigns_ms: documentación

- **Componente:** platform_campaigns_ms
- **Ítems del plan:** P-15, P-16
- **Depende de:** T-02 … T-09

## Objetivo

Que AsyncAPI y la documentación funcional reflejen el nuevo contrato de trazabilidad. Con esta task se cierra el PR de platform_campaigns_ms.

## Archivos

| Archivo | Cambio |
|---|---|
| `docs/docs/asyncapi.yaml` | Headers y campos nuevos. |
| `docs/docs/SequenceDiagrams.md` | Diagrama de trazabilidad. |
| `docs/docs/Functionalities.md` | Sección "Trazabilidad extremo a extremo". |

## Pasos

1. `asyncapi.yaml`:
   - Schema `EventHeaders`: agregar `campaign_id` y describir `CorrelationId` como "= `notification_id` de la notificación; si falta, el servicio usa `notification_id` del body".
   - Ejemplos de los mensajes batch: `CorrelationId` igual al `identifier` de la notificación del ejemplo, y agregar `campaign_id`.
   - `AdapterOutMetadata.MessageIdentifier`: cambiar "UUID aleatorio" por "`notification_id` de la notificación". Documentar el header `CorrelationId` y la key del registro.
   - `EngineCampaignMessage`: agregar `message_id` y `campaign_id` al payload, y los headers AMQP `CorrelationId`, `campaign_id` y las props `messageId`/`correlationId`.
2. `SequenceDiagrams.md`: diagrama mermaid ingester → scheduler → campaigns → engine → adapter, con el `notification_id` en cada salto y el ciclo de reintento.
3. `Functionalities.md`: tabla de identificadores (§4 del plan) y cómo buscar una notificación en los logs.
4. Validar el YAML (por ejemplo, `npx @asyncapi/cli validate docs/docs/asyncapi.yaml`, si está disponible) y que `mkdocs build` no falle.

## Criterios de terminado

- [x] AsyncAPI válido y coherente con el código: `@asyncapi/cli validate` da 0 errores. Los 9 warnings de estilo (`id`, `license`, `messageId`…) ya existían. Diagramas Mermaid renderizados localmente con `mermaid-cli`. No se ejecutó `mkdocs build`: el plugin `kroki` renderiza contra un servidor externo (2026-10-08).
- [ ] PR de platform_campaigns_ms (T-02 … T-10) listo para revisión (falta el commit, lo hace el desarrollador).
- [ ] platform_campaigns_ms desplegado en dev **antes** de iniciar T-11.
