---
id: E-modular
title: "Pruebas modulares de rendimiento (JMeter)"
type: epic
---

# Pruebas modulares de rendimiento (JMeter)

Carga sobre `POST /campaigns` y `POST /notifications` en el script modular de `queuer_ms`: `Back/Modular/queuer_ms/SC_queuer.jmx` del repo `NU0284001_Artemis_Chatbots_Platform_PE`. Corre en **QA** con el Throughput Shaping Timer y envía los resultados a Elasticsearch por el Backend Listener (`ID_PRUEBA`). Al cerrar, comprueba que cada `202` quedó publicado en Kafka.

El grupo existente `GH_queuer` (`POST /queuer`, VariableSetter) no se modifica.

Documentación: [guía de pruebas — modulares](../../docs/pruebas.md#pruebas-modulares-jmeter) · [publicación en Kafka](../../docs/publicacion-kafka.md) · [observaciones](../../docs/observaciones.md)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-modular"
SORT id ASC
```
