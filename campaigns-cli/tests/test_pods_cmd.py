import json

import pytest
from typer.testing import CliRunner

from campaigns_cli.aws import AwsClients
from campaigns_cli.http import HttpClients
from campaigns_cli.main import app
from campaigns_cli.state import AppState
from tests.k8s_fixtures import CLUSTER, EKS_ENV, ENGINE, NAMESPACE, FakeCluster, FakeEks, pod

runner = CliRunner(env={"COLUMNS": "250"})


@pytest.fixture
def cluster(write_env, aws_credentials: None, monkeypatch: pytest.MonkeyPatch) -> FakeCluster:  # type: ignore[no-untyped-def]
    """`.env` con EKS configurado, EKS falso y la API de Kubernetes sobre un transporte falso."""
    write_env(EKS_ENV)
    fake = FakeCluster()
    eks = FakeEks()
    monkeypatch.setattr(AwsClients, "eks", property(lambda self: eks))

    def http(self: AppState) -> HttpClients:
        if self._http is None:
            self._http = HttpClients(self.settings, transport=fake.transport())
        return self._http

    monkeypatch.setattr(AppState, "http", property(http))
    return fake


def test_ls_table(cluster: FakeCluster) -> None:
    cluster.add(pod("platform-campaigns-others-v2-abc"))

    result = runner.invoke(app, ["pods", "ls"])

    assert result.exit_code == 0, result.output
    assert "platform-campaigns-others-v2-abc" in result.stdout
    assert "Running" in result.stdout
    assert cluster.requests[0].headers["authorization"].startswith("Bearer k8s-aws-v1.")


def test_ls_json_custom_selector(cluster: FakeCluster) -> None:
    cluster.add(pod("otro-1", app="otro"))

    result = runner.invoke(app, ["--output", "json", "pods", "ls", "-l", "app=otro"])

    assert [p["pod"] for p in json.loads(result.stdout)] == ["otro-1"]


def test_logs_merges_pods_in_time_order(cluster: FakeCluster) -> None:
    cluster.add(pod("p-1"), ["2026-10-13T20:00:02Z segundo", "2026-10-13T20:00:04Z cuarto"])
    cluster.add(pod("p-2"), ["2026-10-13T20:00:01Z primero", "2026-10-13T20:00:03Z tercero"])

    result = runner.invoke(app, ["pods", "logs", "--tail", "50"])

    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert [line.split()[-1] for line in lines] == ["primero", "segundo", "tercero", "cuarto"]
    assert lines[0].startswith("[campaigns] p-2 2026-10-13 15:00:01")
    assert "4 línea(s) de 2 pod(s)" in result.stderr
    assert cluster.log_requests("p-1")[0].url.params["tailLines"] == "50"


def test_logs_filter_and_json(cluster: FakeCluster) -> None:
    cluster.add(
        pod("p-1"), ["2026-10-13T20:00:01Z notification n-123", "2026-10-13T20:00:02Z otra"]
    )

    result = runner.invoke(
        app, ["--output", "json", "pods", "logs", "--filter", "n-123", "--since", "1h"]
    )

    rows = json.loads(result.stdout)
    assert rows == [
        {
            "componente": "campaigns",
            "pod": "p-1",
            "hora": "2026-10-13 15:00:01.000",
            "mensaje": "notification n-123",
        }
    ]
    assert cluster.log_requests("p-1")[0].url.params["sinceSeconds"] == "3600"


def test_logs_single_pod(cluster: FakeCluster) -> None:
    cluster.add(pod("p-1"), ["2026-10-13T20:00:01Z uno"])
    cluster.add(pod("p-2"), ["2026-10-13T20:00:01Z dos"])

    result = runner.invoke(app, ["pods", "logs", "--pod", "p-2"])

    assert "dos" in result.stdout
    assert cluster.log_requests("p-1") == []


def test_logs_without_pods_exit_1(cluster: FakeCluster) -> None:
    result = runner.invoke(app, ["pods", "logs"])

    assert result.exit_code == 1
    assert f"No hay pods de campaigns en el namespace {NAMESPACE}" in result.stderr


