# Propuesta: Idempotencia en el procesamiento de campañas

| | |
|---|---|
| **Proyecto** | Artemis Chatbots Platform – Flujo de campañas |
| **Componentes** | ingester_Lambda, scheduler_Lambda, platform_campaigns_ms, engine_nlp_ms |
| **Audiencia** | Equipo de Arquitectura |
| **Fecha** | 15/10/2026 |
| **Estado** | Propuesta para revisión |

---

## 1. Resumen ejecutivo

Hoy un mismo evento de campaña puede llegar más de una vez a `platform_campaigns_ms` y procesarse cada vez. El cliente final termina recibiendo **mensajes duplicados**.

Se propone incorporar un **control de idempotencia** en los consumidores de `platform_campaigns_ms`. Antes de procesar un evento, el servicio verifica en un registro compartido (DynamoDB) si ese evento ya se procesó. Si ya se procesó, lo descarta.

La solución:

- cubre los flujos **batch** y **online** con un único mecanismo;
- **no cambia el contrato** de los eventos ni requiere cambios en otros componentes;
- funciona con **varias réplicas** del microservicio;
- se puede **activar y desactivar** por configuración.

---

## 2. Contexto

El flujo de campañas tiene dos rutas:

- **Batch (programadas).**
  1. El `ingester_Lambda` carga el archivo CSV y crea una notificación en DynamoDB por cada combinación día × hora. Cada notificación tiene su propio `notification_id`.
  2. Cada hora, el `scheduler_Lambda` publica en Kafka las notificaciones de esa hora.
  3. `platform_campaigns_ms` las consume y las envía al motor conversacional (`engine_nlp_ms`). Si están fuera del horario permitido, las reprograma.
- **Online (inmediatas).** Un sistema externo publica la notificación en Kafka y `platform_campaigns_ms` la entrega directamente al adapter del canal (WhatsApp, Teams o Webchat).

Las reprogramaciones por horario y los reintentos que solicita el motor (`/v1/retry`) **no publican directamente**. Crean una nueva notificación en DynamoDB con el **mismo `notification_id`** y una **nueva fecha**, y el scheduler la publica cuando llega esa hora.

![Diagrama de idempotencia en campañas](diagrama-idempotencia-campanas.png)

*Figura 1. Diagrama de contenedores de la solución propuesta. En verde, el componente nuevo.*

---

## 3. Problema

Las plataformas de mensajería como Kafka garantizan que cada mensaje se entregue **al menos una vez**, no **exactamente una vez**. En el flujo actual, un evento se duplica en estas situaciones:

| Origen | Situación |
|---|---|
| scheduler_Lambda | Se ejecuta más de una vez en la misma hora o se reintenta. Como consulta por hora, republica todas las notificaciones de esa hora. |
| Productor Kafka | Reintenta un envío por errores de red. |
| Consumidor Kafka | Un reinicio de pod o un rebalanceo antes de confirmar el offset hace que se vuelvan a entregar mensajes ya procesados. |

**Impacto:** el cliente recibe el mismo mensaje varias veces. Eso afecta su experiencia, la percepción de la marca y el costo por mensaje en los canales.

---

## 4. Propuesta

### 4.1 Idea central

Cada evento se identifica con una **clave de idempotencia**. Antes de procesarlo, el servicio intenta **reservar** esa clave en un registro compartido:

- **Si la reserva tiene éxito**, es la primera vez que llega el evento y se procesa.
- **Si la clave ya existe**, es un duplicado: se descarta y queda registrado en logs y métricas.

La reserva es **atómica**. Si dos instancias reciben el mismo evento al mismo tiempo, solo una lo procesa.

### 4.2 Clave de idempotencia

| Flujo | Clave | Justificación |
|---|---|---|
| Batch | `batch # notification_id # datetime # retries` | Las reprogramaciones y los reintentos reutilizan el `notification_id` con otra fecha. Si la clave fuera solo el `notification_id`, se descartarían como si fueran duplicados. |
| Online | `online # notification_id` | En este flujo no hay reprogramaciones ni reintentos, así que el identificador basta. |

- El **prefijo** (`batch#` / `online#`) diferencia los flujos dentro del mismo registro y permite configurar una vigencia y métricas por flujo.
- Todos los datos de la clave **ya viajan en el evento**, así que no hay que cambiar el contrato.

**Comportamiento esperado (flujo batch):**

