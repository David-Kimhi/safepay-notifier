from tests.conftest import valid_payment, idem_headers


def test_pay_success_202(client):
    resp = client.post("/pay", json=valid_payment(), headers=idem_headers())

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert "gateway_transaction_id" in body


def test_pay_missing_idempotency_key_422(client):
    resp = client.post("/pay", json=valid_payment())
    assert resp.status_code == 422


def test_pay_invalid_body_422(client):
    payload = valid_payment()
    del payload["amount"]
    resp = client.post("/pay", json=payload, headers=idem_headers())
    assert resp.status_code == 422


def test_pay_duplicate_idempotency_returns_cached(client, mock_redis):
    payload = valid_payment()
    headers = idem_headers("same-key")

    first = client.post("/pay", json=payload, headers=headers)
    second = client.post("/pay", json=payload, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 200  # default unless you set response.status_code on duplicate path
    assert first.json()["gateway_transaction_id"] == second.json()["gateway_transaction_id"]


def test_pay_kafka_delivery_failure_500(client, mock_redis, mock_producer_failure):
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from app.main import app

    with patch("app.main.ping_redis", return_value=True):
        with TestClient(app) as c:
            resp = c.post("/pay", json=valid_payment(), headers=idem_headers("fail-key"))

    assert resp.status_code == 500
    assert resp.json()["status"] == "failed"


def test_produce_called_with_kafka_key_and_value(client, mock_producer_success):
    client.post("/pay", json=valid_payment(), headers=idem_headers("produce-key"))

    mock_producer_success.produce.assert_called_once()
    kwargs = mock_producer_success.produce.call_args.kwargs
    assert kwargs["key"] == b"acct_user_1"
    assert b"source_account_id" in kwargs["value"]
    mock_producer_success.flush.assert_called_once()