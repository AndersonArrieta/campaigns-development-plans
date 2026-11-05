---
id: T-038
aliases: [T-038]
title: "Correr los grupos E2E del queuer sin exigir el secreto Kafka en el setup"
status: backlog
priority: P1
epic: E-e2e-rendimiento
estimate: S
depends_on: [T-034]
type: task
created: 2026-11-05
---

# T-038 — Correr los grupos E2E del queuer sin exigir el secreto Kafka en el setup

## Objetivo
Hoy `GH_setup` de los scripts E2E corre `Tx_secretManager` con `stoptest`: si la identidad del release no puede leer el secreto Kafka, la prueba se detiene antes de arrancar cualquier grupo, aunque solo corran `GH_campaignsQueuer` / `GH_notificationsQueuer`, que no publican en Kafka. Hacer que el secreto solo se exija cuando lo necesitan los grupos directos (`GH_campaigns` / `GH_notifications`) o la validación en Kafka del teardown, sin cambiar el comportamiento actual cuando corren.

## Documentación relacionada
- [Guía de pruebas — E2E de rendimiento](../../docs/pruebas.md#pruebas-e2e-de-rendimiento-jmeter)
- Referencia: [[T-013-validacion-kafka-modular|T-013]] (`AccessDenied` de `FullStackQARole` sobre el secreto)

## Archivos a crear/modificar
- `Back/E2E/whatsapp/SC_whatsappJMeterTest.jmx`
- `Back/E2E/teams/SC_teamsJMeterTest.jmx`

## Tareas
- [ ] Revisar qué grupos y samplers consumen lo que deja `Tx_secretManager` (credenciales Kafka en `props`) y si algo más del setup depende de él.
- [ ] Ejecutar `Tx_secretManager` solo si hay usuarios en los grupos directos o si la validación en Kafka de [[T-036-validacion-kafka-e2e-rendimiento|T-036]] está activa (p. ej. con un `If Controller` sobre las propiedades de usuarios), manteniendo `stoptest` en ese caso.
- [ ] Revisar el teardown (`GH_tearDownKafkaValidation`): con `Tx_preTestCampaignKafka` desactivado nunca recibe `setup.status`; que se salte limpio cuando no hubo setup de Kafka.
- [ ] Aplicar el mismo cambio en WhatsApp y Teams.

## Criterios de aceptación
- [ ] Con los valores por defecto y con los grupos directos activos, el setup y el teardown generan las mismas transacciones que antes del cambio.
- [ ] Con solo los grupos del queuer activos y una identidad sin acceso al secreto, la prueba corre sin `Tx_secretManager` y sin errores del teardown.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/E2E/whatsapp
# 1) Solo grupos del queuer, identidad FullStackQARole (sin acceso al secreto): la prueba arranca y termina
jmeter -n -t SC_whatsappJMeterTest.jmx -l /tmp/qe2e-nosecret.jtl -q <secretos>.properties \
  -JusersCampaignsQueuer=1 -JcampaignsQueuerTps=1 -JcampaignsQueuerDuration=30
# 2) Valores por defecto: mismas muestras que HEAD
```

## Notas
- Surge de la revisión de la épica (2026-11-05): en [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]] y [[T-035-e2e-rendimiento-queuer-teams|T-035]] las corridas en QA se hicieron con una copia temporal sin `Tx_secretManager`; desde el release eso no es posible.
- Cambia el setup existente de los scripts E2E: confirmar con el equipo dueño antes de llevarlo a la rama.
- Si [[T-036-validacion-kafka-e2e-rendimiento|T-036]] se activa, el secreto vuelve a ser obligatorio; esta tarjeta no resuelve el acceso de la identidad del release al secreto.
