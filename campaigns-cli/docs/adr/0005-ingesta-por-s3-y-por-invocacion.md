---
id: ADR-0005
title: "Ingesta por subida a S3 y por invocación directa de la Lambda"
status: proposed
date: 2026-10-13
supersedes:
---

# ADR-0005 — Ingesta por subida a S3 y por invocación directa de la Lambda

## Contexto
Para probar el ingester se puede reproducir el flujo real (subir el CSV al bucket, que dispara la
Lambda) o invocarla con un evento sintético, más rápido y aislado.

## Decisión (propuesta)
Soportar ambos:
- `s3 upload` para el flujo real ([T-005](../../backlog/tasks/T-005-s3-commands.md)).
- `lambda invoke ingester --s3-key` con un evento `ObjectCreated:Put` sintético, verificando
  antes que la key existe ([T-007](../../backlog/tasks/T-007-lambda-invoke.md)).

## Pendiente para aceptarla
Confirmar en el código del ingester que su trigger es S3 directo (y no SQS o EventBridge) y qué
campos del evento lee. T-007 la pasa a `accepted` o la reemplaza.

## Consecuencias
- Las dos vías producen envíos reales si la fecha/hora del CSV es próxima: ambas bloqueadas en prod.
