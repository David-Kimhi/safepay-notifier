
import os
import redis


def get_redis_client() -> redis.Redis:
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))

    return redis.Redis(host=redis_host, port=redis_port, decode_responses=True)