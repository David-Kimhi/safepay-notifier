import os
from confluent_kafka import Producer

from app.services.logging_config import APP_NAME
import logging

logger = logging.getLogger(APP_NAME)

DEFAULT_BOOTSTRAP_SERVERS = "localhost:9092"
DEFAULT_TOPIC = "transactions"
CLIENT_ID = "fastapi-producer"


def get_kafka_producer() -> Producer:
    """Create and return a Kafka producer using env config."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", DEFAULT_BOOTSTRAP_SERVERS)
    config = {
        "bootstrap.servers": bootstrap_servers,
        "client.id": CLIENT_ID,
    }
    logger.info("Kafka producer configured with bootstrap.servers=%s", bootstrap_servers)
    return Producer(config)


def get_kafka_topic() -> str:
    """Return the Kafka topic name from env or default."""
    topic = os.getenv("KAFKA_TOPIC", DEFAULT_TOPIC)
    logger.info("Kafka topic=%s", topic)
    return topic
