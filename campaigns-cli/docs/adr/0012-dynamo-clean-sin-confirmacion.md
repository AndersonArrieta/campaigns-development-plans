---
id: ADR-0012
title: "dynamo clean borra sin pedir confirmación"
status: accepted
date: 2026-10-16
supersedes: ADR-0011
---

# ADR-0012 — `dynamo clean` borra sin pedir confirmación

## Contexto
[ADR-0011](0011-vaciado-de-tablas-en-dev.md) decidió que `dynamo clean` vacía por completo las tablas
de dev, que son de uso exclusivo de las pruebas, y le puso como protección, entre otras,
`confirm_destructive`. En la práctica `clean` se corre antes de cada prueba y la confirmación
obliga a escribir `--yes` o a responder cada vez, sin proteger nada que el resto de las
protecciones no cubra.

## Decisión
- `dynamo clean` **no pide confirmación**: muestra el plan, informa qué va a borrar y borra.
  `--yes` se sigue aceptando (es opción global) pero no cambia nada.
- Todo lo demás de ADR-0011 sigue vigente: vaciado completo de todos los `app_id` o solo un
  `--campaign-id`, borrado por clave en lotes de 25, plan visible, `--dry-run`, `scan` de
  verificación final y el criterio de triage.
- Se mantiene el bloqueo en prod (`ensure_not_prod`): es la protección que importa.
- Los demás comandos destructivos (`dynamo purge`, `s3 rm`, `scheduler run`) siguen pidiendo
  confirmación.

## Consecuencias
- Un `dynamo clean` escrito por error en dev borra de inmediato; para ver antes qué se borraría,
  `--dry-run`.
- Si las tablas de dev pasan a compartirse con otro equipo, este ADR y el 0011 se reemplazan.
- Origen: [T-024](../../backlog/tasks/T-024-dynamo-clean-sin-confirmacion.md).
