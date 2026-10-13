"""EKS y API de Kubernetes falsos (sin red): `FakeEks` para boto3 y `FakeCluster` sobre httpx."""

import base64
from pathlib import Path
from typing import Any

import certifi
import httpx
from botocore.exceptions import ClientError

CLUSTER = "eks-informacion-dev"
NAMESPACE = "artemis-dev"
SELECTOR = "app=platform-campaigns-others-v2"
ENDPOINT = "https://k8s.test"
APP = "platform-campaigns-others-v2"

EKS_ENV = f"""
AWS_REGION=us-east-1
EKS_CLUSTER_NAME={CLUSTER}
EKS_NAMESPACE={NAMESPACE}
"""


def _first_certificate() -> str:
    """Un certificado PEM válido (del bundle de certifi) para armar el contexto SSL del clúster."""
    text = Path(certifi.where()).read_text(encoding="utf-8")
    end = "-----END CERTIFICATE-----"
    start = text.index("-----BEGIN CERTIFICATE-----")
    return text[start : text.index(end, start) + len(end)] + "\n"


CA_PEM = _first_certificate()


class FakeEks:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def describe_cluster(self, name: str) -> dict[str, Any]:
        self.calls.append(name)
        if name != CLUSTER:
            raise ClientError(
                {"Error": {"Code": "ResourceNotFoundException", "Message": f"No cluster {name}"}},
                "DescribeCluster",
            )
        return {
            "cluster": {
                "name": name,
                "status": "ACTIVE",
                "endpoint": ENDPOINT,
                "certificateAuthority": {"data": base64.b64encode(CA_PEM.encode()).decode()},
            }
        }


def pod(
    name: str,
    *,
    phase: str = "Running",
    app: str = APP,
    containers: tuple[str, ...] = (APP, "istio-proxy"),
    default: str | None = None,
    restarts: int = 0,
) -> dict[str, Any]:
    annotations = {"kubectl.kubernetes.io/default-container": default} if default else {}
    return {
        "metadata": {
            "name": name,
            "labels": {"app": app},
            "annotations": annotations,
            "creationTimestamp": "2026-10-13T20:15:35Z",
        },
        "spec": {
            "nodeName": "ip-10-104-89-42.ec2.internal",
            "containers": [{"name": c} for c in containers],
        },
        "status": {
            "phase": phase,
            "containerStatuses": [
                {"name": c, "ready": True, "restartCount": restarts} for c in containers
            ],
        },
    }


class FakeCluster:
    """API de Kubernetes mínima: pods, un pod y sus logs.

    `logs[pod]` es una lista de respuestas: cada GET a `/log` consume la siguiente (la última se
    repite). Cada respuesta es una lista de líneas `"<RFC3339Nano> mensaje"`.
    """

    def __init__(self) -> None:
        self.pods: dict[str, dict[str, Any]] = {}
        self.logs: dict[str, list[list[str]]] = {}
        self.status: int | None = None
        self.requests: list[httpx.Request] = []

    def add(self, item: dict[str, Any], *responses: list[str]) -> None:
        name = item["metadata"]["name"]
        self.pods[name] = item
        self.logs[name] = list(responses) or [[]]

    def log_requests(self, name: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path.endswith(f"/pods/{name}/log")]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status is not None:
            return httpx.Response(
                self.status, json={"kind": "Status", "message": "pods is forbidden: user test"}
            )
        prefix = f"/api/v1/namespaces/{NAMESPACE}/pods"
        path = request.url.path
        if path == prefix:
            key, _, value = request.url.params.get("labelSelector", "").partition("=")
            items = [p for p in self.pods.values() if p["metadata"]["labels"].get(key) == value]
            return httpx.Response(200, json={"kind": "PodList", "items": items})
        name, _, rest = path.removeprefix(prefix + "/").partition("/")
        if name not in self.pods:
            return httpx.Response(
                404, json={"kind": "Status", "message": f'pods "{name}" not found'}
            )
        if rest == "log":
            responses = self.logs[name]
            index = min(len(self.log_requests(name)), len(responses)) - 1
            body = "".join(line + "\n" for line in responses[index])
            return httpx.Response(200, text=body)
        return httpx.Response(200, json=self.pods[name])

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def client(self) -> httpx.Client:
        return httpx.Client(base_url=ENDPOINT, transport=self.transport())
