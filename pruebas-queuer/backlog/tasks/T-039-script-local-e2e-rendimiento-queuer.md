---
id: T-039
aliases: [T-039]
title: "Script Python con llamadas HTTP directas para probar en local el flujo E2E de rendimiento por el queuer"
status: done
priority: P2
epic: E-e2e-rendimiento
estimate: M
depends_on: [T-034]
type: task
created: 2026-11-05
---

# T-039 — Script Python con llamadas HTTP directas para probar en local el flujo E2E de rendimiento por el queuer

## Objetivo
Crear `scripts/e2e_rendimiento_queuer.py` para que el usuario pruebe desde WSL el mismo flujo de los grupos `GH_campaignsQueuer` / `GH_notificationsQueuer` de [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]]: token de Cognito → `POST /campaigns` y `POST /notifications` del queuer → verificación de la entrega en el fakechannel (`get-messages`), con una carga pequeña y configurable. El script hace él mismo las llamadas HTTP, sin ejecutar el `.jmx`: sirve para pruebas rápidas del flujo y de la configuración. La ejecución del propio `.jmx` desde Python es [[T-040-script-local-jmeter-e2e-rendimiento|T-040]].

Hoy se tienen las variables de QA (`queuer-qa.env`), pero el usuario también va a probar en **dev**. Por eso el script no debe tener ningún ambiente fijo: todas las variables se pueden definir por el usuario.