| Caso | ¿Se procesa? |
|---|---|
| Republicación del mismo evento (scheduler, Kafka, rebalanceo) | No, es un duplicado |
| Reprogramación por horario (nueva fecha) | Sí |
| Reintento solicitado por el motor (nueva fecha) | Sí |

### 4.3 Ciclo de vida del registro

1. **En proceso:** la clave se reservó y el evento se está procesando.
2. **Completado:** el evento se procesó correctamente. Las llegadas posteriores se descartan.
3. **Fallido:** el procesamiento falló. Una nueva publicación del mismo evento puede reprocesarse.

Controles adicionales:

- **Tiempo máximo en proceso:** si una instancia se cae a mitad del procesamiento, la reserva se libera a los pocos minutos para no bloquear el evento.
- **Expiración automática (TTL):** los registros se eliminan solos cuando vence la vigencia de la campaña.
- **Si el registro no está disponible:** se procesa igual y se dispara una alarma (fail-open). Se prefiere arriesgar un duplicado antes que perder una campaña. La política es configurable.

### 4.4 Ubicación en la arquitectura

- El control se implementa **dentro de `platform_campaigns_ms`** como un caso de uso de dominio, según la arquitectura limpia del servicio.
- El registro se guarda en una **tabla nueva de DynamoDB**, dedicada a idempotencia y separada de la tabla de campañas.
- El servicio reutiliza el cliente de DynamoDB que ya tiene, así que **no se agregan tecnologías nuevas** al stack.

---

## 5. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Decisión |
|---|---|---|---|
| **Caché en memoria del servicio** | Simple y sin infraestructura | No se comparte entre réplicas y se pierde al reiniciar | Descartada |
| **Redis / Valkey** | Muy baja latencia y TTL nativo | Infraestructura adicional para este servicio; requiere persistencia para ser confiable | Alternativa viable |
| **Exactly-once de Kafka (transacciones)** | Nativo del broker | No cubre efectos externos como la publicación a RabbitMQ y los adapters, ni las republicaciones del scheduler | Descartada |
| **DynamoDB (tabla dedicada)** ✅ | Ya está en el stack; escritura condicional atómica; TTL nativo; serverless | Latencia algo mayor que la de una caché | **Recomendada** |

---

## 6. Beneficios

- **Se eliminan los mensajes duplicados** al cliente final por reentregas o republicaciones.
- **Sin impacto en otros componentes:** no cambia el contrato ni requiere ajustes en el ingester, el scheduler ni el engine.
- **Escalable:** funciona con cualquier número de réplicas.
- **Observable:** métricas y logs de los duplicados detectados, por flujo.
- **Reversible:** se puede activar o desactivar por configuración.

---

## 7. Riesgos y limitaciones

| Riesgo | Mitigación |
|---|---|
| Ventana residual: si una instancia se cae justo después de enviar al motor y antes de marcar el registro como completado, el evento podría reprocesarse. | La probabilidad es baja. Cerrarla del todo requiere deduplicar también en `engine_nlp_ms` (mejora futura). |
| El ingester procesa dos veces el mismo archivo y genera identificadores nuevos, que el control no puede detectar. | Fuera de este alcance. Se propone que el ingester genere identificadores deterministas o lleve un control de archivos ya procesados. |
| El productor online genera un identificador nuevo en cada reintento. | Acordar con el equipo productor que reutilice el mismo `notification_id`. |
| El registro de idempotencia (DynamoDB) no está disponible. | Política fail-open configurable, con alarma. |

---

## 8. Plan de implementación (alto nivel)

1. Crear la tabla de idempotencia con TTL y los permisos para el servicio.
2. Implementar el control de idempotencia en `platform_campaigns_ms`, desactivado por defecto.
3. Hacer pruebas unitarias y de integración: eventos duplicados, concurrencia entre réplicas, reprogramaciones y reintentos.
4. Desplegar y activar gradualmente por ambiente (dev → cer → pdn), monitoreando las métricas de duplicados.

---

## 9. Decisiones solicitadas al equipo de Arquitectura

1. Aprobar **DynamoDB** como registro de idempotencia, frente a Redis/Valkey.
2. Validar la **política fail-open** cuando el registro no esté disponible.
3. Priorizar las **mejoras complementarias**: identificadores deterministas en el ingester y deduplicación en `engine_nlp_ms`.
4. Definir el **acuerdo de contrato** con el productor del flujo online.
