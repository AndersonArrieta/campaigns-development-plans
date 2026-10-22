---
id: T-010
aliases: [T-010]
title: "Parametrizar SC_queuer.jmx para los endpoints Kafka sin romper GH_queuer"
status: backlog
priority: P1
epic: E-modular
estimate: S
depends_on: [T-008]
type: task
created: 2026-10-22
---

# T-010 — Parametrizar `SC_queuer.jmx` para los endpoints Kafka sin romper `GH_queuer`

## Objetivo
Agregar a `SC_queuer.jmx` las variables que necesitan los dos grupos de carga nuevos ([[T-011-carga-campaigns-jmeter|T-011]] y [[T-012-carga-notifications-jmeter|T-012]]). El script debe seguir siendo **retrocompatible**: con las propiedades que hoy pasa el release, solo corre `GH_queuer` y los grupos nuevos quedan en cero.

## Documentación relacionada
- [Guía de pruebas — modulares](../../docs/pruebas.md#pruebas-modulares-jmeter)
- Referencia de estilo: `Back/Modular/campaigns_ms/SC_campaigns.jmx`, que tiene TPS, usuarios, rampa y duración separados por flujo.

## Archivos a crear/modificar
- `NU0284001_Artemis_Chatbots_Platform_PE/Back/Modular/queuer_ms/SC_queuer.jmx`, en el bloque `User Defined Variables`.

## Tareas
- [ ] En el repo PE, crear la rama `feature/<id>-queuer-ms-kafka-modular` desde `trunk`.
- [ ] Agregar estas variables con `${__P(...)}`:

| Variable | Propiedad | Valor por defecto |
|---|---|---|
| `V_pathCampaigns` | `pathCampaigns` | path de [[T-008-exposicion-rutas-qa\|T-008]] |
| `V_pathNotifications` | `pathNotifications` | path de [[T-008-exposicion-rutas-qa\|T-008]] |
| `V_kafkaAppId` | `kafkaAppId` | `appId` de [[T-009-datos-carga-kafka-qa\|T-009]] |
| `V_campaignsTps` / `V_notificationsTps` | `campaignsTps` / `notificationsTps` | `0` |
| `V_usersCampaigns` / `V_usersNotifications` | `usersCampaigns` / `usersNotifications` | `0` |
| `V_rampUpCampaigns` / `V_rampUpNotifications` | `rampUpCampaigns` / `rampUpNotifications` | `0` |
| `V_durationCampaigns` / `V_durationNotifications` | `durationCampaigns` / `durationNotifications` | `0` |
| `V_assertionTimeout` | `assertionTimeout` | `2000` (ms) |
| `V_runId` | — | `${__time(yyyyMMddHHmmss)}`, para marcar los `metadata.Id` de la corrida |

- [ ] No cambiar `V_path`, `users`, `rampUp`, `duration`, `contextVarsTps` ni `testAppId`, que son los que usa `GH_queuer`.
- [ ] No versionar credenciales: `clientId` y `clientSecret` siguen en `xxx`.

## Criterios de aceptación
- [ ] El `.jmx` es XML válido y abre en JMeter 5.5.
- [ ] Ejecutado con solo las propiedades actuales del release, el plan genera únicamente muestras de `GH_setUp` y `GH_queuer`.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/Modular/queuer_ms
python3 -c "import xml.etree.ElementTree as ET; ET.parse('SC_queuer.jmx'); print('XML OK')"
for v in V_pathCampaigns V_pathNotifications V_kafkaAppId V_campaignsTps V_notificationsTps V_runId V_assertionTimeout; do
  grep -q "<stringProp name=\"Argument.name\">$v</stringProp>" SC_queuer.jmx && echo "OK $v" || echo "FALTA $v"; done
git diff --stat
```

## Notas
- La convención de commits del repo PE es `perf(queuer_ms): ...` / `test(queuer_ms): ...`. Los commits y el push requieren confirmación del usuario.
