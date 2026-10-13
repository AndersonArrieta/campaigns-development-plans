---
id: ADR-0009
title: "Logs de los pods por la API de Kubernetes con token de EKS, sin kubectl"
status: accepted
date: 2026-10-13
supersedes:
---

# ADR-0009 — Logs de los pods por la API de Kubernetes con token de EKS, sin kubectl

## Contexto
Los logs de `platform_campaigns_ms` se leen hoy a mano:
`aws eks update-kubeconfig --name eks-informacion-dev`, `kubectl config set-context --namespace=artemis-dev`
y `kubectl logs -f -l app=platform-campaigns-others-v2 --tail 1000`.

Antes de decidir se revisó CloudWatch (2026-10-13). Existen los log groups de Container Insights
del clúster (`/aws/containerinsights/eks-informacion-dev/application` y
`.../namespace/artemis-dev`), pero **dejaron de recibir eventos**: el último de `artemis-dev` es de
febrero de 2024 y el de `application`, de septiembre de 2022. `/aws/eks/eks-informacion-dev/cluster`
solo tiene logs del plano de control. Los logs actuales de los pods solo están en Kubernetes.

## Decisión
- El grupo `pods` habla **directo con la API de Kubernetes** del clúster:
  - endpoint y CA con `eks:DescribeCluster` (boto3);
  - token igual al de `aws eks get-token`: URL prefirmada de `sts:GetCallerIdentity` con el header
    `x-k8s-aws-id: <cluster>`, en base64url con prefijo `k8s-aws-v1.`; se renueva cada 10 minutos;
  - llamadas con `httpx` ([ADR-0008](0008-cliente-http.md)), verificando el certificado con la CA del clúster.
- Descartado: invocar `kubectl`/`aws` como subprocesos (exige tenerlos instalados, modifica
  `~/.kube/config` y el namespace del contexto, y es difícil de probar) y la librería `kubernetes`
  (dependencia pesada para cuatro endpoints).
- Contenedor por defecto como `kubectl`: anotación `kubectl.kubernetes.io/default-container` (la pone
  istio) o el primero del pod.

## Consecuencias
- Usa las mismas credenciales del `.env` que el resto de la CLI. La identidad necesita
  `eks:DescribeCluster` y estar dada de alta en el clúster con permisos RBAC sobre `pods` y `pods/log`.
- Solo ve lo que guarda el pod actual (como `kubectl logs`); no hay histórico tras un reinicio.
  Si Container Insights vuelve a recibir logs, `logs tail/search` sobre ese log group sería la
  alternativa con histórico.
- Origen: [T-017](../../backlog/tasks/T-017-pods-logs-eks.md).
