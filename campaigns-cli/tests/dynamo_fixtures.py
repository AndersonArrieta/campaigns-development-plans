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
) -> dict[str, Any]:
    """Registro igual al que arma CampaignRegistry._add_to_list del ingester."""
    return {
        "campaign_id": campaign_id,
        "app_id": app_id,
        "channel": "WhatsApp",
        "user": user,
        "notification_node": "N-03-99-10",
        "retries": "0",
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
