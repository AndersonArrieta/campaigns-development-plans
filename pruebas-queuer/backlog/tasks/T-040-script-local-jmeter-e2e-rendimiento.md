---
id: T-040
aliases: [T-040]
title: "Script Python que ejecuta en local (WSL) el .jmx E2E de rendimiento por el queuer"
status: backlog
priority: P2
epic: E-e2e-rendimiento
estimate: M
depends_on: [T-034, T-039]
type: task
created: 2026-11-05
---

# T-040 — Script Python que ejecuta en local (WSL) el `.jmx` E2E de rendimiento por el queuer

## Objetivo
Crear `scripts/jmeter_e2e_rendimiento_queuer.py` para que el usuario ejecute desde WSL, con su JMeter instalado, el propio `Back/E2E/whatsapp/SC_whatsappJMeterTest.jmx` del repo PE con solo los grupos `GH_campaignsQueuer` / `GH_notificationsQueuer` de [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]], contra QA o dev, y obtenga un resumen de la corrida. A diferencia de [[T-039-script-local-e2e-rendimiento-queuer|T-039]] (llamadas HTTP directas), aquí se prueba el script que correrá el release.

Como en T-039, ningún ambiente queda fijo: las variables las define el usuario. Se reutiliza `scripts/qe2e_config.py` de T-039.

## Documentación relacionada
- [Guía de pruebas — E2E de rendimiento](../../docs/pruebas.md#pruebas-e2e-de-rendimiento-jmeter) (propiedades de los grupos del queuer)
- Verificación local de [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]] (copia temporal sin `Tx_secretManager` ni Backend Listener)
- [scripts/README.md](../../scripts/README.md)

## Archivos a crear/modificar
- `scripts/jmeter_e2e_rendimiento_queuer.py` (nuevo)
- `scripts/README.md` (sección del script nuevo con los prerrequisitos)
- `docs/pruebas.md` (referencia al script en la sección de E2E de rendimiento)

## Prerrequisitos (los instala el usuario)
Estado de WSL revisado el 2026-11-05: JMeter 5.5 en `/opt/jmeter` (Groovy 3.0.11), solo Java 21 en `/usr/lib/jvm`, sin plugins en `lib/ext` y sin caché de Grape en `~/.groovy/grapes`. Falta:

| Dependencia | Por qué | Cómo instalarla (sugerido) |
|---|---|---|
| **JRE 17** | Groovy 3.0.11 de JMeter 5.5 no compila los JSR223 con Java 21 (`Unsupported class file major version 65`, visto en [[T-036-validacion-kafka-e2e-rendimiento|T-036]]) | `sudo apt install openjdk-17-jre-headless`. El script lanza JMeter con `JAVA_HOME` = `--java-home` (por defecto `/usr/lib/jvm/java-17-openjdk-amd64`) sin cambiar el Java por defecto del sistema |
| **Plugin Custom Thread Groups** (`jpgc-casutg` 2.10) | `ConcurrencyThreadGroup` de `GH_*Queuer` | Copiar `jmeter-plugins-casutg-2.10.jar` en `/opt/jmeter/lib/ext`, o con el Plugins Manager: `/opt/jmeter/bin/PluginsManagerCMD.sh install jpgc-casutg=2.10` |
| **Plugin Throughput Shaping Timer** (`jpgc-tst` 2.6) | `VariableThroughputTimer` hijo de cada `POST` | `jmeter-plugins-tst-2.6.jar` en `lib/ext`, o `PluginsManagerCMD.sh install jpgc-tst=2.6` |
| **`jmeter-plugins-cmn-jmeter`** (0.7) | Dependencia común de los dos plugins | `jmeter-plugins-cmn-jmeter-0.7.jar` en `/opt/jmeter/lib/ext` (el Plugins Manager la instala solo) |
| Plugins Manager (opcional) | Solo si se instala con `PluginsManagerCMD.sh` | `jmeter-plugins-manager-1.10.jar` en `lib/ext` y `cmdrunner-2.3.jar` en `lib`, y luego `java -cp /opt/jmeter/lib/ext/jmeter-plugins-manager-1.10.jar org.jmeterplugins.repository.PluginManagerCMDInstaller` |
| Librerías de `@Grab` — **solo con `--con-kafka`** | `kafka-clients` 3.5.1, `jackson-databind` 2.12.5, `software.amazon.awssdk` `secretsmanager` / `s3` / `bom` 2.15.0, usadas por `Tx_secretManager` y el teardown de Kafka | Con salida a Maven Central, Grape las descarga en la primera corrida (`~/.groovy/grapes`). Si la red lo bloquea, copiar la caché de Ivy de Windows (`C:\Users\<usuario>\.groovy\grapes`) a `~/.groovy/grapes` y correr con `--sin-grape` (`-Dgroovy.grape.enable=false` + jars en `user.classpath`) |
| Repo PE con la rama `feature/8016357-queuer-e2e-performance-test` | El `.jmx` con los grupos del queuer y `campaigns/DT_Campaigns.txt` | Ya existe en `/mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE` |

