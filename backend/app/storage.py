"""S3-compatible object storage wrapper. Points at MinIO locally/CI, real S3 in prod via env."""

from __future__ import annotations

from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import get_settings


@lru_cache
def get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(signature_version="s3v4"),
    )


def ensure_bucket(*, bucket: str | None = None, client=None) -> str:
    """Create the bucket if it doesn't already exist. Idempotent."""
    client = client or get_s3_client()
    bucket = bucket or get_settings().s3_bucket
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)
    return bucket


def put_object(key: str, data: bytes, *, bucket: str | None = None, content_type: str | None = None, client=None) -> str:
    client = client or get_s3_client()
    bucket = bucket or get_settings().s3_bucket
    extra = {"ContentType": content_type} if content_type else {}
    client.put_object(Bucket=bucket, Key=key, Body=data, **extra)
    return key


def get_object(key: str, *, bucket: str | None = None, client=None) -> bytes:
    client = client or get_s3_client()
    bucket = bucket or get_settings().s3_bucket
    resp = client.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def presign_url(key: str, *, bucket: str | None = None, expires_in: int = 3600, client=None) -> str:
    client = client or get_s3_client()
    bucket = bucket or get_settings().s3_bucket
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in
    )
