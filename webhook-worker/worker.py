import json
import os
import time
import random
import sys
import redis
from confluent_kafka import Consumer, KafkaError

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'), 
    port=int(os.getenv('REDIS_PORT', 6379)), 
    decode_responses=True
)
kafka_bootstrap = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')

conf = {
    'bootstrap.servers': kafka_bootstrap,
    'group.id': 'payment_workers',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False  # We commit manually only after success
}

def process_payment(payment_data):
    txn_id = payment_data.get('transaction_id')
    amount = payment_data.get('amount')
    
    # 1. Idempotency Check
    if redis_client.exists(txn_id):
        print(f"⏭️  Skipping {txn_id} (Already processed)")
        return True

    print(f"🔄 Processing {txn_id} (${amount})...")

    # 2. Retry Loop with Exponential Backoff
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            # Simulate processing time
            time.sleep(0.5)
            
            # Simulate random failure (30% chance to fail)
            if random.random() < 0.3:
                raise Exception("Bank API Connection Timeout")

            # Success logic
            redis_client.set(txn_id, "processed", ex=3600) # Expire in 1 hour
            print(f"✅ Success: {txn_id}")
            return True

        except Exception as e:
            wait_time = 2 ** attempt  # 2, 4, 8 seconds
            print(f"⚠️  Attempt {attempt} failed: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
    
    print(f"❌ Critical Failure: {txn_id} moved to Dead Letter Queue")
    return False

def main():
    consumer = Consumer(conf)
    topic = 'transactions'
    consumer.subscribe([topic])

    print("👷 Worker with Redis & Retries started...")

    try:
        while True:
            msg = consumer.poll(1.0)

            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue

            try:
                data = json.loads(msg.value().decode('utf-8'))
                
                success = process_payment(data)
                
                if success:
                    consumer.commit(asynchronous=False)
                
            except Exception as e:
                print(f"Error decoding message: {e}")

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

if __name__ == '__main__':
    main()