"""Bucket de entrada de ingester_Lambda (`CAMPAIGNS_INPUT_BUCKET`).

Subir un CSV dispara la ingesta real. El ingester borra el archivo al terminar de procesarlo
(`processor.py` → `DataSourceManagement.delete_data_file`), así que un CSV ya procesado no aparece
en `list`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from campaigns_cli.errors import UsageError
from campaigns_cli.timeutils import COLOMBIA_TZ, colombia_now

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

CSV_CONTENT_TYPE = "text/csv"


def normalize_prefix(prefix: str) -> str:
    """`entrada` → `entrada/`; vacío = raíz del bucket."""
    clean = prefix.strip().lstrip("/")
    return f"{clean.rstrip('/')}/" if clean else ""


@dataclass(frozen=True)
class UploadResult:
    bucket: str
    key: str
    etag: str
    version_id: str | None
    uploaded_at: datetime  # hora Colombia

    def as_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "key": self.key,
            "etag": self.etag,
            "version_id": self.version_id,
            "hora_subida": self.uploaded_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


@dataclass(frozen=True)
class S3Object:
    key: str
    size: int
    last_modified: datetime  # hora Colombia

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "tamano_bytes": self.size,
            "ultima_modificacion": self.last_modified.strftime("%Y-%m-%d %H:%M:%S"),
        }


class S3Service:
    def __init__(
        self,
        client: S3Client,
        bucket: str,
        prefix: str = "",
        *,
        clock: Callable[[], datetime] = colombia_now,
    ) -> None:
        self.client = client
        self.bucket = bucket
        self.prefix = normalize_prefix(prefix)
        self.clock = clock

    def key_for(self, path: Path) -> str:
        """Key por defecto: `CAMPAIGNS_INPUT_PREFIX` + nombre del archivo."""
        return f"{self.prefix}{path.name}"

    def in_prefix(self, key: str) -> bool:
        return key.startswith(self.prefix)

    def upload(self, path: Path, key: str | None = None) -> UploadResult:
        """Sube el archivo con `ContentType=text/csv`. Dispara la ingesta."""
        target = key or self.key_for(path)
        response = self.client.put_object(
            Bucket=self.bucket,
            Key=target,
            Body=path.read_bytes(),
            ContentType=CSV_CONTENT_TYPE,
        )
        return UploadResult(
            bucket=self.bucket,
            key=target,
            etag=str(response.get("ETag", "")).strip('"'),
            version_id=response.get("VersionId"),
            uploaded_at=self.clock(),
        )

    def list(
        self, prefix: str | None = None, limit: int | None = None
    ) -> tuple[list[S3Object], bool]:
        """Objetos bajo el prefijo, del más reciente al más antiguo: (objetos, truncado)."""
        paginator = self.client.get_paginator("list_objects_v2")
        objects: list[S3Object] = []
        for page in paginator.paginate(
            Bucket=self.bucket, Prefix=self.prefix if prefix is None else prefix
        ):
            for item in page.get("Contents", []):
                objects.append(
                    S3Object(
                        key=item["Key"],
                        size=int(item.get("Size", 0)),
                        last_modified=item["LastModified"]
                        .astimezone(COLOMBIA_TZ)
                        .replace(tzinfo=None),
                    )
                )
        objects.sort(key=lambda obj: (obj.last_modified, obj.key), reverse=True)
        if limit is not None and len(objects) > limit:
            return objects[:limit], True
        return objects, False

    def download(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def ensure_deletable(self, key: str) -> None:
        """Solo keys dentro del prefijo; `head_object` falla con 404 si no existe."""
        if not self.in_prefix(key):
            raise UsageError(
                f"La key '{key}' está fuera de CAMPAIGNS_INPUT_PREFIX ('{self.prefix}'): "
                "no se borra."
            )
        self.client.head_object(Bucket=self.bucket, Key=key)

    def delete(self, key: str) -> None:
        self.ensure_deletable(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)