def test_follow_prints_lines_until_pods_finish(cluster: FakeCluster) -> None:
    cluster.add(pod("p-1", phase="Succeeded"), ["2026-10-13T20:00:01Z uno"])

    result = runner.invoke(app, ["pods", "logs", "-f"])

    assert result.exit_code == 0, result.output
    assert "uno" in result.stdout
    assert "Siguiendo 1 pod(s): p-1" in result.stderr
    assert "p-1: el pod terminó" in result.stderr
    assert cluster.log_requests("p-1")[0].url.params["follow"] == "true"


def test_follow_json_one_object_per_line(cluster: FakeCluster) -> None:
    cluster.add(
        pod("p-1", phase="Succeeded"), ["2026-10-13T20:00:01Z uno", "2026-10-13T20:00:02Z dos"]
    )

    result = runner.invoke(app, ["--output", "json", "pods", "logs", "-f"])

    assert [json.loads(line)["mensaje"] for line in result.stdout.splitlines()] == ["uno", "dos"]


def test_follow_too_many_pods(cluster: FakeCluster) -> None:
    for index in range(3):
        cluster.add(pod(f"p-{index}"))

    result = runner.invoke(app, ["pods", "logs", "-f", "--max-pods", "2"])

    assert result.exit_code == 2
    assert "Hay 3 pods y --max-pods es 2" in result.stderr


def test_forbidden_exit_3(cluster: FakeCluster) -> None:
    cluster.status = 403

    result = runner.invoke(app, ["pods", "ls"])

    assert result.exit_code == 3
    assert "rechazó la identidad del .env (HTTP 403)" in result.stderr


