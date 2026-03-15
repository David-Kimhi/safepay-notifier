from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from confluent_kafka import Producer
import json
import asyncio
import uuid
from redis import Redis
from app.services.redis_service import get_redis_client, ping_redis
from app.services.logging_config import setup_logging
from app.services.kafka_config import get_kafka_producer, get_kafka_topic

import os

# Define logger for this module
logger = setup_logging()

# Define FastAPI app
app = FastAPI(title="SafePay Payment Gateway")

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
    user_id: str
    amount: float
    currency: str
    merchant_id: str
    timestamp: str



# Callback function for Kafka delivery reports
def delivery_report(err, msg):
    if err is not None:
        logger.error("Message delivery failed: %s", err)
    else:
        logger.info("Message delivered to %s [%s]", msg.topic(), msg.partition())

    

# Endpoint
@app.post("/pay", status_code=202)
async def process_payment(
    payment: PaymentRequest,
    x_idempotency_key: str = Header(..., alias="Idempotency-Key")
):
    """
    Receives a payment request and immediately forwards it for background processing.
    Returns a quick response to the client.
    """
    logger.info("Payment request received: user_id=%s amount=%s idempotency_key=%s", payment.user_id, payment.amount, x_idempotency_key)

    if redis_client.exists(x_idempotency_key):
        logger.warning("Duplicate request rejected: idempotency_key=%s", x_idempotency_key)
        raise HTTPException(status_code=409, detail="Duplicate request detected")

    payment_data = payment.model_dump()
    payment_data['status'] = 'processing'
    payment_data['timestamp'] = asyncio.get_event_loop().time()
    payment_data['transaction_id'] = str(uuid.uuid4())

    try:
        producer.produce(
            TOPIC_NAME,
            value=json.dumps(payment_data).encode('utf-8'),
            callback=delivery_report
        )
        producer.poll(0)
        logger.info("Payment accepted for processing: transaction_id=%s", payment_data['transaction_id'])
        return {"message": "Payment accepted for processing", "transaction_id": payment_data['transaction_id']}
    except Exception as e:
        logger.exception("Failed to produce payment to Kafka: %s", e)
        raise HTTPException(status_code=500, detail=str(e))