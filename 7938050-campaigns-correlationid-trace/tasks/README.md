# Tasks — 7938050 Trazabilidad extremo a extremo con `notification_id`

Plan de origen: [`../plan-7938050-campaigns-correlationid-trace.md`](../plan-7938050-campaigns-correlationid-trace.md)
Rama: `feature/7938050-campaigns-correlationid-trace`

Ejecuta las tasks en orden. Cada una deja el código compilando y con las pruebas en verde, así que se puede hacer un commit por task.
El orden sigue la estrategia de despliegue del plan: primero **platform_campaigns_ms**, que tolera que falten los headers gracias al fallback; luego **scheduler_Lambda**; después **ingester_Lambda**; y al final la validación de punta a punta.

| # | Task | Componente | Ítems del plan | Depende de |
|---|---|---|---|---|
| 01 | [Validaciones previas con consumidores](01-validaciones-previas.md) | engine_nlp_ms / adapters out | D-1…D-6, Riesgos | — |
| 02 | [Headers de entrada `campaign_id`](02-pcms-headers-entrada.md) | platform_campaigns_ms | P-1, P-2, P-3 | — |
| 03 | [`TraceContext` de dominio](03-pcms-trace-context.md) | platform_campaigns_ms | P-4 | 02 |
| 04 | [Trazas en `BatchMessageUseCase`](04-pcms-batch-usecase-trazas.md) | platform_campaigns_ms | P-5 | 03 |
| 05 | [`message_id` y `campaign_id` en el mensaje al engine](05-pcms-engine-message-id.md) | platform_campaigns_ms | P-7, P-8, P-9 | 01, 04 |
| 06 | [Headers AMQP de correlación en `EngineMessageSender`](06-pcms-engine-sender-headers.md) | platform_campaigns_ms | P-10 | 05 |
| 07 | [`MessageIdentifier = notification_id` en el flujo online](07-pcms-adapter-message-id.md) | platform_campaigns_ms | P-6, P-11 | 01, 03 |
| 08 | [Header `CorrelationId` en `AdapterOutKafkaService`](08-pcms-adapter-out-kafka-header.md) | platform_campaigns_ms | P-12 | 07 |
| 09 | [Trazas en el flujo de reintentos](09-pcms-retry-trazas.md) | platform_campaigns_ms | P-13, P-14 | — |
| 10 | [Documentación platform_campaigns_ms](10-pcms-documentacion.md) | platform_campaigns_ms | P-15, P-16 | 02–09 |
| 11 | [`campaign_id` en los registros formateados del scheduler](11-scheduler-campaign-id-registros.md) | scheduler_Lambda | S-1, S-4 | 10 (desplegado) |
| 12 | [Headers Kafka `CorrelationId` y `campaign_id`](12-scheduler-headers-kafka.md) | scheduler_Lambda | S-2, S-3, S-6 | 11 |
| 13 | [Documentación scheduler_Lambda](13-scheduler-documentacion.md) | scheduler_Lambda | S-5, S-7 | 12 |
| 14 | [Logs de trazabilidad en el ingester](14-ingester-logs.md) | ingester_Lambda | I-1, I-2, I-3 | — |
| 15 | [Validación de punta a punta en dev](15-validacion-e2e.md) | Todos | §6, §9 | 01–14, 16 |
| 16 | [Corregir el feedback de reintento de engine_nlp_ms](16-engine-nlp-feedback-reintento.md) ⚠️ sujeta a D-6 | engine_nlp_ms | §2.5, D-6 | 01 |

## Convenciones

- **Commit por task:** `feat(campaigns): [7938050] <resumen de la task>`
- **Comandos de prueba:**
  - platform_campaigns_ms: `./gradlew clean build jacocoMergedReport` (o `./gradlew test` por módulo)
  - scheduler_Lambda / ingester_Lambda: `make test` (o `python -m pytest test/ --cov=src`)
- Las tasks 09, 14 y 16 no dependen de las demás y se pueden hacer en paralelo. T-16 debe estar en dev antes de la T-15.
- T-16 está fuera de los 3 componentes originales (engine_nlp_ms). Se ejecuta solo si se aprueba D-6; si no, pasa a una HU aparte.
