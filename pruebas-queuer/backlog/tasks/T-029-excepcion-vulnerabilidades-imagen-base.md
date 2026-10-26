---
id: T-029
aliases: [T-029]
title: "Gestionar excepción temporal de las vulnerabilidades de la imagen base si no hay imagen corregida"
status: backlog
priority: P1
epic: E-seguridad
estimate: S
depends_on: []
type: task
created: 2026-10-26
---

# T-029 — Gestionar excepción temporal de las vulnerabilidades de la imagen base si no hay imagen corregida

## Objetivo
Plan de contingencia de [[T-028-actualizar-imagen-base-queuer|T-028]]. Si EVC todavía no publicó una imagen `amazoncorretto:21` con Corretto `>= 21.0.13.0.10` y los paquetes corregidos, solicitar en Vulnerability Management (vultracker) una excepción temporal para los 54 hallazgos con razón "base image vulnerability", como las 15 que ya están vigentes para `openssl`, `python-pip`, `libX11`, `libXrender` y `python:3.9.25`. Así el release de `queuer_ms` puede desplegar en `dev` mientras sale la imagen corregida.

Solo aplica si T-028 se detiene por falta de imagen corregida. No sustituye a T-028.

## Documentación relacionada
- Tabla de hallazgos en [[T-028-actualizar-imagen-base-queuer|T-028]]
- Reporte en vultracker `test/2933723`
- [Discuss: engine_container](https://discuss.apps.bancolombia.com/t/lanzamiento-engine-container-sca-analisis-de-seguridad-en-contenedores/8322)

## Archivos a crear/modificar
- Ninguno en los repos.

## Tareas
- [ ] Confirmar con T-028 que no existe imagen EVC corregida (anotar la última disponible y sus versiones de `java-21-amazon-corretto`, `pcre2`, `libcap`, `curl`, `python3.9`, `ca-certificates`, `brotli`).
- [ ] Preparar la solicitud con: imagen escaneada, imagen base, lista de CVE (44 de `java-21-amazon-corretto`, 4 de `pcre2`, 3 de `libcap`, 1 de `curl`, 1 de `python3.9`, 1 de `ca-certificates`), versión que los corrige y fecha estimada de la imagen EVC corregida.
- [ ] Incluir las excepciones que vencen: CVE-2026-91403 (high, Corretto, vence 26/10/2026) y CVE-2026-111497 (critical, `brotli`, vence 27/10/2026), si siguen sin corrección.
- [ ] Enviar la solicitud por el canal del equipo DevSecOps. **Acción con efecto fuera del repo: requiere confirmación del usuario.**
- [ ] Cuando se apruebe, volver a correr el release de `queuer_ms` y confirmar que `engine_container` pasa.
- [ ] Dejar en `## Notas` la fecha de vencimiento de la excepción para retomar T-028 antes de esa fecha.

## Criterios de aceptación
- [ ] Excepción aprobada con fecha de vencimiento registrada.
- [ ] `engine_container` pasa para `queuer_ms` y el release despliega en `dev`.
- [ ] T-028 sigue abierta para resolver de fondo antes del vencimiento.

## Verificación
```bash
# Tras aprobar la excepcion, el log de "DevSecOps Engine Tool - engine_container" del release
# debe listar los CVE en "findings that were excepted" y no terminar con ##[error]
curl -s -o /dev/null -w '%{http_code}\n' "$URL_EXT/actuator/health"   # 200
```

## Notas
- La excepción es temporal: la corrección real es actualizar la imagen base (T-028).
- No ejecutar si T-028 encuentra una imagen corregida.
