"""Logs de los pods de un clúster EKS por la API de Kubernetes, sin `kubectl` ni `aws` instalados.

Equivale a:
    aws eks update-kubeconfig --name <EKS_CLUSTER_NAME>
    kubectl logs -n <EKS_NAMESPACE> -l <CAMPAIGNS_POD_SELECTOR> --tail N [-f]

- Endpoint y CA del clúster: `eks:DescribeCluster`.
- Token: el mismo que `aws eks get-token`: URL prefirmada de `sts:GetCallerIdentity` con el header
  `x-k8s-aws-id: <cluster>`, en base64url y con prefijo `k8s-aws-v1.`.
- Contenedor por defecto: la anotación `kubectl.kubernetes.io/default-container` (la pone istio) o
  el primero del pod, como hace `kubectl`.
- Las horas se devuelven en hora Colombia, sin zona.
"""

from __future__ import annotations

import base64
import queue
import re
import threading
import time
from collections.abc import Callable, Generator, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx

from campaigns_cli.errors import CliError, ExternalServiceError, ServiceAuthError
from campaigns_cli.timeutils import COLOMBIA_TZ

if TYPE_CHECKING:
    from mypy_boto3_eks import EKSClient
    from mypy_boto3_sts import STSClient

    from campaigns_cli.aws import AwsClients
    from campaigns_cli.http import HttpClients
    from campaigns_cli.settings import Settings

TOKEN_PREFIX = "k8s-aws-v1."
CLUSTER_HEADER = "x-k8s-aws-id"
TOKEN_PRESIGN_SECONDS = 60
# EKS acepta el token unos 15 minutos; se renueva antes.
TOKEN_REUSE_SECONDS = 600
DEFAULT_CONTAINER_ANNOTATION = "kubectl.kubernetes.io/default-container"
FINISHED_PHASES = frozenset({"Succeeded", "Failed"})
RECONNECT_DELAY_SECONDS = 2.0
REQUIRED_SETTINGS = ("eks_cluster_name", "eks_namespace")

_LOG_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z$")


# --- Autenticación ---


def eks_token(sts: STSClient, cluster: str) -> str:
    """Token para la API de Kubernetes de un clúster EKS (lo mismo que `aws eks get-token`)."""

    def add_cluster_header(request: Any, **_: Any) -> None:
        request.headers[CLUSTER_HEADER] = cluster

    sts.meta.events.register(
        "before-sign.sts.GetCallerIdentity",
        add_cluster_header,
        unique_id=f"campaigns-cli-k8s-aws-id-{cluster}",
    )
    url = sts.generate_presigned_url(
        "get_caller_identity", Params={}, ExpiresIn=TOKEN_PRESIGN_SECONDS, HttpMethod="GET"
    )
    return TOKEN_PREFIX + base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")


class EksTokenAuth(httpx.Auth):
    """Agrega `Authorization: Bearer <token>` y renueva el token antes de que venza."""

    def __init__(
        self, generate: Callable[[], str], *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.generate = generate
        self.clock = clock
        self._token: str | None = None
        self._created = 0.0
        self._lock = threading.Lock()

    def token(self) -> str:
        with self._lock:
            if self._token is None or self.clock() - self._created >= TOKEN_REUSE_SECONDS:
                self._token = self.generate()
                self._created = self.clock()
            return self._token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self.token()}"
        yield request


@dataclass(frozen=True)
class ClusterInfo:
    name: str
    endpoint: str
    ca_pem: str


def describe_cluster(eks: EKSClient, name: str) -> ClusterInfo:
    cluster = eks.describe_cluster(name=name)["cluster"]
    endpoint = cluster.get("endpoint")
    ca_data = cluster.get("certificateAuthority", {}).get("data")
    if not endpoint or not ca_data:
        raise ExternalServiceError(
            f"El clúster {name} no expone endpoint o certificado (estado: "
            f"{cluster.get('status', '?')})."
        )
    return ClusterInfo(name, endpoint, base64.b64decode(ca_data).decode())


# --- Modelos ---


def _to_colombia(value: datetime) -> datetime:
    return value.astimezone(COLOMBIA_TZ).replace(tzinfo=None)


