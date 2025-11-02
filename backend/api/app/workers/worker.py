"""
RQ worker entrypoint for processing background jobs.
"""

import logging
import sys
from pathlib import Path

from rq import Worker
from rq.handlers import SignalHandler

from app.config import settings
from app.services.queue import get_queue, get_redis_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_worker(queue_name: str = "default") -> Worker:
    """Create and return RQ worker."""
    queue = get_queue(queue_name)
    redis_conn = get_redis_connection()
    
    worker = Worker(
        [queue],
        connection=redis_conn,
        name=f"wdfwatch-worker-{queue_name}",
    )
    
    return worker


def main():
    """Main entrypoint for worker."""
    logger.info("Starting WDFWatch RQ worker")
    logger.info(f"Project root: {settings.PROJECT_ROOT}")
    logger.info(f"Episodes directory: {settings.EPISODES_DIR}")
    
    # Ensure episodes directory exists
    settings.EPISODES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create worker
    queue_name = sys.argv[1] if len(sys.argv) > 1 else "default"
    worker = create_worker(queue_name)
    
    logger.info(f"Worker listening on queue: {queue_name}")
    
    # Start worker with signal handling
    signal_handler = SignalHandler()
    signal_handler.register(worker)
    
    try:
        worker.work(with_scheduler=True)
    except KeyboardInterrupt:
        logger.info("Worker shutdown requested")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