Ruta de JMeter configurable con `--jmeter` / `JMETER_HOME` (por defecto, el `jmeter` del `PATH`).

## Tareas
- [ ] **Comprobación previa** (`--revisar`, y siempre antes de correr): versión de JMeter, versión de Java de `--java-home` (debe ser 17), presencia de los jars de `casutg`, `tst` y `cmn-jmeter` en `lib/ext`, existencia del `.jmx` y de `campaigns/DT_Campaigns.txt`, y con `--con-kafka` las librerías de `@Grab`. Si falta algo, listar cada dependencia con el comando sugerido de la tabla y salir con código `1`, **sin instalar nada**.
- [ ] Variables con `qe2e_config.py` ([[T-039-script-local-e2e-rendimiento-queuer|T-039]]) y mapeo a las propiedades del `.jmx`:
  - `CLIENT_ID` → `cognitoId`; `CLIENT_SECRET` → `cognitoSecret`; `COGNITO_URL` → `cognitoServer` + `cognitoPath`
  - `HOST` → `queuerServer` (sin esquema) y `protocol`; `PREFIX` → `pathQueuerCampaigns` / `pathQueuerNotifications`
  - `ENDPOINT_GET_MESSAGE_FAKE` → `server` + `pathGetMsg` (`<path>/whatsapp/get-messages`)
  - Opciones → `usersCampaignsQueuer` / `rampUpCampaignsQueuer` / `campaignsQueuerDuration` / `campaignsQueuerTps` y los de notificaciones, según `--flujo` (`campaigns`, `notifications`, `ambos`); el resto de grupos queda en `0`.
- [ ] Secretos solo en un `.properties` temporal (permisos `600`, borrado al terminar aunque falle) pasado con `-q`, nunca con `-J`, para que no queden en `jmeter.log` ni en `ps`. Revisar al final que `jmeter.log` no tenga el secreto.
- [ ] Copia temporal del `.jmx` **en la misma carpeta** (los CSV son relativos al script), borrada al terminar, con:
  - `Tx_secretManager` desactivado (sin él, `GH_setup` detiene la prueba; ver [[T-038-secret-manager-opcional-e2e-rendimiento|T-038]]).
  - `GH_tearDownKafkaValidation` desactivado (la validación en Kafka necesita el secreto).
  - Backend Listener de Elasticsearch desactivado.
  - Con `--con-kafka` se mantienen `Tx_secretManager` y el teardown, y se piden `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` (→ `awsAccessKey` / `awsSecretKey` / `awsSessionToken`) para una identidad con acceso al secreto Kafka.
  - El `.jmx` versionado no se modifica.
