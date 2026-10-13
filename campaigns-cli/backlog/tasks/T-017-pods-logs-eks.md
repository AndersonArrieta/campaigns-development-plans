---
id: T-017
aliases: [T-017]
title: "Grupo pods: logs de los pods de platform_campaigns_ms en EKS"
status: done
priority: P2
epic: E-logs
estimate: L
depends_on: [T-003, T-015]
type: task
created: 2026-10-13
---

# T-017 — Grupo `pods`: logs de los pods de `platform_campaigns_ms` en EKS

## Objetivo
Automatizar desde la CLI lo que hoy se hace a mano para ver los logs del microservicio de campañas:

```bash
aws eks update-kubeconfig --name eks-informacion-dev --region us-east-1
kubectl config set-context --current --namespace=artemis-dev
kubectl logs -f -l app=platform-campaigns-others-v2 --tail 1000
```

La CLI hablará directo con la API de Kubernetes del clúster, sin depender de `kubectl` ni del CLI de
`aws` y sin modificar `~/.kube/config`. Usará las credenciales del `.env`, como el resto de la CLI.
Además deja una fuente para buscar el `notification_id` en `platform_campaigns_ms`, pendiente en
[[T-013-trace-aguas-abajo|T-013]].

**Paso previo (puede reducir el alcance):** si los logs de los pods ya llegan a CloudWatch (Container
Insights / Fluent Bit), no hace falta hablar con Kubernetes: basta con configurar ese log group y
`logs tail` / `logs search` ya funcionan, con histórico incluido (`kubectl logs` solo ve lo que guarda
el pod actual).

## Archivos a crear/modificar
- `src/campaigns_cli/settings.py` — `EKS_CLUSTER_NAME`, `EKS_NAMESPACE`, `CAMPAIGNS_POD_SELECTOR`
- `src/campaigns_cli/aws.py` — cliente `eks`
- `src/campaigns_cli/services/k8s_service.py` — `eks_token(session, cluster)`, `ClusterAccess` (endpoint + CA de `describe_cluster`), `PodsService` (`list_pods`, `logs`, `follow`)
- `src/campaigns_cli/commands/pods_cmd.py` — subgrupo `pods`
- `src/campaigns_cli/main.py` — registrar `pods`
- `src/campaigns_cli/services/config_service.py` — fila "EKS" en `config check`
- `pyproject.toml`, `uv.lock` — `boto3-stubs[eks]` en dev
- `src/campaigns_cli/http.py` — `HttpClients.kubernetes` (cliente con la CA del clúster)
- `.env.example`
- `tests/k8s_fixtures.py`, `tests/test_k8s_service.py`, `tests/test_pods_cmd.py`, `tests/test_config_check.py`, `tests/test_settings.py`
- `docs/adr/0009-acceso-a-kubernetes.md`, `docs/adr/README.md`
- `docs/comandos.md`, `docs/configuracion.md`, `docs/recursos-aws.md`, `docs/arquitectura.md`, `docs/README.md`, `README.md`

## Tareas
- [x] **Paso previo:** buscar log groups de los contenedores del clúster (`campaigns logs groups --prefix /aws/containerinsights/eks-informacion-dev` y `--prefix /aws/eks/eks-informacion-dev`).
  - Si los logs de `platform-campaigns-others-v2` llegan a CloudWatch: documentar el log group en `.env.example` y `docs/configuracion.md`, registrarlo en el ADR-0009 y limitar esta tarjeta a eso (las tareas siguientes se marcan como no necesarias en `## Notas`).
  - Si no: seguir con las tareas siguientes.
