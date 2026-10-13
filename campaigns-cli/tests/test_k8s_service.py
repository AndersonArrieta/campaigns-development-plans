import base64
import threading
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import boto3
import pytest

from campaigns_cli.errors import ExternalServiceError, ServiceAuthError
from campaigns_cli.services.k8s_service import (
    TOKEN_REUSE_SECONDS,
    EksTokenAuth,
    PodLogLine,
    PodsService,
    StreamEnd,
    describe_cluster,
    eks_token,
    parse_log_line,
    parse_pod,
)
from tests.k8s_fixtures import (
    APP,
    CA_PEM,
    CLUSTER,
    ENDPOINT,
    NAMESPACE,
    SELECTOR,
    FakeCluster,
    FakeEks,
    pod,
)


@pytest.fixture
def cluster() -> FakeCluster:
    return FakeCluster()


def _service(cluster: FakeCluster, sleeps: list[float] | None = None) -> PodsService:
    recorded = sleeps if sleeps is not None else []
    return PodsService(cluster.client(), NAMESPACE, sleep=recorded.append)


# --- token y clúster ---


def test_eks_token_is_presigned_get_caller_identity() -> None:
    session = boto3.Session(
        aws_access_key_id="AKIATEST", aws_secret_access_key="secret", region_name="us-east-1"
    )
    sts = session.client("sts", endpoint_url="https://sts.us-east-1.amazonaws.com")

    token = eks_token(sts, CLUSTER)

    assert token.startswith("k8s-aws-v1.")
    assert "=" not in token
    encoded = token.removeprefix("k8s-aws-v1.")
    url = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "sts.us-east-1.amazonaws.com"
    assert query["Action"] == ["GetCallerIdentity"]
    assert query["X-Amz-Expires"] == ["60"]
    assert "x-k8s-aws-id" in query["X-Amz-SignedHeaders"][0].split(";")
    assert "X-Amz-Signature" in query


def test_token_auth_reuses_and_renews() -> None:
    now = [0.0]
    generated: list[str] = []

    def generate() -> str:
        generated.append(f"t{len(generated)}")
        return generated[-1]

    auth = EksTokenAuth(generate, clock=lambda: now[0])

    assert auth.token() == "t0"
    now[0] = TOKEN_REUSE_SECONDS - 1
    assert auth.token() == "t0"
    now[0] = TOKEN_REUSE_SECONDS
    assert auth.token() == "t1"


def test_describe_cluster() -> None:
    info = describe_cluster(FakeEks(), CLUSTER)  # type: ignore[arg-type]

    assert info.endpoint == ENDPOINT
    assert info.ca_pem == CA_PEM


def test_describe_cluster_without_endpoint() -> None:
    class Creating(FakeEks):
        def describe_cluster(self, name: str) -> dict[str, object]:
            return {"cluster": {"name": name, "status": "CREATING"}}

    with pytest.raises(ExternalServiceError, match="CREATING"):
        describe_cluster(Creating(), CLUSTER)  # type: ignore[arg-type]


# --- modelos ---


def test_parse_pod_uses_default_container_annotation() -> None:
    parsed = parse_pod(pod("p-1", containers=("istio-proxy", APP), default=APP, restarts=2))

    assert parsed.default_container == APP
    assert parsed.ready == "2/2"
    assert parsed.restarts == 4
    assert parsed.created == datetime(2026, 10, 13, 15, 15, 35)
    assert parsed.as_dict()["contenedores"] == ["istio-proxy", APP]


def test_parse_pod_defaults_to_first_container() -> None:
    assert parse_pod(pod("p-1")).default_container == APP


def test_parse_log_line_with_nanoseconds() -> None:
    line = parse_log_line("p-1", "2026-10-13T20:28:02.577123456Z INFO hola mundo")

    assert line == PodLogLine("p-1", datetime(2026, 10, 13, 15, 28, 2, 577123), "INFO hola mundo")
    assert line.as_dict()["hora"] == "2026-10-13 15:28:02.577"


def test_parse_log_line_without_timestamp() -> None:
    assert parse_log_line("p-1", "sin hora") == PodLogLine("p-1", None, "sin hora")


# --- API ---


def test_list_pods_by_selector(cluster: FakeCluster) -> None:
    cluster.add(pod("p-b"))
    cluster.add(pod("p-a"))
    cluster.add(pod("otro", app="otro"))

    pods = _service(cluster).list_pods(SELECTOR)

    assert [p.name for p in pods] == ["p-a", "p-b"]
    assert cluster.requests[0].url.params["labelSelector"] == SELECTOR


