import json

import pytest
from typer.testing import CliRunner

from campaigns_cli.aws import AwsClients
from campaigns_cli.http import HttpClients
from campaigns_cli.main import app
from campaigns_cli.state import AppState
from tests.k8s_fixtures import CLUSTER, EKS_ENV, NAMESPACE, FakeCluster, FakeEks, pod

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
    assert lines[0].startswith("p-2 2026-10-13 15:00:01")
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
        {"pod": "p-1", "hora": "2026-10-13 15:00:01.000", "mensaje": "notification n-123"}
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
    assert (
        f"No hay pods con app=platform-campaigns-others-v2 en el namespace {NAMESPACE}"
        in result.stderr
    )


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
