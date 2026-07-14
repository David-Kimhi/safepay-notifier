from fastapi import FastAPI, HTTPException, Header, Response
from pydantic import BaseModel
import time
import json
import uuid
from app.services.redis_service import get_redis_client, ping_redis
from app.services.logging_config import setup_logging
from app.services.kafka_config import get_kafka_producer, get_kafka_topic
from prometheus_fastapi_instrumentator import Instrumentator

import os

# Define logger for this module
logger = setup_logging()

# Define FastAPI app
app = FastAPI(title="SafePay Payment Gateway")

# Expose Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app)

# Define Redis client
redis_client = get_redis_client()

# Define Kafka producer and topic
producer = get_kafka_producer()
TOPIC_NAME = get_kafka_topic()


@app.on_event("startup")
def startup():
    logger.info("SafePay Payment Gateway started")
    
    # Ping Redis
    ping_redis(redis_client)

# Schema
class PaymentRequest(BaseModel):
    source_account_id: str
    destination_account_id: str
    amount: float
    currency: str
    payment_type: str
    timestamp: str
    
class PaymentResponse(BaseModel):
    status: str
    gateway_transaction_id: str
    


# Endpoint
@app.post("/pay", response_model=PaymentResponse)
async def process_payment(
    payment: PaymentRequest,
    response: Response,
    x_idempotency_key: str = Header(..., alias="Idempotency-Key")
):
    """
    Receives a payment request and forwards it for background processing.
    Returns a quick response to the client.
    """

    idempotency_key = f"{payment.source_account_id}:{x_idempotency_key}"
    result = {"ok": True, "error": None}
    def delivery_report(err, msg):
        if err is not None:
            result["ok"] = False
            result["error"] = str(err)
        
    payment_data = {
        **payment.model_dump(),
        "status": "processing",
        "gateway_received_timestamp": time.time(),
        "gateway_transaction_id": str(uuid.uuid4()),
        "idempotency_key": idempotency_key
    }
    
    
    # Rename timestamp to source_account_timestamp
    payment_data['source_account_timestamp'] = payment_data.pop('timestamp')
    
    
    
    try:
        
        resp = PaymentResponse(status="accepted", gateway_transaction_id=payment_data['gateway_transaction_id'])
        
        # Idempotency check
        redis_key = f"producer:{idempotency_key}"
        redis_resp = redis_client.set(
            redis_key,
            json.dumps(resp.model_dump()),
            nx=True,
            ex=3*60*60 # 3 hours
        )
        
        if not redis_resp:
            logger.warning("Duplicate request rejected: idempotency_key=%s", idempotency_key)
            existing = redis_client.get(redis_key)
            return PaymentResponse.model_validate_json(existing)
        
        # Produce to Kafka
        producer.produce(
            TOPIC_NAME,
            key=payment_data['source_account_id'].encode('utf-8'),
            value=json.dumps(payment_data).encode('utf-8'),
            callback=delivery_report
        )
        producer.flush()
        
        if not result["ok"]:
            logger.error("Message delivery failed: %s", result["error"])

            failed = PaymentResponse(status="failed", gateway_transaction_id=payment_data['gateway_transaction_id'])
            redis_client.set(redis_key, failed.model_dump_json(), ex=3*60*60)
            response.status_code = 500
            return failed
        
        queued = PaymentResponse(status="queued", gateway_transaction_id=payment_data['gateway_transaction_id'])
        redis_client.set(redis_key, queued.model_dump_json(), ex=3*60*60)
        response.status_code = 202

        logger.info("Payment request sent to Kafka: %s", payment_data['gateway_transaction_id'])
        
        return queued
    
    except Exception as e:
        logger.exception("Failed to process payment request: %s\nGateway Transaction ID: %s", e, payment_data['gateway_transaction_id'])
        raise HTTPException(status_code=500, detail=str(e))