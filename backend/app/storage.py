"""Object storage for reviews and recordings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import get_settings


def storage_backend() -> str:
    return "s3" if get_settings().s3_bucket else "local"


def save_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> dict[str, Any]:
    settings = get_settings()
    if settings.s3_bucket:
        return _save_s3(key, data, content_type)
    return _save_local(key, data)


def save_json(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return save_bytes(key, data, "application/json")


def _save_local(key: str, data: bytes) -> dict[str, Any]:
    root = Path(__file__).resolve().parent.parent.parent / "reviews"
    path = root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"backend": "local", "key": key, "path": str(path)}


def _s3_client():
    import boto3

    settings = get_settings()
    kwargs: dict[str, Any] = {
        "aws_access_key_id": settings.s3_access_key_id,
        "aws_secret_access_key": settings.s3_secret_access_key,
        "region_name": settings.s3_region,
    }
    if settings.s3_endpoint:
        kwargs["endpoint_url"] = settings.s3_endpoint
    return boto3.client("s3", **kwargs)


def _save_s3(key: str, data: bytes, content_type: str) -> dict[str, Any]:
    settings = get_settings()
    client = _s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    url = f"{settings.s3_public_base.rstrip('/')}/{key}" if settings.s3_public_base else None
    return {"backend": "s3", "key": key, "bucket": settings.s3_bucket, "url": url}