## Documentación relacionada
- [Guía de pruebas — E2E de rendimiento](../../docs/pruebas.md#pruebas-e2e-de-rendimiento-jmeter)
- [Contrato de `POST /campaigns`](../../docs/endpoints/POST-api-v1-campaigns.md)
- [Contrato de `POST /notifications`](../../docs/endpoints/POST-api-v1-notifications.md)
- Script de referencia del estilo: `scripts/leer_segmento_kafka.py` y [scripts/README.md](../../scripts/README.md)

## Archivos a crear/modificar
- `scripts/e2e_rendimiento_queuer.py` (nuevo)
- `scripts/qe2e_config.py` (nuevo: carga de variables, compartida con [[T-040-script-local-jmeter-e2e-rendimiento|T-040]])
- `scripts/README.md` (sección del script nuevo)
- `docs/pruebas.md` (referencia al script en la sección de E2E de rendimiento)

## Tareas
- [x] **Variables configurables** en un módulo `scripts/qe2e_config.py`, que reutiliza [[T-040-script-local-jmeter-e2e-rendimiento|T-040]]. Orden de prioridad: argumentos de la línea de comandos → variables de entorno → archivo `--env-file` (por defecto `queuer-qa.env`; para dev, otro archivo, p. ej. `queuer-dev.env`, ignorado por git) → pedirlas por consola. Se usan los nombres de `queuer-qa.env`: `HOST`, `PREFIX`, `COGNITO_URL`, `CLIENT_ID`, `CLIENT_SECRET`, `ENDPOINT_GET_MESSAGE_FAKE`. Los secretos (`CLIENT_SECRET`) se piden con `getpass` y no se aceptan como argumento, para que no queden en el historial (igual que `leer_segmento_kafka.py`).
- [x] Dejar una plantilla sin valores (`scripts/e2e-rendimiento.env.example`) con todas las variables y comentarios de los valores de QA y dónde obtener los de dev. Agregar `*.env` (excepto `*.env.example`) al `.gitignore` de `pruebas-queuer`.
- [x] Opciones de la prueba con valores por defecto seguros: `--flujo` (`campaigns`, `notifications` o `ambos`), `--tps` (por defecto `1`), `--duracion` en segundos (por defecto `10`), `--hilos` (concurrencia), `--app-id` (por defecto `performance_test`), `--canal` (`WhatsApp`), `--nodo` (`N-03-99-10`), `--mensaje-esperado` (`Campaig_e2e_test_delivered_successfully`), `--intentos` / `--intervalo` de `get-messages`, `--timeout` y `--insecure` (desactiva la validación TLS, para hosts `int-*` con CA interna).
- [x] Token `client_credentials` igual que `Tx_oauthToken` (`client_id`, `client_secret`, `grant_type` en `x-www-form-urlencoded`); renovarlo si vence durante la corrida.
- [x] Bodies iguales a `ReqCampaignsQueuer` / `ReqNotificationsQueuer` del `.jmx` de WhatsApp: metadata en PascalCase, `metadata.Id` = `qe2e-<runId>-<uuid>`, `userIdentifier` = `57` + 10 dígitos aleatorios, UUIDs nuevos por petición, `dataTime` y `Time` ISO-8601 UTC.
- [x] Validar `202` y `status == accepted`; verificar la entrega como `ReqInteraction2*`: `GET <ENDPOINT_GET_MESSAGE_FAKE>/whatsapp/get-messages/<userIdentifier>` hasta que el primer elemento tenga `to` = usuario, `type` = `text` y `text.body` = mensaje esperado.
- [x] Control de la carga: ritmo por TPS con hilos (`concurrent.futures`), solo con la librería estándar de Python (sin dependencias).
- [x] **Protección:** cada `202` genera un mensaje real. Antes de enviar, mostrar el ambiente, el host y el número estimado de peticiones, y pedir confirmación (o `--si` para no preguntar). `--dry-run` muestra los bodies sin enviar ni pedir token. Límite duro por defecto de 1 TPS y 60 s salvo `--forzar`, hasta tener los límites acordados en [[T-033-prerrequisitos-e2e-rendimiento-qa|T-033]].
- [x] Resumen al final por flujo: peticiones, `202`, entregas verificadas, fallos por motivo, p50 / p95 / p99 del `POST` y de la transacción completa, y TPS efectivos. Con `--salida <archivo>.csv`, una fila por petición (`metadata.Id`, usuario, código, tiempos, entregada) sin datos sensibles.
- [x] Mensajes con `logging` (`--verbose` para el detalle por petición); nunca imprimir el token ni el secreto.
- [x] Código de salida: `0` todo OK; `2` hubo rechazos o entregas no verificadas; `1` errores de configuración, token o conexión.
- [x] Documentar en `scripts/README.md` la instalación, la configuración para QA y para dev, y ejemplos en bash para WSL.

## Criterios de aceptación
- [x] `--help` y `--dry-run` funcionan sin credenciales ni conexión.
- [x] Contra un mock local (queuer + fakechannel + Cognito), una corrida de 10 s a 1 TPS da todos los `metadata.Id` distintos con prefijo `qe2e-<runId>-`, el resumen correcto y código `0`; con el mock devolviendo errores o sin el mensaje, código `2`.
- [x] Ningún secreto aparece en la salida, los logs ni el CSV.
- [x] Con las variables de un ambiente diferente (archivo `--env-file` o variables de entorno), el script usa esos valores sin cambiar el código.
- [x] Una corrida corta en QA o dev (1 TPS, 10 s, flujo `ambos`), con aprobación del usuario, termina con todos los `202` y la entrega verificada.

## Verificación
```bash
cd pruebas-queuer
python3 scripts/e2e_rendimiento_queuer.py --help
python3 scripts/e2e_rendimiento_queuer.py --env-file queuer-qa.env --flujo ambos --dry-run
# Mock local: levantar el mock y apuntar HOST / COGNITO_URL / ENDPOINT_GET_MESSAGE_FAKE a http://127.0.0.1:<puerto>
python3 scripts/e2e_rendimiento_queuer.py --env-file <mock>.env --flujo ambos --tps 1 --duracion 10 --si --salida /tmp/qe2e-local.csv
# QA o dev, con aprobación del usuario (mensajes reales)
python3 scripts/e2e_rendimiento_queuer.py --env-file queuer-dev.env --flujo ambos --tps 1 --duracion 10
```

## Notas
- Pedido por el usuario el 2026-11-05 para probar en local desde WSL; primero en QA (variables de `queuer-qa.env`) y después en dev. El usuario pidió los dos enfoques: este (HTTP directo) y [[T-040-script-local-jmeter-e2e-rendimiento|T-040]] (ejecuta el `.jmx` con el JMeter instalado en WSL).
- Para **dev** hay que confirmar: host del queuer y prefijo, URL de Cognito y cliente con acceso a la `AuthorizationPolicy` de dev, URL del fakechannel de dev y un `applicationIdentifier` con segmento Kafka completo que `platform_campaigns_ms` entregue en el fakechannel (en dev las suites usan `others-test`, [[T-003-datos-prueba-kafka-dev|T-003]]). El nodo `N-03-99-10` y su texto pueden no existir en dev; por eso `--nodo` y `--mensaje-esperado` son configurables.
- Fuera de alcance: **Teams**, porque el pool de usuarios no recibe entregas en QA ([[T-035-e2e-rendimiento-queuer-teams|T-035]]); y la validación en Kafka ([[T-036-validacion-kafka-e2e-rendimiento|T-036]]), que necesita el secreto. Se pueden agregar después en otra tarjeta.
- No reemplaza la prueba de JMeter ([[T-040-script-local-jmeter-e2e-rendimiento|T-040]]) ni la ejecución desde el release ([[T-037-ejecucion-e2e-rendimiento-qa|T-037]]); sirve para probar el flujo y la configuración rápido y desde local.
- `get-messages` de WhatsApp: en [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]] la entrega se verificó en el primer intento. En Teams el fakechannel consume el mensaje al leerlo; si se agrega Teams, cada usuario solo puede leerse una vez.
- 2026-11-05 — Implementado en `pruebas-queuer/scripts/`: `qe2e_config.py` (carga de variables, compartida con T-040), `e2e_rendimiento_queuer.py`, `e2e-rendimiento.env.example`; sección nueva en `scripts/README.md` y referencia en `docs/pruebas.md` (E2E de rendimiento → Prueba local sin JMeter). `.gitignore` de `pruebas-queuer`: `*.env` (salvo `*.env.example`) y `__pycache__/`.
  - Desviaciones de la tarjeta: (1) las variables de entorno llevan prefijo `QE2E_` (`QE2E_HOST`, …) para no chocar con variables del sistema como `HOST` (zsh); el `--env-file` usa los nombres de `queuer-qa.env` sin prefijo. (2) `dataTime` va con el formato del `.jmx` (`yyyy-MM-dd HH:mm:ss`, `${__time}`), no ISO-8601; `metadata.Time` sí es ISO-8601 UTC. Así el body es igual al de `ReqCampaignsQueuer` / `ReqNotificationsQueuer`.
  - Ritmo: un hilo programa los envíos a `--tps` por flujo y un `ThreadPoolExecutor` de `--hilos` ejecuta envío + verificación; si la verificación satura los hilos, baja el TPS efectivo y el resumen lo muestra.
