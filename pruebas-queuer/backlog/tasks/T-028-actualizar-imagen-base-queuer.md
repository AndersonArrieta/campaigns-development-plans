---
id: T-028
aliases: [T-028]
title: "Actualizar la imagen base de queuer_ms para pasar el análisis de contenedor"
status: done
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
- [x] ~~Ubicar dónde se define `java-version` para el release de `queuer_ms`: variables del release, library propia o library global (`nu0284001-artemis-bot-platform-global-variables-aws` u otra). Anotar el valor actual.~~ No hizo falta: la variable ya resuelve a la imagen EVC nueva (ver Notas).
- [x] Buscar en `artifactory.apps.bancolombia.com/evc/stable/` la imagen `amazoncorretto:21-...-al2023-headless_<fecha>` más reciente y confirmar (con su SBOM, Prisma Cloud o `docker run --rm <imagen> rpm -q java-21-amazon-corretto pcre2 libcap curl python3.9 ca-certificates brotli openssl`) que trae las versiones de la columna "Corregido en". Si EVC aún no publicó una imagen corregida, **detenerse** y pasar a [[T-029-excepcion-vulnerabilidades-imagen-base|T-029]].
- [x] ~~Decidir con el usuario el alcance: sobrescribir `java-version` solo en el release de `queuer_ms` o actualizar la library compartida (impacta a los 15 componentes Java; coordinar con el equipo).~~ No aplica: no se cambió ninguna variable.
- [x] Actualizar la variable y volver a correr el release de `queuer_ms` en `dev` (nuevo build desde la rama que se despliega, para que la imagen se construya con la base nueva).
- [x] Revisar el resultado de `engine_container`: sin falla (quedan 10 hallazgos de la tabla sin corrección disponible, ver Notas).
- [ ] Revisar que el microservicio arranca y responde con la imagen nueva (health y suites de aceptación y humo; ver Notas).

## Criterios de aceptación
- [x] `engine_container` termina sin `##[error]Security count issues` para la imagen nueva de `queuer_ms`.
- [ ] Ninguno de los hallazgos de la tabla aparece en el reporte; CVE-2026-91403 y CVE-2026-111497 quedan resueltos sin depender de su excepción. **Parcial:** se resolvieron los 44 del JDK y CVE-2026-91403; quedan 10 y CVE-2026-111497 porque AL2023 aún no publica la corrección (ver Notas).
- [x] El release de `queuer_ms` en `dev` termina desplegado y `/actuator/health` responde `200`.

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
- 2026-10-26 — Ejecución parcial. Sin CLI de Azure (`az`) en WSL ni sesión de Docker en Artifactory (`/v2/evc/stable/amazoncorretto/tags/list` → `401 authentication required`): no se pudo leer la library del release ni listar los tags EVC.
- **Upstream (Docker Hub, público):** `amazoncorretto:21.0.13-al2023-headless` publicada el 2026-10-23. Versiones dentro de la imagen (`rpm -q`): `java-21-amazon-corretto-headless-21.0.13.0.10-1.amzn2023.1` (**corregido**), `openssl-libs-3.5.8-1.amzn2023.0.3` (corregido), `libX11-1.8.10-2.amzn2023.0.2` y `libXrender-0.9.11-6.amzn2023.0.2` (corregidos); `pcre2-10.40-1.amzn2023.0.4`, `libcap-2.73-1.amzn2023.0.7` y `ca-certificates-2025.2.76-1.0.amzn2023.0.3` (**sin corregir**). `curl`, `python3.9`, `brotli` y `python3-pip` no vienen en la imagen upstream: los agrega la capa EVC.
- **Repositorio AL2023 (`2023.12.20261021`, `dnf repoquery --latest-limit 1`):** lo último disponible es `pcre2 .0.4`, `libcap .0.7`, `ca-certificates .0.3`, `curl .0.2`, `python3 3.9.25 .0.9` y `brotli .0.1`. **Amazon aún no publicó la corrección de esos paquetes**, así que ni EVC ni un `dnf update` pueden corregirlos hoy.
- **Proyección con una imagen EVC basada en Corretto 21.0.13:** quedan 10 medium low (pcre2 4, libcap 3, curl 1, python3.9 1, ca-certificates 1), por debajo del umbral de 15. CVE-2026-91403 (high) se corrige. CVE-2026-111497 (critical, brotli) sigue sin corrección y, al vencer su excepción el 27/10, suma 1 critical (umbral 4). **El engine pasaría.** El criterio "ninguno de los hallazgos de la tabla aparece" no se puede cumplir del todo hasta que AL2023 publique las correcciones: los 10 restantes quedan para una actualización posterior o para [[T-029-excepcion-vulnerabilidades-imagen-base|T-029]] si el equipo de seguridad lo exige.
- **Falta (requiere al usuario):**
  1. Buscar en Artifactory (`evc/stable/amazoncorretto`) un tag `21.0.13-al2023-headless_<fecha>` (fecha >= 20261023). Si no existe, pedirlo al equipo EVC o pasar a T-029.
  2. Ubicar dónde está `java-version` (variables del release de `queuer_ms`, library propia o global) y su valor actual.
  3. Decidir el alcance (solo `queuer_ms` o la library compartida) y confirmar el cambio de la variable antes de aplicarlo.
