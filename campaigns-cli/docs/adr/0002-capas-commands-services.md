---
id: ADR-0002
title: "Capas commands/ y services/ con clientes boto3 inyectados"
status: accepted
date: 2026-10-13
supersedes:
---

# ADR-0002 — Capas commands/ y services/ con clientes boto3 inyectados

## Contexto
La lógica de las pruebas (consultas, polling, parseo) debe probarse sin AWS real y sin pasar por
la capa de línea de comandos.

## Decisión
- `commands/` solo parsea argumentos, exige la configuración necesaria, arma el servicio y
  muestra el resultado.
- `services/` contiene la lógica, no importa Typer y recibe los clientes boto3 (y `sleep`/`clock`
  cuando hay esperas) por parámetro.
- Ningún módulo crea clientes boto3 por su cuenta: todos salen de `AwsClients`.

## Consecuencias
- Los servicios se prueban con moto, `Stubber` o clientes falsos; los comandos con `CliRunner`.
- Agregar un grupo sigue siempre el mismo patrón ([desarrollo](../desarrollo.md#cómo-agregar-un-grupo-de-comandos)).
- Origen: [T-003](../../backlog/tasks/T-003-aws-output-guards.md).
