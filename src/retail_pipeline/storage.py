"""Raw-layer object storage: AWS S3 / MinIO in the cloud setup, a local folder for quick runs."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Protocol

import pandas as pd

from .config import Settings


class ObjectStore(Protocol):
    def uri(self, key: str) -> str: ...
    def put_dataframe(self, df: pd.DataFrame, key: str) -> str: ...
    def get_dataframe(self, key: str) -> pd.DataFrame: ...
    def list_keys(self, prefix: str = "") -> list[str]: ...
    def size_bytes(self, prefix: str = "") -> int: ...


class LocalStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def uri(self, key: str) -> str:
        return str(self.root / key)

    def put_dataframe(self, df: pd.DataFrame, key: str) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        return self.uri(key)

    def get_dataframe(self, key: str) -> pd.DataFrame:
        return pd.read_parquet(self.root / key)

    def list_keys(self, prefix: str = "") -> list[str]:
        base = self.root
        return sorted(
            str(p.relative_to(base)).replace("\\", "/")
            for p in base.rglob("*")
            if p.is_file() and str(p.relative_to(base)).replace("\\", "/").startswith(prefix)
        )

    def size_bytes(self, prefix: str = "") -> int:
        return sum((self.root / k).stat().st_size for k in self.list_keys(prefix))


class S3Store:
    def __init__(self, bucket: str, region: str, endpoint_url: str | None = None):
        import boto3  # imported lazily so local mode needs no AWS libraries at runtime

        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region, endpoint_url=endpoint_url)

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def put_dataframe(self, df: pd.DataFrame, key: str) -> str:
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        buf.seek(0)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=buf.getvalue())
        return self.uri(key)

    def get_dataframe(self, key: str) -> pd.DataFrame:
        body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        return pd.read_parquet(io.BytesIO(body))

    def _iter_objects(self, prefix: str):
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            yield from page.get("Contents", [])

    def list_keys(self, prefix: str = "") -> list[str]:
        return sorted(o["Key"] for o in self._iter_objects(prefix))

    def size_bytes(self, prefix: str = "") -> int:
        return sum(o["Size"] for o in self._iter_objects(prefix))


def get_store(settings: Settings) -> ObjectStore:
    if settings.storage_backend == "s3":
        return S3Store(settings.s3_bucket, settings.s3_region, settings.s3_endpoint_url)
    return LocalStore(settings.local_lake_dir)
