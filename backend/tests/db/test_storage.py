import uuid

import httpx
import pytest

from app import storage


@pytest.fixture(scope="module", autouse=True)
def _ensure_bucket():
    storage.ensure_bucket()


def test_put_get_round_trip():
    key = f"test/{uuid.uuid4()}.txt"
    body = b"hello codebench"

    storage.put_object(key, body, content_type="text/plain")
    fetched = storage.get_object(key)

    assert fetched == body


def test_presign_url_is_fetchable():
    key = f"test/{uuid.uuid4()}.txt"
    body = b"presigned content"
    storage.put_object(key, body, content_type="text/plain")

    url = storage.presign_url(key, expires_in=60)
    resp = httpx.get(url, timeout=10)

    assert resp.status_code == 200
    assert resp.content == body


def test_ensure_bucket_is_idempotent():
    storage.ensure_bucket()
    storage.ensure_bucket()
