---
id: T-028
aliases: [T-028]
title: "Actualizar la imagen base de queuer_ms para pasar el análisis de contenedor"
status: backlog
priority: P0
epic: E-seguridad
estimate: M
depends_on: []
type: task
created: 2026-10-26
---

# T-028 — Actualizar la imagen base de `queuer_ms` para pasar el análisis de contenedor

## Objetivo
El release de `queuer_ms` falla en `DevSecOps Engine Tool - engine_container` (2026-10-26, imagen `nu0284001-artemis-dev-ecr:queuer-v1-trunk.20261020.1-2668681`):

```
Security count issues (very critical: 0, critical: 0, high: 0, medium low: 54) is greater than or
equal to failure criteria (very critical: 2, critical: 4, high: 8, medium low: 15, operator: or)
```

Los 54 hallazgos no exceptuados son de la imagen base `artifactory.apps.bancolombia.com/evc/stable/amazoncorretto:21.0.12-al2023-headless_20261019`, no del código:

| Paquete | Versión actual | Corregido en | Hallazgos |
|---|---|---|---|
| `java-21-amazon-corretto` | `21.0.12+13-1.amzn2023.1` | `21.0.13.0.10-1.amzn2023.1` | 44 (CVE de Oracle Java SE: 2D, Networking, JGSS, JSSE, Security, JAXP, Compiler, etc. y CVE-2026-113470) |
| `pcre2` | `10.40-1.amzn2023.0.4` | `10.40-1.amzn2023.0.5` | 4 (CVE-2026-103111, CVE-2026-86145, CVE-2026-89160, CVE-2026-89156) |
| `libcap` | `2.73-1.amzn2023.0.7` | `2.73-1.amzn2023.0.8` | 3 (CVE-2026-94440, CVE-2026-78667, CVE-2026-78659) |
| `curl` | `8.21.0-5.amzn2023.0.2` | `8.21.0-5.amzn2023.0.3` | 1 (CVE-2026-92392) |
| `python3.9` | `3.9.25-1.amzn2023.0.9` | `3.9.25-1.amzn2023.0.11` | 1 (CVE-2026-19553) |
| `ca-certificates` | `2025.2.76-1.0.amzn2023.0.3` | `2025.2.76-1.0.amzn2023.0.4` | 1 (CVE-2026-113470) |

Además vencen excepciones que hoy no cuentan:
- CVE-2026-91403 (**high**, `java-21-amazon-corretto`), vence el **26/10/2026**. Se corrige con Corretto `21.0.13.0.10`.
- CVE-2026-111497 (**critical**, `brotli:1.1.0-1.amzn2023.0.1`), vence el **27/10/2026**. Se corrige en `1.1.0-1.amzn2023.0.2`.
- 15 de `openssl`, `python-pip`, `libX11`, `libXrender` y `python:3.9.25` (razón "base image vulnerability"), que vencen entre 18/12/2026 y 08/03/2027.

El `Dockerfile` usa `FROM #{java-version}#`: la imagen base sale de la variable `java-version` del release (la comparten los 15 componentes Java del repo). La solución es apuntar a una imagen EVC más reciente con Corretto `>= 21.0.13.0.10` y los paquetes corregidos, y volver a correr el release.

## Documentación relacionada
- Log del release del 2026-10-26 (pegado por el usuario en la conversación; reporte en vultracker `test/2933723`)
- `queuer_ms/deployment/Dockerfile`
- [Discuss: engine_container](https://discuss.apps.bancolombia.com/t/lanzamiento-engine-container-sca-analisis-de-seguridad-en-contenedores/8322)

## Archivos a crear/modificar
- Ninguno en el repo, salvo que se decida fijar la imagen en el `Dockerfile` (no recomendado: rompe el patrón del resto de componentes).
- Variable `java-version` del release de `queuer_ms` (o de la library donde esté definida). **Cambio con efecto en el ambiente: requiere confirmación del usuario.**

## Tareas
- [ ] Ubicar dónde se define `java-version` para el release de `queuer_ms`: variables del release, library propia o library global (`nu0284001-artemis-bot-platform-global-variables-aws` u otra). Anotar el valor actual.
- [ ] Buscar en `artifactory.apps.bancolombia.com/evc/stable/` la imagen `amazoncorretto:21-...-al2023-headless_<fecha>` más reciente y confirmar (con su SBOM, Prisma Cloud o `docker run --rm <imagen> rpm -q java-21-amazon-corretto pcre2 libcap curl python3.9 ca-certificates brotli openssl`) que trae las versiones de la columna "Corregido en". Si EVC aún no publicó una imagen corregida, **detenerse** y pasar a [[T-029-excepcion-vulnerabilidades-imagen-base|T-029]].
- [ ] Decidir con el usuario el alcance: sobrescribir `java-version` solo en el release de `queuer_ms` o actualizar la library compartida (impacta a los 15 componentes Java; coordinar con el equipo).
- [ ] Actualizar la variable y volver a correr el release de `queuer_ms` en `dev` (nuevo build desde la rama que se despliega, para que la imagen se construya con la base nueva).
- [ ] Revisar el resultado de `engine_container`: sin falla y sin hallazgos de la tabla.
- [ ] Revisar que el microservicio arranca y responde con la imagen nueva (health y suites de aceptación y humo; ver Notas).

## Criterios de aceptación
- [ ] `engine_container` termina sin `##[error]Security count issues` para la imagen nueva de `queuer_ms`.
- [ ] Ninguno de los hallazgos de la tabla aparece en el reporte; CVE-2026-91403 y CVE-2026-111497 quedan resueltos sin depender de su excepción.
- [ ] El release de `queuer_ms` en `dev` termina desplegado y `/actuator/health` responde `200`.

## Verificación
```bash
# Con acceso al registry de artifactory (VPN), confirmar versiones de la imagen candidata
IMG=artifactory.apps.bancolombia.com/evc/stable/amazoncorretto:<tag-candidato>
docker run --rm --entrypoint rpm "$IMG" -q java-21-amazon-corretto pcre2 libcap curl python3.9 ca-certificates brotli openssl

# Tras el release: el log de "DevSecOps Engine Tool - engine_container" no debe tener ##[error]
# y el health debe responder
curl -s -o /dev/null -w '%{http_code}\n' "$URL_EXT/actuator/health"   # 200
```

## Notas
- No es un defecto del código ni de las pruebas: cualquier release de `queuer_ms` con la imagen base actual falla igual. Bloquea la validación en `dev` de [[T-021-quitar-prefijo-api-v1|T-021]], [[T-022-ajustar-aceptacion-rutas-sin-api-v1|T-022]], [[T-024-eliminar-humo-campaigns-notifications|T-024]], [[T-026-validar-mensaje-kafka-aceptacion|T-026]] y [[T-027-truststore-solo-ca-secreto|T-027]].
- Prioridad `P0`: el release no despliega en `dev`, así que las suites no pueden ejecutarse en el pipeline.
- Si se actualiza la library compartida, los otros componentes Java tomarán la imagen nueva en su siguiente build: avisar al equipo.
- Cambiar variables del release es una acción con efecto real: se hace solo con confirmación explícita del usuario.
