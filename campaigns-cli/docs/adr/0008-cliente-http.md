---
id: ADR-0008
title: "Cliente HTTP httpx y verificación SSL configurable para el fake channel"
status: accepted
date: 2026-10-13
supersedes:
---

# ADR-0008 — Cliente HTTP httpx y verificación SSL configurable para el fake channel

## Contexto
Para verificar la entrega de una campaña ([T-015](../../backlog/tasks/T-015-fake-channel-messages.md))
la CLI tiene que consumir dos servicios HTTP que no son de AWS: el endpoint OAuth2 de Cognito
(`client_credentials`) y el fake channel (`GET …/get-messages/{user}`). La prueba E2E de
`Platform_test` usa Unirest y **acepta cualquier certificado** (`configureUnirestSsl`).

## Decisión
- **httpx** como cliente HTTP (síncrono), con timeouts explícitos (30 s; 10 s de conexión).
  Las pruebas usan `httpx.MockTransport`, sin otra dependencia ni red.
  Alternativa descartada: `urllib` de la librería estándar (más código para formularios, JSON,
  timeouts y mocks).
- Los clientes salen de `HttpClients` (`http.py`), creados la primera vez que se piden, igual que
  `AwsClients`; ningún comando crea clientes HTTP por su cuenta.
- **El certificado se verifica por defecto.** `FAKE_CHANNEL_VERIFY_SSL=false` lo desactiva solo para
  el fake channel (no para Cognito) y la CLI lo avisa por stderr en cada ejecución.
- Los errores de transporte (conexión, timeout) y las respuestas inesperadas salen con el código 3,
  que pasa a significar "AWS o servicio externo".

## Consecuencias
- Nueva dependencia de ejecución: `httpx` (y sus transitivas `httpcore`, `h11`, `anyio`, `certifi`).
- En ambientes con certificados internos hay que poner `FAKE_CHANNEL_VERIFY_SSL=false` en el `.env`,
  una decisión explícita por ambiente en vez de un comportamiento oculto.
- El `client_secret` viaja en el cuerpo del POST a Cognito y nunca se incluye en mensajes de error.
