"""Tablas y datos de prueba con el mismo esquema y formato que escriben ingester_Lambda y su log."""

import json
from typing import Any

import boto3

REGION = "us-east-1"
CAMPAIGNS_TABLE = "scheduled-campaigns-test"
LOGS_TABLE = "scheduled-campaigns-logs-test"
CAMPAIGN_INDEX = "campaign_id-index"

CAMPAIGN_A = "11111111-1111-1111-1111-111111111111"
CAMPAIGN_B = "22222222-2222-2222-2222-222222222222"
CAMPAIGN_C = "33333333-3333-3333-3333-333333333333"

ENV = f"""
AWS_REGION={REGION}
CAMPAIGNS_TABLE_NAME={CAMPAIGNS_TABLE}
CAMPAIGNS_LOGS_TABLE_NAME={LOGS_TABLE}
"""


def create_campaigns_table(with_index: bool = False) -> None:
    attributes = [
        {"AttributeName": "datetime", "AttributeType": "S"},
        {"AttributeName": "notification_id", "AttributeType": "S"},
    ]
    kwargs: dict[str, Any] = {}
    if with_index:
        attributes.append({"AttributeName": "campaign_id", "AttributeType": "S"})
        kwargs["GlobalSecondaryIndexes"] = [
            {
                "IndexName": CAMPAIGN_INDEX,
                "KeySchema": [{"AttributeName": "campaign_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ]
    boto3.client("dynamodb", region_name=REGION).create_table(
        TableName=CAMPAIGNS_TABLE,
        KeySchema=[
            {"AttributeName": "datetime", "KeyType": "HASH"},
            {"AttributeName": "notification_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=attributes,
        BillingMode="PAY_PER_REQUEST",
        **kwargs,
    )


def create_logs_table() -> None:
    boto3.client("dynamodb", region_name=REGION).create_table(
        TableName=LOGS_TABLE,
        KeySchema=[
            {"AttributeName": "app_id", "KeyType": "HASH"},
            {"AttributeName": "datetime", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "app_id", "AttributeType": "S"},
            {"AttributeName": "datetime", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def campaign_item(
    notification_id: str,
    scheduled: str,
    *,
    campaign_id: str = CAMPAIGN_A,
    app_id: str = "others-test",
    user: str = "573232540390",
    retries: str = "0",
) -> dict[str, Any]:
    """Registro igual al que arma CampaignRegistry._add_to_list del ingester (o, con otra
    `datetime` y el mismo `notification_id`, el que agrega platform_campaigns_ms al reprogramar)."""
    return {
        "campaign_id": campaign_id,
        "app_id": app_id,
        "channel": "WhatsApp",
        "user": user,
        "notification_node": "N-03-99-10",
        "retries": retries,
        "context": {"text": "hola"},
        "datetime": scheduled,
        "expiration_date": 1760500000,
        "notification_id": notification_id,
    }


def put_campaigns(items: list[dict[str, Any]]) -> None:
    table = boto3.resource("dynamodb", region_name=REGION).Table(CAMPAIGNS_TABLE)
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)


def seed_campaigns() -> None:
    put_campaigns(
        [
            campaign_item("n-1", "2026-10-13 10:00:00"),
            campaign_item("n-2", "2026-10-13 10:00:00", user="573001112233"),
            campaign_item("n-3", "2026-10-13 15:00:00"),
            campaign_item("n-4", "2026-10-14 08:00:00", campaign_id=CAMPAIGN_B, app_id="otra-app"),
        ]
    )


def log_item(
    app_id: str,
    when: str,
    *,
    status: str = "SUCCESSFUL",
    campaign_id: str = CAMPAIGN_A,
    file_route: str = "campaign.csv",
) -> dict[str, Any]:
    """Registro igual al que arma processor._log_execution del ingester."""
    stats = {"total_processed": 2, "successful": 2, "omitted": 0, "errors": 0}
    payload: dict[str, Any] = {"stats": stats, "status": status}
    if status == "SUCCESSFUL":
        payload["body_result"] = (
            f"[Campaign {campaign_id}]Campaign event received at {when} with file {file_route}"
        )
    else:
        stats.update({"successful": 0, "errors": 2})
        payload["body_result"] = {
            "log_errors": [
                {
                    "app_id": app_id,
                    "campaign_id": campaign_id,
                    "error": "CSV structure validation failed",
                }
            ],
            "field_validation_errors": [],
        }
    return {"app_id": app_id, "datetime": when, "result": json.dumps(payload)}


def put_logs(items: list[dict[str, Any]]) -> None:
    table = boto3.resource("dynamodb", region_name=REGION).Table(LOGS_TABLE)
    for item in items:
        table.put_item(Item=item)


def count_items(table_name: str) -> int:
    client = boto3.client("dynamodb", region_name=REGION)
    total = 0
    kwargs: dict[str, Any] = {"TableName": table_name, "Select": "COUNT"}
    while True:
        response = client.scan(**kwargs)
        total += response["Count"]
        if "LastEvaluatedKey" not in response:
            return total
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]


class FlakyBatchClient:
    """Cliente DynamoDB que, en las primeras `failures` llamadas a batch_write_item, solo procesa
    la primera petición del lote y devuelve el resto como `UnprocessedItems`."""

    def __init__(self, client: Any, failures: int) -> None:
        self._client = client
        self.failures = failures
        self.batch_calls = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def batch_write_item(self, **kwargs: Any) -> Any:
        self.batch_calls += 1
        if not self.failures:
            return self._client.batch_write_item(**kwargs)
        self.failures -= 1
        table, requests = next(iter(kwargs["RequestItems"].items()))
        self._client.batch_write_item(RequestItems={table: requests[:1]})
        return {"UnprocessedItems": {table: requests[1:]} if requests[1:] else {}}


def seed_history() -> None:
    """Dos CSV y sus cargas: el de CAMPAIGN_A con reprogramaciones y una carga UNKNOWN, y el de
    CAMPAIGN_B (otra app), cuya carga falló.

    n-1 se reprogramó dos veces: fuera de horario (retries igual) y por reintento (retries + 1).
    """
    put_campaigns(
        [
            campaign_item("n-1", "2026-10-13 10:00:00"),
            campaign_item("n-1", "2026-10-13 18:00:00"),
            campaign_item("n-1", "2026-10-14 09:00:00", retries="1"),
            campaign_item("n-2", "2026-10-13 10:00:00", user="573001112233"),
            campaign_item("n-4", "2026-10-14 08:00:00", campaign_id=CAMPAIGN_B, app_id="otra-app"),
        ]
    )
    put_logs(
        [
            log_item("others-test", "2026-10-13 14:00:00.100000", file_route="a.csv"),
            log_item("UNKNOWN", "2026-10-13 14:05:00.000000", status="FAILED"),
            log_item(
                "otra-app", "2026-10-13 15:00:00.300000", status="FAILED", campaign_id=CAMPAIGN_B
            ),
        ]
    )


class CallCounter:
    """Cliente DynamoDB que cuenta las llamadas por operación y puede ejecutar algo después de
    cada batch_write_item (para simular escrituras concurrentes)."""

    def __init__(self, client: Any, after_batch: Any = None) -> None:
        self._client = client
        self.after_batch = after_batch
        self.calls: dict[str, int] = {}

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._client, name)
        if not callable(attribute):
            return attribute

        def counted(**kwargs: Any) -> Any:
            self.calls[name] = self.calls.get(name, 0) + 1
            response = attribute(**kwargs)
            if name == "batch_write_item" and self.after_batch is not None:
                self.after_batch()
                self.after_batch = None
            return response

        return counted
