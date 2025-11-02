"""
Redis connection and RQ queue setup.
"""

import redis
from rq import Queue
from rq.job import Job

from app.config import settings

# Create Redis connection
redis_conn = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
)

# Create RQ queue
default_queue = Queue("default", connection=redis_conn, default_timeout=settings.JOB_TIMEOUT)


def get_queue(name: str = "default") -> Queue:
    """Get RQ queue by name."""
    return Queue(name, connection=redis_conn, default_timeout=settings.JOB_TIMEOUT)


def get_job(job_id: str) -> Job:
    """Get job by ID."""
    return Job.fetch(job_id, connection=redis_conn)


def get_redis_connection() -> redis.Redis:
    """Get Redis connection."""
    return redis_conn

