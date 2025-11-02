"""
Server-Sent Events endpoint for real-time pipeline updates.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio
import logging
from typing import Any, Dict

from app.services.queue import get_redis_connection

router = APIRouter()
logger = logging.getLogger(__name__)


async def _stream_channel(channel: str, initial_payload: Dict[str, Any]):
    redis_conn = get_redis_connection()
    pubsub = redis_conn.pubsub()
    pubsub.subscribe(channel)

    async def event_generator():
        try:
            # Initial connection event for clients
            yield f"data: {json.dumps(initial_payload)}\n\n"

            while True:
                message = pubsub.get_message()
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield f"data: {json.dumps(data)}\n\n"
                    except json.JSONDecodeError:
                        logger.warning("Failed to decode message: %s", message["data"])

                await asyncio.sleep(0.1)

        except Exception as e:  # pragma: no cover - defensive logging
            logger.error("Error in event stream: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/queue")
async def stream_queue_events():
    """SSE endpoint for queue-wide events."""
    channel = "wdfwatch:events:queue"
    payload = {"type": "connected", "channel": "queue"}
    return await _stream_channel(channel, payload)


@router.get("/{episode_id}")
async def stream_events(episode_id: str):
    """
    SSE endpoint for episode pipeline events.
    Streams events from Redis pub/sub for the given episode.
    """
    channel = f"wdfwatch:events:episode:{episode_id}"
    payload = {"type": "connected", "episode_id": episode_id}
    return await _stream_channel(channel, payload)

