---
id: E-entrega
title: "Verificación de entrega en canales"
type: epic
---

# Verificación de entrega en canales

Comprobar que el mensaje de una campaña llegó al usuario final consultando el **fake channel**
de la plataforma (WhatsApp y Teams), autenticado con un token de Cognito (`client_credentials`).
Es el último paso de la prueba E2E de `Platform_test`.

Documentación: [configuración](../../docs/configuracion.md) · [comandos § grupos planeados](../../docs/comandos.md#grupos-planeados)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-entrega"
SORT id ASC
```
