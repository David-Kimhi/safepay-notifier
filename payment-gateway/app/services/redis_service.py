import logging
import os
import redis
from app.services.logging_config import APP_NAME
import time
import random


logger = logging.getLogger(APP_NAME)


def get_redis_client() -> redis.Redis:
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    
    logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")

    return redis.Redis(host=redis_host, port=redis_port, decode_responses=True)



def ping_redis(redis_client: redis.Redis, retries: int = 3, delay: float = 2.0) -> bool:
    """
    Ping Redis with retries and randomized exponential backoff.

    :param redis_client: Redis client instance.
    :param retries: Number of retry attempts on failure.
    :param delay: Initial delay between retries in seconds.
    :return: True if ping successful, False otherwise.
    """
    backoff = delay
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Pinging Redis... (attempt {attempt})")
            if redis_client.ping():
                return True
        except Exception as e:
            logger.error(f"Redis ping attempt {attempt} failed: {e}")
            if attempt < retries:
                # Use power-of-2 exponential backoff
                last_backoff = backoff
                backoff = delay * (2 ** (attempt - 1))
                sleep_time = random.uniform(last_backoff, backoff)
                logger.info(f"Retrying Redis ping in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
    return False