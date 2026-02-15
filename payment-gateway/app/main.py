from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from confluent_kafka import Producer
import json
import asyncio
import uuid
from redis import Redis 
from app.services.redis_service import get_redis_client


app = FastAPI(title="SafePay Payment Gateway")
redis_client = get_redis_client()

# Schema
class PaymentRequest(BaseModel):
    user_id: str
    amount: float
    currency: str
    merchant_id: str
    timestamp: str

# Kafka Producer 
config = {
    'bootstrap.servers': 'localhost:9092',  
    'client.id': 'fastapi-producer'
}

producer = Producer(config)
TOPIC_NAME = 'transactions'

# Callback function for Kafka delivery reports
def delivery_report(err, msg):
    if err is not None:
        print(f'❌ Message delivery failed: {err}')
    else:
        print(f'✅ Message delivered to {msg.topic()} [{msg.partition()}]')

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
    
    if redis_client.exists(x_idempotency_key):
        raise HTTPException(status_code=409, detail="Duplicate request detected")
    
    # convert to json
    payment_data = payment.model_dump()
    # Additional field
    payment_data['status'] = 'processing'
    payment_data['timestamp'] = asyncio.get_event_loop().time() 
    payment_data['transaction_id'] = str(uuid.uuid4())
    payment_data['transaction_id'] = f"{int(payment_data['timestamp'])}_{payment.user_id}"
    
    try:
        producer.produce(
            TOPIC_NAME, 
            value=json.dumps(payment_data).encode('utf-8'),
            callback=delivery_report
        )
        
        producer.poll(0)
        
        return {"message": "Payment accepted for processing", "transaction_id": payment_data['transaction_id']}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))