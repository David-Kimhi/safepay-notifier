"""Kafka consumer worker: idempotency in Redis, settlement in Postgres."""

import json
import os
import time
import redis
from confluent_kafka import Consumer

from logging_config import setup_logging
from ledger import settle_payment

logger = setup_logging()

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'), 
    port=int(os.getenv('REDIS_PORT', 6379)), 
    decode_responses=True
)
kafka_bootstrap = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
logger.info("Kafka bootstrap servers: %s", kafka_bootstrap)
logger.info("Redis host: %s", os.getenv('REDIS_HOST', 'localhost'))
logger.info("Redis port: %s", os.getenv('REDIS_PORT', 6379))

conf = {
    'bootstrap.servers': kafka_bootstrap,
    'group.id': 'payment_workers',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False  # We commit manually only after success
}

def process_payment(payment_data):
    """Handle one Kafka payment message; return True if safe to commit offset."""
    txn_id = payment_data.get('gateway_transaction_id')
    amount = payment_data.get('amount')
    redis_key = f"consumer:{payment_data.get('idempotency_key')}"

    # 1. Idempotency Check
    if redis_client.exists(redis_key):
        logger.info("Skipping %s (already processed)", txn_id)
        return True

    logger.info("Processing %s ($%s)...", txn_id, amount)

    try:
        status, reason = settle_payment(payment_data)

        if status == "duplicate":
            logger.info("Skipping %s (already in Postgres)", txn_id)
            redis_client.set(redis_key, "processed", ex=3600)
            return True

        redis_client.set(redis_key, status, ex=3600)
        if status == "approved":
            logger.info("Approved: %s", txn_id)
        else:
            logger.warning("Rejected: %s — %s", txn_id, reason)
        return True

    except Exception as e:
        logger.error("Critical failure: %s: %s", txn_id, e)
        return False

def main():
    """Poll Kafka, process payments, commit offset only after success."""
    consumer = Consumer(conf)
    topic = os.getenv('KAFKA_TOPIC', 'transactions')
    consumer.subscribe([topic])
    logger.info("Worker started")

    try:
        while True:
            time.sleep(0.2)
            msg = consumer.poll(1.0)

            if msg is None:
                continue
            if msg.error():
                logger.error("Consumer error: %s", msg.error())
                continue

            try:
                data = json.loads(msg.value().decode('utf-8'))
                success = process_payment(data)
                if success:
                    consumer.commit(asynchronous=False)
            except Exception as e:
                logger.exception("Error decoding message: %s", e)

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

if __name__ == '__main__':
    main()