- [x] Escribir ADR en `docs/adr/` (0009): acceso directo a la API de Kubernetes con token de EKS generado con boto3 y `httpx`, en lugar de invocar `kubectl`/`aws` ni usar la librería `kubernetes`.
- [x] Settings nuevas, opcionales en conjunto (como las del fake channel): `EKS_CLUSTER_NAME` (ej. `eks-informacion-{env}`), `EKS_NAMESPACE` (ej. `artemis-{env}`), `CAMPAIGNS_POD_SELECTOR` (por defecto `app=platform-campaigns-others-v2`).
- [x] `eks_token`: URL prefirmada de `sts:GetCallerIdentity` con el header `x-k8s-aws-id: <cluster>` (expira en 60 s), codificada en base64url sin `=` y con prefijo `k8s-aws-v1.`. Lo mismo que `aws eks get-token`.
- [x] `ClusterAccess`: `eks.describe_cluster` → `endpoint` y `certificateAuthority.data`; cliente `httpx` que verifica con esa CA (`ssl.create_default_context(cadata=...)`).
- [x] `PodsService.list_pods(selector)`: `GET /api/v1/namespaces/{ns}/pods?labelSelector=...` → nombre, estado, reinicios, edad, nodo.
- [x] `PodsService.logs(pod, tail, since, timestamps)`: `GET .../pods/{pod}/log?tailLines=&sinceSeconds=&timestamps=true`.
- [x] `follow`: `follow=true` por pod, un hilo por pod (máximo `--max-pods 5`, como `kubectl`), líneas con prefijo `[pod]`, hasta Ctrl+C; renueva el token si la conexión se corta al vencer.
- [x] Comandos:
  - `campaigns pods ls [-l SELECTOR]`
  - `campaigns pods logs [-l SELECTOR] [--pod NOMBRE] [--tail 1000] [--since 1h] [--filter TEXTO] [-f] [--max-pods 5]`
  - `--output json` en `logs` (sin `-f`): lista de `{pod, hora, mensaje}`.
- [x] Errores: 401/403 de la API → mensaje que indica que la identidad del `.env` no tiene acceso al clúster o al namespace (exit 3); clúster inexistente → exit 3; ningún pod con el selector → exit 1.
- [x] `config check`: fila "EKS" (`OK` si `describe_cluster` responde y se pueden listar pods; `OPCIONAL` sin configurar; `SIN PERMISO` en 401/403).
- [x] Documentar el grupo, las variables, los permisos (`eks:DescribeCluster` + acceso RBAC a `pods` y `pods/log` en el namespace) y el estado en `docs/`.

## Criterios de aceptación
- [x] El token generado empieza por `k8s-aws-v1.` y, decodificado, es una URL de STS `GetCallerIdentity` firmada con `x-k8s-aws-id` en `X-Amz-SignedHeaders` y `X-Amz-Expires=60`.
- [x] `pods ls` lista los pods del selector con el token como `Authorization: Bearer`, contra el endpoint y la CA de `describe_cluster`.
- [x] `pods logs --tail 1000` pide `tailLines=1000` a cada pod y muestra las líneas con el nombre del pod; `--filter` deja solo las que contienen el texto.
- [x] `pods logs -f` con dos pods mezcla las líneas de ambos con su prefijo y termina limpio con Ctrl+C.
- [x] 403 de la API → exit 3 con mensaje claro; sin pods → exit 1.
- [x] No modifica `~/.kube/config` ni necesita `kubectl` o `aws` instalados.
- [x] Ninguna prueba hace llamadas reales a AWS ni a Kubernetes (Stubber para EKS, `httpx.MockTransport` para la API).

## Verificación
```bash
uv run pytest tests/test_k8s_service.py tests/test_pods_cmd.py tests/test_config_check.py -q
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run campaigns pods --help
test -f docs/adr/0009-acceso-a-kubernetes.md
# en dev (solo lectura; requiere EKS_* en el .env)
uv run campaigns pods ls
uv run campaigns pods logs --tail 50
```

## Notas
- Los comandos de dev se corren cuando haya credenciales; lo que falle allí se registra como bug con `affects: [T-017]`.
- Depende de [[T-015-fake-channel-messages|T-015]] porque reutiliza `httpx` y el patrón de `HttpClients` (ADR-0008).
- Solo lectura: permitido en prod, como `logs`.
- **Paso previo (2026-10-13):** Container Insights existe (`/aws/containerinsights/eks-informacion-dev/application` y `.../namespace/artemis-dev`) pero no recibe eventos desde 2024 (último en `artemis-dev`: febrero de 2024). Se siguió con la API de Kubernetes; queda registrado en ADR-0009.
- **Cerrada (2026-10-13):** 248 pruebas en verde (96 % de cobertura), ruff y mypy sin errores. También se probó en dev con `EKS_CLUSTER_NAME=eks-informacion-dev` y `EKS_NAMESPACE=artemis-dev` como variables del proceso: `pods ls`, `pods logs --tail 50`, `pods logs -f` (Ctrl+C limpio) y la fila EKS de `config check` en `OK`. El `.env` local no se modificó: hay que agregarle esas dos variables.
