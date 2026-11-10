---
id: T-042
aliases: [T-042]
title: "Agregar a la ruta crítica de queuer_ms_test la campaña WhatsApp y la notificación Teams por el queuer"
status: backlog
priority: P1
epic: E-e2e
estimate: S
depends_on: [T-019]
type: task
created: 2026-11-10
---

# T-042 — Agregar a la ruta crítica de `queuer_ms_test` la campaña WhatsApp y la notificación Teams por el queuer

## Objetivo
Nuevo requerimiento: la ruta crítica del componente `queuer_ms_test` debe incluir dos de los escenarios E2E por el queuer de `queuer.feature` ([[T-017-e2e-notificaciones-queuer|T-017]], [[T-018-e2e-campanas-queuer|T-018]]): la **campaña por WhatsApp** y la **notificación en línea por Teams**. La ruta crítica se declara en el repo `NU0007001_Control_Ruta_Critica_E2E_DOP`, archivo `NU0284001_Artemis_Chatbots_Platform_MR_Test/rutacritica.json`. Hoy el componente `queuer_ms_test` solo declara los 20 escenarios de `integrator_node.feature`.

## Documentación relacionada
- [Guía de pruebas — E2E](../../docs/pruebas.md#pruebas-e2e-serenity)
- Escenarios: `Platform_test/src/test/resources/features/queuer.feature` (repo `NU0284001_Artemis_Chatbots_Platform_MR_Test`, `trunk`)

## Archivos a crear/modificar
- `C:\Users\AndersonElitArrietaR\repos\NU0007001_Control_Ruta_Critica_E2E_DOP\NU0284001_Artemis_Chatbots_Platform_MR_Test\rutacritica.json` (WSL: `/mnt/c/Users/AndersonElitArrietaR/repos/NU0007001_Control_Ruta_Critica_E2E_DOP/...`): solo el objeto con `"componente": "queuer_ms_test"`.
- `docs/pruebas.md`: indicar en la tabla de escenarios E2E cuáles están en la ruta crítica.

## Tareas
- [ ] En el repo DOP, `git pull` de `trunk` y crear rama desde `trunk` (la rama y el PR requieren confirmación del usuario).
- [ ] En el componente `queuer_ms_test`, agregar a `ruta` un segundo objeto después de `integrator_node.feature`:
  ```json
  {
      "nombre_feature": "queuer.feature",
      "escenarios": [
          "Queuer campaign E2E WhatsApp flow",
          "Queuer online notification E2E TEAMS flow"
      ]
  }
  ```
  Los nombres se copian literalmente de `queuer.feature`, incluido `TEAMS` en mayúsculas. La revisión `afec4d88` del repo DOP corrigió precisamente nombres de feature y escenarios que no coincidían.
- [ ] Actualizar `fecha_definicion` de `queuer_ms_test` a la fecha del cambio (`dd/MM/yyyy`), como en `afec4d88`. Mantener `"activo": true` y no tocar los demás componentes.
- [ ] Mantener el formato del archivo (4 espacios de sangría, fin de línea del repo) para que el diff muestre solo el bloque nuevo y la fecha.
- [ ] Commit, push y PR hacia `trunk` del repo DOP (requieren confirmación del usuario).
- [ ] Marcar en `docs/pruebas.md` las filas E2E-C01 y E2E-N02 como parte de la ruta crítica.

## Criterios de aceptación
- [ ] `rutacritica.json` es JSON válido y el componente `queuer_ms_test` tiene `integrator_node.feature` (sin cambios) y `queuer.feature` con exactamente los 2 escenarios.
- [ ] Cada escenario declarado existe con el mismo texto en `queuer.feature` de `trunk` de `_MR_Test`.
- [ ] El artefacto de `queuer_ms_test` incluye `queuer.feature` y `Queuer.java` ([[T-019-pipeline-queuer-ms-test|T-019]]).
- [ ] `git diff` en el repo DOP solo toca el componente `queuer_ms_test`.

## Verificación
```bash
DOP=/mnt/c/Users/AndersonElitArrietaR/repos/NU0007001_Control_Ruta_Critica_E2E_DOP
MRT=/mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR_Test
F=$DOP/NU0284001_Artemis_Chatbots_Platform_MR_Test/rutacritica.json

# JSON válido y contenido del componente
python3 -c "import json,sys; c=[x for x in json.load(open(sys.argv[1]))['componentes'] if x['componente']=='queuer_ms_test'][0]; print(c['fecha_definicion']); [print(r['nombre_feature'], r['escenarios']) for r in c['ruta']]" "$F"

# Cada escenario de queuer.feature declarado existe literalmente en trunk de _MR_Test
git -C "$MRT" show origin/trunk:Platform_test/src/test/resources/features/queuer.feature > /tmp/queuer.feature
for s in "Queuer campaign E2E WhatsApp flow" "Queuer online notification E2E TEAMS flow"; do
  grep -qxF "  Scenario: $s" /tmp/queuer.feature && echo "OK  $s" || echo "FALTA  $s"
done

# Solo cambia el componente queuer_ms_test
git -C "$DOP" -c core.autocrlf=true diff --stat
```

## Notas
- 2026-11-10 — Estado de partida: rama `trunk` del repo DOP en `dfd3349d` (al día con `origin/trunk`). `git status` muestra muchos `rutacritica.json` como modificados, pero con `git -c core.autocrlf=true status` el árbol está limpio: es solo fin de línea. No hay que descartar nada. Revisar el diff con `-c core.autocrlf=true`.
- Los 4 escenarios de `queuer.feature` están en `trunk` de `_MR_Test` (PR 1638381, `1496833`). Solo entran a la ruta crítica los 2 pedidos. Además, E2E-C02 (campaña Teams) puede dar un falso positivo si corre aislado ([[T-018-e2e-campanas-queuer|T-018]]). E2E-C01 y E2E-N02 usan usuario o mensaje aleatorio y no tienen ese riesgo.
- Si la ruta crítica filtra la ejecución por nombre de escenario, E2E-N02 (Teams) ya no tendría antes a E2E-N01 en la misma corrida. No le afecta: su mensaje es aleatorio (`Notif_e2e_test_<uuid>`).
- La ejecución que confirma que los escenarios de la ruta crítica pasan desde el release es la de [[T-020-ejecucion-e2e-qa|T-020]]. Si en el release no se puede confirmar, queda pendiente en `## Notas`, sin marcar.
- El nombre del componente (`queuer_ms_test`) coincide con la carpeta del pipeline de `_MR_Test` y con la entrada que ya existe en el JSON. No se crea un componente nuevo.