def test_unknown_cluster_exit_3(cluster: FakeCluster, write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(EKS_ENV.replace(CLUSTER, "eks-inexistente"))

    result = runner.invoke(app, ["pods", "ls"])

    assert result.exit_code == 3
    assert "DescribeCluster" in result.stderr


def test_missing_config_exit_2(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("EKS_CLUSTER_NAME=eks-informacion-dev\n")

    result = runner.invoke(app, ["pods", "ls"])

    assert result.exit_code == 2
    assert "EKS_NAMESPACE" in result.stderr


# --- T-018: componentes y notification_id ---

NID = "213bc663-cad7-48bb-a39f-a1719b547303"


def _engine_and_campaigns(cluster: FakeCluster) -> None:
    cluster.add(
        pod("cms-1"),
        [
            "2026-10-13T21:00:00Z Message sent correlationId=" + NID,
            "2026-10-13T21:00:01Z otra notificación",
        ],
    )
    cluster.add(
        pod("eng-1", app=ENGINE, containers=(ENGINE, "istio-proxy")),
        [
            "2026-10-13T21:00:05Z Message null Headers: {x-consumer-id=}",
            '2026-10-13T21:00:05Z Message null Body: {"data":{"notification_id":"' + NID + '"}}',
            "2026-10-13T21:00:05Z ATTENTION!! Sending message to Retry DLQ: null",
            "2026-10-13T21:00:09Z sin relación",
        ],
    )


def test_ls_all_components(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(app, ["--output", "json", "pods", "ls", "--component", "all"])

    rows = json.loads(result.stdout)
    assert [(r["componente"], r["pod"]) for r in rows] == [
        ("campaigns", "cms-1"),
        ("engine", "eng-1"),
    ]


def test_logs_engine_component(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(app, ["pods", "logs", "-k", "engine"])

    assert result.exit_code == 0, result.output
    assert cluster.log_requests("cms-1") == []
    assert cluster.log_requests("eng-1")[0].url.params["container"] == ENGINE
    assert result.stdout.splitlines()[0].startswith("[engine] eng-1")


def test_notification_id_searches_both_components(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(app, ["pods", "logs", "--notification-id", NID])

    assert result.exit_code == 0, result.output
    assert len(result.stdout.splitlines()) == 2
    for name in ("cms-1", "eng-1"):
        params = cluster.log_requests(name)[0].url.params
        assert params["sinceSeconds"] == "86400"
        assert "tailLines" not in params
    assert "campaigns: 1 coincidencia(s) en 1 pod(s), de 16:00:00 a 16:00:00." in result.stderr
    assert "engine: 1 coincidencia(s) en 1 pod(s), de 16:00:05 a 16:00:05." in result.stderr


def test_notification_id_json_summary(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(
        app, ["--output", "json", "pods", "logs", "--notification-id", NID, "--since", "2h"]
    )

    report = json.loads(result.stdout)
    assert [line["componente"] for line in report["lineas"]] == ["campaigns", "engine"]
    assert report["resumen"] == [
        {
            "componente": "campaigns",
            "pods": 1,
            "coincidencias": 1,
            "primera": "2026-10-13 16:00:00.000",
            "ultima": "2026-10-13 16:00:00.000",
        },
        {
            "componente": "engine",
            "pods": 1,
            "coincidencias": 1,
            "primera": "2026-10-13 16:00:05.000",
            "ultima": "2026-10-13 16:00:05.000",
        },
    ]
    assert cluster.log_requests("eng-1")[0].url.params["sinceSeconds"] == "7200"


def test_notification_id_only_in_one_component(cluster: FakeCluster) -> None:
    cluster.add(pod("cms-1"), [f"2026-10-13T21:00:00Z id {NID}"])
    cluster.add(pod("eng-1", app=ENGINE), ["2026-10-13T21:00:05Z nada"])

    result = runner.invoke(app, ["pods", "logs", "--notification-id", NID])

    assert result.exit_code == 0
    assert "engine: sin coincidencias (1 pod(s) revisados)." in result.stderr


def test_notification_id_not_found_exit_1(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(app, ["pods", "logs", "--notification-id", "no-existe-123"])

    assert result.exit_code == 1
    assert "no aparece en los logs de campaigns, engine" in result.stderr


def test_notification_id_restricted_to_component(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(app, ["pods", "logs", "--notification-id", NID, "-k", "engine"])

    assert result.exit_code == 0
    assert cluster.log_requests("cms-1") == []
    assert "campaigns:" not in result.stderr


def test_context_shows_neighbour_lines(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(
        app,
        ["--output", "json", "pods", "logs", "--notification-id", NID, "-k", "engine", "-C", "1"],
    )

    lines = json.loads(result.stdout)["lineas"]
    assert [(line["mensaje"][:20], line["coincide"]) for line in lines] == [
        ("Message null Headers", False),
        ("Message null Body: {", True),
        ("ATTENTION!! Sending ", False),
    ]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--notification-id", "abc"], "al menos 6 caracteres"),
        (["--notification-id", NID, "--filter", "x"], "no ambos"),
        (["--context", "2"], "--context requiere"),
        (["--filter", "algo", "--context", "2", "-f"], "--context no admite --follow"),
    ],
)
def test_usage_errors(cluster: FakeCluster, args: list[str], message: str) -> None:
    result = runner.invoke(app, ["pods", "logs", *args])

    assert result.exit_code == 2
    assert message in result.stderr
    assert cluster.requests == []


# --- pods scan: un bloque por componente ---


def test_scan_campaigns_then_engine(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(app, ["pods", "scan", NID])

    assert result.exit_code == 0, result.output
    assert [line.split()[0] for line in result.stdout.splitlines()] == ["[campaigns]", "[engine]"]
    assert cluster.log_requests("cms-1")[0].url.params["sinceSeconds"] == "86400"
    campaigns = result.stderr.index("campaigns: 1 coincidencia(s)")
    assert campaigns < result.stderr.index("engine (1 pod(s))")
    assert campaigns < result.stderr.index("engine: 1 coincidencia(s)")


def test_scan_order_follows_component_option(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(
        app, ["--output", "json", "pods", "scan", NID, "-k", "engine", "-k", "campaigns", "-C", "1"]
    )

    sections = json.loads(result.stdout)
    assert [(s["componente"], s["coincidencias"]) for s in sections] == [
        ("engine", 1),
        ("campaigns", 1),
    ]
    assert [line["coincide"] for line in sections[0]["lineas"]] == [False, True, False]


def test_scan_only_one_component(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(app, ["pods", "scan", NID, "-k", "engine"])

    assert result.exit_code == 0
    assert cluster.log_requests("cms-1") == []


def test_scan_not_found_exit_1(cluster: FakeCluster) -> None:
    _engine_and_campaigns(cluster)

    result = runner.invoke(app, ["pods", "scan", "no-existe-123"])

    assert result.exit_code == 1
    assert "campaigns: sin coincidencias" in result.stderr
    assert "engine: sin coincidencias" in result.stderr


def test_scan_short_id_exit_2(cluster: FakeCluster) -> None:
    result = runner.invoke(app, ["pods", "scan", "abc"])

    assert result.exit_code == 2
    assert cluster.requests == []