def test_logs_request_parameters(cluster: FakeCluster) -> None:
    cluster.add(
        pod("p-1", containers=("istio-proxy", APP), default=APP), ["2026-10-13T20:00:00Z uno"]
    )
    service = _service(cluster)

    lines = service.logs(service.get_pod("p-1"), tail=1000, since_seconds=3600)

    params = cluster.log_requests("p-1")[0].url.params
    assert dict(params) == {
        "timestamps": "true",
        "container": APP,
        "tailLines": "1000",
        "sinceSeconds": "3600",
    }
    assert [line.message for line in lines] == ["uno"]


def test_logs_explicit_container(cluster: FakeCluster) -> None:
    cluster.add(pod("p-1"))
    service = _service(cluster)

    service.logs(service.get_pod("p-1"), container="istio-proxy")

    assert cluster.log_requests("p-1")[0].url.params["container"] == "istio-proxy"


@pytest.mark.parametrize("status", [401, 403])
def test_forbidden(cluster: FakeCluster, status: int) -> None:
    cluster.status = status

    with pytest.raises(ServiceAuthError) as error:
        _service(cluster).list_pods(SELECTOR)

    assert f"HTTP {status}" in str(error.value)
    assert NAMESPACE in str(error.value)
    assert "pods is forbidden" in str(error.value)


def test_missing_pod(cluster: FakeCluster) -> None:
    with pytest.raises(ExternalServiceError, match='pods "nada" not found'):
        _service(cluster).get_pod("nada")


def test_server_error(cluster: FakeCluster) -> None:
    cluster.status = 500

    with pytest.raises(ExternalServiceError, match="HTTP 500"):
        _service(cluster).list_pods(SELECTOR)


# --- seguimiento ---


def test_stream_reconnects_without_duplicates(cluster: FakeCluster) -> None:
    cluster.add(
        pod("p-1"),
        ["2026-10-13T20:00:00.1Z uno", "2026-10-13T20:00:01.5Z dos"],
        ["2026-10-13T20:00:01.5Z dos", "2026-10-13T20:00:02Z tres"],
    )
    sleeps: list[float] = []
    service = _service(cluster, sleeps)
    stop = threading.Event()

    received = []
    for line in service.stream(service.get_pod("p-1"), stop, tail=10):
        received.append(line.message)
        if len(received) == 3:
            stop.set()

    first, second = cluster.log_requests("p-1")[:2]
    assert received == ["uno", "dos", "tres"]
    assert sleeps == [2.0]
    assert first.url.params["follow"] == "true"
    assert first.url.params["tailLines"] == "10"
    assert "tailLines" not in second.url.params
    assert second.url.params["sinceTime"] == "2026-10-13T20:00:01Z"


def test_stream_ends_when_pod_finishes(cluster: FakeCluster) -> None:
    cluster.add(pod("p-1", phase="Succeeded"), ["2026-10-13T20:00:00Z fin"])
    service = _service(cluster)

    lines = list(service.stream(service.get_pod("p-1"), threading.Event()))

    assert [line.message for line in lines] == ["fin"]


def test_follow_many_merges_pods(cluster: FakeCluster) -> None:
    cluster.add(
        pod("p-1", phase="Succeeded"), ["2026-10-13T20:00:00Z a1", "2026-10-13T20:00:01Z a2"]
    )
    cluster.add(pod("p-2", phase="Succeeded"), ["2026-10-13T20:00:00Z b1"])
    service = _service(cluster)
    pods = service.list_pods(SELECTOR)

    items = list(service.follow_many(pods, threading.Event()))

    lines = {(i.pod, i.message) for i in items if isinstance(i, PodLogLine)}
    ends = [i for i in items if isinstance(i, StreamEnd)]
    assert lines == {("p-1", "a1"), ("p-1", "a2"), ("p-2", "b1")}
    assert sorted(end.pod for end in ends) == ["p-1", "p-2"]
    assert {end.reason for end in ends} == {"el pod terminó"}


def test_follow_many_reports_errors(cluster: FakeCluster) -> None:
    cluster.add(pod("p-1"))
    service = _service(cluster)
    pods = service.list_pods(SELECTOR)
    cluster.status = 403

    items = list(service.follow_many(pods, threading.Event()))

    assert len(items) == 1
    assert isinstance(items[0], StreamEnd)
    assert "HTTP 403" in items[0].reason
