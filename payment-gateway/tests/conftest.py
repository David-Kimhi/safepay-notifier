import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def mock_redis():
    store = {}

    redis = MagicMock()

    def set_(key, value, nx=False, ex=None):
        if nx and key in store:
            return False
        store[key] = value
        return True

    def get_(key):
        return store.get(key)

    redis.set.side_effect = set_
    redis.get.side_effect = get_
    redis._store = store

    with patch("app.main.redis_client", redis):
        yield redis


@pytest.fixture
def mock_producer_success():
    producer = MagicMock()

    def produce_side_effect(*args, **kwargs):
        callback = kwargs.get("callback")
        if callback:
            msg = MagicMock()
            msg.topic.return_value = "payments"
            msg.partition.return_value = 0
            callback(None, msg)

    producer.produce.side_effect = produce_side_effect
    producer.flush.return_value = None

    with patch("app.main.producer", producer):
        yield producer


@pytest.fixture
def mock_producer_failure():
    producer = MagicMock()

    def produce_side_effect(*args, **kwargs):
        callback = kwargs.get("callback")
        if callback:
            callback("broker unavailable", None)

    producer.produce.side_effect = produce_side_effect
    producer.flush.return_value = None

    with patch("app.main.producer", producer):
        yield producer


@pytest.fixture
def client(mock_redis, mock_producer_success):
    with patch("app.main.ping_redis", return_value=True):
        with TestClient(app) as c:
            yield c


def valid_payment():
    return {
        "source_account_id": "acct_user_1",
        "destination_account_id": "acct_merchant_1",
        "amount": 100.0,
        "currency": "ILS",
        "payment_type": "purchase",
        "timestamp": "2026-06-27T10:00:00Z",
    }


def idem_headers(key="idem-123"):
    return {"Idempotency-Key": key}