- [ ] Ejecutar `jmeter -n` con `JAVA_HOME` de `--java-home`, `.jtl` en XML con subresultados (para separar `Req_CampaignsQueuer` / `Req_NotificationsQueuer` de `Req_Interaction2CampaignsQueuer` / `Req_Interaction2NotificationsQueuer`, nombres de [[T-044-nombres-req-grupos-queuer|T-044]]) y log en una carpeta de salida (`--salida-dir`, por defecto `./qe2e-<runId>/`, ignorada por git). Mostrar el progreso de JMeter en consola.
- [ ] Resumen al final leyendo el `.jtl`: por flujo, transacciones, `202`, entregas verificadas, fallos por motivo, p50 / p95 / p99 del `POST` y de la transacción completa (`Tx_*QueuerTest`) y TPS efectivos. Opcional `--reporte-html` (`jmeter -g <jtl> -o <dir>`).
- [ ] **Protección**, igual que T-039: confirmación antes de enviar con ambiente, host y carga estimada (`--si` para no preguntar); `--dry-run` hace la comprobación previa, genera la copia y el comando sin ejecutarlos y muestra el comando con los secretos ocultos; tope de 1 TPS y 60 s salvo `--forzar` hasta tener los límites de [[T-033-prerrequisitos-e2e-rendimiento-qa|T-033]]. Por defecto 15 usuarios por grupo (en T-034 dieron ~0,7 TPS con `Tps=1`).
- [ ] Opciones de rutas: `--jmx` (por defecto el de WhatsApp del repo PE), `--jmeter`, `--java-home`.
- [ ] Código de salida: `0` todo OK; `2` hubo rechazos o entregas no verificadas; `1` dependencias faltantes, configuración o error de JMeter.
- [ ] Documentar en `scripts/README.md` los prerrequisitos (tabla de arriba), la configuración para QA y dev y ejemplos en bash para WSL.

## Criterios de aceptación
- [ ] `--help` funciona sin dependencias; `--revisar` en el WSL actual lista JRE 17 y los plugins como faltantes y sale con `1`.
- [ ] Con las dependencias instaladas, `--dry-run` genera la copia temporal con `Tx_secretManager`, el teardown y el Backend Listener desactivados, y el comando sin secretos visibles.
- [ ] Con los grupos del queuer en `0` (o sin flujo), la copia genera las mismas muestras de setup que el `.jmx` original salvo los elementos desactivados.
- [ ] Contra un mock local (queuer + fakechannel + Cognito), una corrida corta da el resumen correcto, código `0`, y no deja la copia temporal ni el `.properties` en disco; con errores en el mock, código `2`.
- [ ] Ningún secreto aparece en la consola, `jmeter.log`, el `.jtl` ni el resumen.
- [ ] Una corrida corta en QA o dev (1 TPS, 60 s, flujo `ambos`), con aprobación del usuario, termina con todos los `202` y la entrega verificada, igual que la corrida de T-034.

## Verificación
```bash
cd pruebas-queuer
python3 scripts/jmeter_e2e_rendimiento_queuer.py --help
python3 scripts/jmeter_e2e_rendimiento_queuer.py --revisar
python3 scripts/jmeter_e2e_rendimiento_queuer.py --env-file queuer-qa.env --flujo ambos --dry-run
# Mock local
python3 scripts/jmeter_e2e_rendimiento_queuer.py --env-file <mock>.env --flujo ambos --tps 1 --duracion 30 --si
# QA o dev, con aprobación del usuario (mensajes reales)
python3 scripts/jmeter_e2e_rendimiento_queuer.py --env-file queuer-dev.env --flujo ambos --tps 1 --duracion 60
grep -c "<valor del secreto>" qe2e-*/jmeter.log   # esperado: 0
```

## Notas
- Pedido por el usuario el 2026-11-05: tiene JMeter instalado en WSL y quiere los dos enfoques (este y [[T-039-script-local-e2e-rendimiento-queuer|T-039]]). Las dependencias que falten las instala el usuario; el script solo las detecta y dice cómo instalarlas.
- Lo de dev que hay que confirmar es lo mismo que en T-039 (host, Cognito, fakechannel, `appId`). Además, `DT_Campaigns.txt` trae `performance_test` / `N-03-99-10`; si en dev no sirven, agregar `--app-id` / `--nodo` / `--mensaje-esperado` que generen un CSV temporal junto a la copia del `.jmx`.
- Fuera de alcance: Teams ([[T-035-e2e-rendimiento-queuer-teams|T-035]], pool sin entregas). Si se desbloquea, agregar `--canal teams` con `SC_teamsJMeterTest.jmx`.
- Si [[T-038-secret-manager-opcional-e2e-rendimiento|T-038]] se implementa, la copia temporal ya no necesita desactivar `Tx_secretManager`; revisar entonces qué sigue desactivando el script.