def _parse_k8s_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return _to_colombia(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


@dataclass(frozen=True)
class Pod:
    name: str
    phase: str
    ready: str
    restarts: int
    created: datetime | None
    node: str
    containers: tuple[str, ...]
    default_container: str | None

    @property
    def finished(self) -> bool:
        return self.phase in FINISHED_PHASES

    def as_dict(self) -> dict[str, Any]:
        return {
            "pod": self.name,
            "estado": self.phase,
            "listos": self.ready,
            "reinicios": self.restarts,
            "creado": self.created.isoformat(sep=" ") if self.created else None,
            "nodo": self.node,
            "contenedores": list(self.containers),
        }


def parse_pod(item: Any) -> Pod:
    data: dict[str, Any] = item if isinstance(item, dict) else {}
    metadata = data.get("metadata") or {}
    spec = data.get("spec") or {}
    status = data.get("status") or {}
    containers = tuple(str(c.get("name", "")) for c in spec.get("containers") or [])
    statuses = status.get("containerStatuses") or []
    annotations = metadata.get("annotations") or {}
    default = annotations.get(DEFAULT_CONTAINER_ANNOTATION)
    if default not in containers:
        default = containers[0] if containers else None
    return Pod(
        name=str(metadata.get("name", "")),
        phase=str(status.get("phase", "?")),
        ready=f"{sum(1 for s in statuses if s.get('ready'))}/{len(containers)}",
        restarts=sum(int(s.get("restartCount", 0)) for s in statuses),
        created=_parse_k8s_time(metadata.get("creationTimestamp")),
        node=str(spec.get("nodeName", "")),
        containers=containers,
        default_container=default,
    )


@dataclass(frozen=True)
class PodLogLine:
    pod: str
    timestamp: datetime | None
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "pod": self.pod,
            "hora": self.timestamp.isoformat(sep=" ", timespec="milliseconds")
            if self.timestamp
            else None,
            "mensaje": self.message,
        }


def parse_log_line(pod: str, line: str) -> PodLogLine:
    """`2026-10-13T15:04:05.123456789Z mensaje` (con `timestamps=true`) → línea en hora Colombia."""
    raw, _, message = line.partition(" ")
    match = _LOG_TIMESTAMP.match(raw)
    if not match:
        return PodLogLine(pod, None, line)
    fraction = (match.group(2) or "0")[:6].ljust(6, "0")
    parsed = datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S").replace(
        microsecond=int(fraction), tzinfo=UTC
    )
    return PodLogLine(pod, _to_colombia(parsed), message)


@dataclass(frozen=True)
class StreamEnd:
    """Fin del seguimiento de un pod (terminó, se borró o falló la conexión)."""

    pod: str
    reason: str


# --- Servicio ---


@dataclass
class _Cursor:
    """Última línea entregada: al reconectar se pide desde ahí y se descartan las repetidas."""

    last: datetime | None = None
    seen: set[str] = field(default_factory=set)

    def is_new(self, line: PodLogLine) -> bool:
        if self.last is None or line.timestamp is None or line.timestamp > self.last:
            return True
        return line.timestamp == self.last and line.message not in self.seen

    def advance(self, line: PodLogLine) -> None:
        if line.timestamp is None:
            return
        if self.last is None or line.timestamp > self.last:
            self.last = line.timestamp
            self.seen = set()
        self.seen.add(line.message)


