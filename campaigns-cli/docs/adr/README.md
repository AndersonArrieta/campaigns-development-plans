# Decisiones de arquitectura (ADR)

Cada decisión que fija tecnología, límites entre componentes, acceso a datos o seguridad se
registra aquí. Las D-1…D-6 del plan original de la CLI se migraron como ADR-0001…0007.

| ADR | Decisión | Estado | Antes |
|---|---|---|---|
| [0001](0001-typer-y-uv.md) | Typer + Rich, gestionado con uv | accepted | D-1 |
| [0002](0002-capas-commands-services.md) | Capas `commands/` y `services/` con clientes inyectados | accepted | §4 del plan |
| [0003](0003-credenciales-en-env.md) | Credenciales AWS en el `.env`, con prioridad sobre `AWS_PROFILE` | accepted | D-3 |
| [0004](0004-busquedas-sin-gsi.md) | Sin GSI: scan filtrado por `campaign_id` y query por hora | accepted | D-4 |
| [0005](0005-ingesta-por-s3-y-por-invocacion.md) | Ingesta por subida a S3 y por invocación directa | proposed | D-5 |
| [0006](0006-hora-colombia.md) | Hora Colombia en la entrada y salida de la CLI | accepted | T-006 / T-008 |
| [0007](0007-ubicacion-del-codigo.md) | Código en `campaigns-cli/` dentro del repo de planes | accepted | D-6 |
| [0008](0008-cliente-http.md) | Cliente HTTP httpx y verificación SSL configurable para el fake channel | accepted | T-015 |

D-2 (nombres reales de recursos por ambiente) es configuración, no arquitectura: está en
[configuración](../configuracion.md#nombres-de-recursos-por-ambiente).

## Reglas

- Nombre: `NNNN-<slug>.md`, numeración correlativa.
- Estados: `proposed` → `accepted` → (`superseded` | `deprecated`).
- Un ADR `accepted` no se edita: se reemplaza con uno nuevo que lo indique en `supersedes:`, y
  el viejo pasa a `superseded` con `superseded_by:`.
- La tarjeta del [backlog](../../backlog/README.md) que toma la decisión enlaza su ADR.
