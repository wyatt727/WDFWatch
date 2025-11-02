"""
Structured logging configuration for WDFWatch API.
Uses structlog for JSON-formatted logs with trace IDs and job IDs.
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.types import Processor

from app.config import settings


def configure_logging():
    """Configure structured logging for the application."""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
    )
    
    # Configure structlog processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    # Add JSON formatting in production
    if settings.ENVIRONMENT == "production":
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ])
    else:
        # Pretty console output in development
        processors.extend([
            structlog.dev.ConsoleRenderer(),
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (defaults to calling module)
        
    Returns:
        Bound logger instance
    """
    return structlog.get_logger(name)


def add_trace_context(logger: structlog.BoundLogger, trace_id: str, job_id: str = None) -> structlog.BoundLogger:
    """
    Add trace context to logger.
    
    Args:
        logger: Logger instance
        trace_id: Trace identifier
        job_id: Optional job identifier
        
    Returns:
        Logger with context bound
    """
    context = {"trace_id": trace_id}
    if job_id:
        context["job_id"] = job_id
    return logger.bind(**context)

