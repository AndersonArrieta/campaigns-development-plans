---
id: ADR-0003
title: "Credenciales AWS en el .env, con prioridad sobre AWS_PROFILE"
status: accepted
date: 2026-10-13
supersedes:
---

# ADR-0003 — Credenciales AWS en el .env, con prioridad sobre AWS_PROFILE

## Contexto
El plan inicial asumía perfiles/SSO (`aws sso login`). En la práctica el equipo recibe llaves
(a menudo temporales, `ASIA...`) para la cuenta donde están las tablas.

## Decisión
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y, si son temporales, `AWS_SESSION_TOKEN` van en
  el `.env` (no versionado) y tienen prioridad sobre `AWS_PROFILE`; sin ellas se usa el perfil o
  la cadena estándar de boto3.
- Se manejan como `SecretStr`: no salen en `repr`, tracebacks ni mensajes; `config show` las enmascara.
- Las dos llaves van juntas y el token exige ambas; si no, la CLI no arranca.

## Consecuencias
- Los mensajes de error de credenciales apuntan al `.env`, no a `aws sso login`.
- Las credenciales temporales vencen y hay que renovarlas a mano.
- Decidido el 2026-10-13. Origen: [T-003](../../backlog/tasks/T-003-aws-output-guards.md).