- 2026-10-26 18:41 — Release de `trunk` (imagen `queuer-v1-trunk.20261020.1-2668835`) construido sobre `artifactory.apps.bancolombia.com/evc/stable/amazoncorretto:21.0.13-al2023-headless_20261026`: `engine_container` termina con `##[warning]Security count issues (very critical: 0, critical: 0, high: 0, medium low: 10) is not greater than or equal to failure criteria` y el release despliega con éxito (según el usuario). La variable `java-version` ya resuelve a la imagen EVC publicada hoy; no se cambió ninguna variable desde aquí.
- Coincide con la proyección: quedan 10 medium low (`pcre2` 4, `libcap` 3, `curl` 1, `python3.9` 1, `ca-certificates` 1). Desaparecen los 44 del JDK, CVE-2026-91403 (high) y las excepciones de `openssl`, `libX11`, `libXrender` y `python-pip`. Siguen exceptuadas CVE-2026-111497 (critical, `brotli`, vence 27/10/2026) y CVE-2025-12781 (`python:3.9.25`, "Transferred Finding").
- El fallo de las 16:47 no dependía de la rama: esa imagen (`…-2668681`) se construyó con la base anterior `21.0.12-al2023-headless_20261019`. Un release nuevo de la rama de pruebas debería construirse con la base nueva y pasar.
- Se cierra en `done`: el objetivo (que el release pase el engine y despliegue en `dev`) se cumple. Los 10 hallazgos restantes no tienen corrección en AL2023 (`2023.12.20261021`) y quedan por debajo del umbral. Cuando venza la excepción de `brotli` (27/10) sumará 1 critical (umbral 4): sigue pasando. [[T-029-excepcion-vulnerabilidades-imagen-base|T-029]] deja de ser necesaria mientras el conteo no supere los umbrales.
- 2026-10-26 18:49 — Redespliegue del stage del release `…-2668681` (el que falló a las 16:47): la imagen se reconstruye (`Created date 13:49`) pero otra vez sobre `21.0.12-al2023-headless_20261019` y vuelve a fallar con 54 medium low. Causa: en los releases clásicos de Azure DevOps los valores de las variables (incluidos los variable groups) se fijan al **crear** el release; redesplegar un stage reutiliza el `java-version` de ese momento. **Para tomar la imagen nueva hay que crear un release nuevo**, no redesplegar uno anterior al 2026-10-26.
- 2026-10-26 18:49 — Redespliegue del stage del release `…-2668681` (el que falló a las 16:47): la imagen se reconstruye (`Created date 13:49`) pero otra vez sobre `21.0.12-al2023-headless_20261019` y vuelve a fallar con 54 medium low. Causa: en los releases clásicos de Azure DevOps los valores de las variables (incluidos los variable groups) se fijan al **crear** el release; redesplegar un stage reutiliza el `java-version` de ese momento.
- 2026-10-26 — El usuario creó un release nuevo ("Create release") con el mismo artefacto y `engine_container` pasó. **Para tomar una imagen base nueva hay que crear un release nuevo**, no redesplegar uno creado antes de que cambie `java-version`.