class PodsService:
    def __init__(
        self,
        client: httpx.Client,
        namespace: str,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.namespace = namespace
        self.sleep = sleep

    def _pods_path(self) -> str:
        return f"/api/v1/namespaces/{self.namespace}/pods"

    def _check(self, response: httpx.Response, action: str) -> None:
        status = response.status_code
        if status == 200:
            return
        detail = _api_message(response)
        if status in (401, 403):
            raise ServiceAuthError(
                f"La API de Kubernetes rechazó la identidad del .env (HTTP {status}) al {action}. "
                f"Necesita acceso al clúster y permisos sobre pods y pods/log en el namespace "
                f"{self.namespace}. {detail}".strip()
            )
        if status == 404:
            raise ExternalServiceError(f"No existe el recurso al {action}. {detail}".strip())
        raise ExternalServiceError(
            f"La API de Kubernetes respondió HTTP {status} al {action}. {detail}".strip()
        )

    def list_pods(self, selector: str) -> list[Pod]:
        response = self.client.get(self._pods_path(), params={"labelSelector": selector})
        self._check(response, f"listar los pods con {selector}")
        items = response.json().get("items") or []
        return sorted((parse_pod(item) for item in items), key=lambda pod: pod.name)

    def get_pod(self, name: str) -> Pod:
        response = self.client.get(f"{self._pods_path()}/{name}")
        self._check(response, f"leer el pod {name}")
        return parse_pod(response.json())

    def _log_params(
        self, pod: Pod, container: str | None, tail: int | None, since_seconds: int | None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"timestamps": "true"}
        chosen = container or pod.default_container
        if chosen:
            params["container"] = chosen
        if tail is not None:
            params["tailLines"] = tail
        if since_seconds is not None:
            params["sinceSeconds"] = since_seconds
        return params

    def logs(
        self,
        pod: Pod,
        *,
        container: str | None = None,
        tail: int | None = None,
        since_seconds: int | None = None,
    ) -> list[PodLogLine]:
        response = self.client.get(
            f"{self._pods_path()}/{pod.name}/log",
            params=self._log_params(pod, container, tail, since_seconds),
        )
        self._check(response, f"leer los logs de {pod.name}")
        return [parse_log_line(pod.name, line) for line in response.text.splitlines() if line]

    def stream(
        self,
        pod: Pod,
        stop: threading.Event,
        *,
        container: str | None = None,
        tail: int | None = None,
        since_seconds: int | None = None,
    ) -> Iterator[PodLogLine]:
        """Sigue los logs de un pod; si la conexión se corta, reconecta desde la última línea."""
        params = {**self._log_params(pod, container, tail, since_seconds), "follow": "true"}
        cursor = _Cursor()
        path = f"{self._pods_path()}/{pod.name}/log"
        while not stop.is_set():
            try:
                with self.client.stream(
                    "GET", path, params=params, timeout=httpx.Timeout(30.0, read=None)
                ) as response:
                    if response.status_code != 200:
                        response.read()
                        self._check(response, f"seguir los logs de {pod.name}")
                    for raw in response.iter_lines():
                        if stop.is_set():
                            return
                        if not raw:
                            continue
                        line = parse_log_line(pod.name, raw)
                        if cursor.is_new(line):
                            cursor.advance(line)
                            yield line
            except (httpx.ReadError, httpx.RemoteProtocolError, httpx.ReadTimeout):
                pass
            if stop.is_set() or self.get_pod(pod.name).finished:
                return
            self.sleep(RECONNECT_DELAY_SECONDS)
            params = {k: v for k, v in params.items() if k not in ("tailLines", "sinceSeconds")}
            if cursor.last is not None:
                since = cursor.last.replace(tzinfo=COLOMBIA_TZ).astimezone(UTC)
                params["sinceTime"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    def follow_many(
        self,
        pods: Sequence[Pod],
        stop: threading.Event,
        *,
        container: str | None = None,
        tail: int | None = None,
        since_seconds: int | None = None,
    ) -> Iterator[PodLogLine | StreamEnd]:
        """Sigue varios pods a la vez (un hilo por pod) y entrega las líneas según llegan."""
        items: queue.Queue[PodLogLine | StreamEnd] = queue.Queue()

        def worker(pod: Pod) -> None:
            reason = "el pod terminó"
            try:
                for line in self.stream(
                    pod, stop, container=container, tail=tail, since_seconds=since_seconds
                ):
                    items.put(line)
            except (CliError, httpx.HTTPError) as exc:
                reason = str(exc)
            finally:
                items.put(StreamEnd(pod.name, "detenido" if stop.is_set() else reason))

        for pod in pods:
            threading.Thread(target=worker, args=(pod,), daemon=True).start()
        remaining = len(pods)
        while remaining:
            try:
                item = items.get(timeout=0.5)
            except queue.Empty:
                continue
            if isinstance(item, StreamEnd):
                remaining -= 1
            yield item


def _api_message(response: httpx.Response) -> str:
    """Mensaje de un `Status` de Kubernetes, si la respuesta lo trae."""
    try:
        payload = response.json()
    except ValueError:
        return ""
    return str(payload.get("message", "")) if isinstance(payload, dict) else ""


def pods_service_from(settings: Settings, aws: AwsClients, http: HttpClients) -> PodsService:
    """Arma el cliente del clúster; exige EKS_CLUSTER_NAME y EKS_NAMESPACE."""
    settings.require(*REQUIRED_SETTINGS)
    name = str(settings.eks_cluster_name)
    cluster = describe_cluster(aws.eks, name)
    region = settings.aws_region
    sts = aws.session.client(
        "sts", region_name=region, endpoint_url=f"https://sts.{region}.amazonaws.com"
    )
    auth = EksTokenAuth(lambda: eks_token(sts, name))
    client = http.kubernetes(cluster.endpoint, cluster.ca_pem, auth)
    return PodsService(client, str(settings.eks_namespace))