- 2026-11-05 — Verificación local (Python 3.12, WSL), sin tocar QA ni dev:
  - `--help` y `--dry-run` sin conexión: OK (`0`). El dry-run con `queuer-qa.env` muestra `CLIENT_SECRET` como `****` y el valor no aparece en la salida. `--tps 2` sin `--forzar` → `1`; sin consola y sin `--si` → `1`; `--env-file` inexistente → `1`. Prioridad opción > `QE2E_*` > archivo comprobada.
  - Mock local (Cognito + queuer + fakechannel, `ThreadingHTTPServer`), 1 TPS, 10 s, `ambos`: 20 peticiones, 20 `202`, 20 entregas, TPS efectivos 1,00, código `0`; 20 `metadata.Id` distintos `qe2e-<runId>-<uuid>` con un solo `runId`, `userIdentifier` siempre `57` + 10 dígitos, 20 filas en el CSV. Con `POST 500` en 1 de cada 3 → 14/20 y código `2`; sin entrega de notificaciones → 10/20 (`no entregada tras 5 intentos (get-messages 404)`) y código `2`. Credenciales inválidas → `Cognito respondio 400: {"error": "invalid_client"}` y `1`; sin servidor → `no se pudo conectar con Cognito` y `1`.
  - Ni el secreto ni el token aparecen en la consola (también con `--verbose`) ni en los CSV.
- 2026-11-05 — Corrida corta en QA, con aprobación del usuario (`queuer-qa.env`, `ext-qa`, `appId` `performance_test`, run `20261105152942`, 1 TPS, 10 s, `ambos`): **20/20 `202`** y **20/20 entregas** verificadas en el fakechannel (17 en el primer intento, 3 en el segundo), código `0`. TPS efectivos 1,00 por flujo. Ni el secreto ni el token en la salida ni en el CSV.
  - `POST` p50 413 ms (campañas) / 461 ms (notificaciones); p95 4,7 s / 4,2 s. Transacción completa p50 781 / 755 ms.
  - Los p95 son el arranque en frío del queuer: las peticiones de los primeros ~5 s terminan casi a la vez, unos 4,7 s después de iniciar la corrida (4,7 → 3,7 → 2,3 → 1,8 → 0,9 s), y desde ahí el `POST` queda en 320–460 ms. Coincide con la primera notificación de [[T-033-prerrequisitos-e2e-rendimiento-qa|T-033]] (3,9 s) y con la [observación 5](../../docs/observaciones.md#5-latencia-del-endpoint-atada-a-los-reintentos-de-kafka). No es del script; para la línea base de [[T-037-ejecucion-e2e-rendimiento-qa|T-037]] conviene descartar el calentamiento o reportarlo aparte.
- Pendiente para dev (no bloquea): confirmar host, Cognito, fakechannel y `appId` cuando el usuario corra allí.
