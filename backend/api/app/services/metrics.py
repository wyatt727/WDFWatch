"""
Prometheus metrics collection for WDFWatch API.
"""

import time
from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# Job metrics
job_duration = Histogram(
    'wdfwatch_job_duration_seconds',
    'Job execution duration in seconds',
    ['job_type', 'status'],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
)

job_count = Counter(
    'wdfwatch_job_total',
    'Total number of jobs processed',
    ['job_type', 'status']
)

job_retries = Counter(
    'wdfwatch_job_retries_total',
    'Total number of job retries',
    ['job_type']
)

# Queue metrics
queue_depth = Gauge(
    'wdfwatch_queue_depth',
    'Current queue depth',
    ['queue_name']
)

queue_jobs_processed = Counter(
    'wdfwatch_queue_jobs_processed_total',
    'Total number of jobs processed from queue',
    ['queue_name', 'status']
)

# Pipeline metrics
pipeline_stage_duration = Histogram(
    'wdfwatch_pipeline_stage_duration_seconds',
    'Pipeline stage execution duration',
    ['episode_id', 'stage', 'status'],
    buckets=[1, 5, 10, 30, 60, 300, 600]
)

pipeline_stage_count = Counter(
    'wdfwatch_pipeline_stage_total',
    'Total number of pipeline stages executed',
    ['stage', 'status']
)

# Claude API metrics
claude_api_calls = Counter(
    'wdfwatch_claude_api_calls_total',
    'Total number of Claude API calls',
    ['stage', 'status']
)

claude_tokens_total = Counter(
    'wdfwatch_claude_tokens_total',
    'Total Claude API tokens used',
    ['token_type']  # 'input' or 'output'
)

claude_cost_usd = Counter(
    'wdfwatch_claude_cost_usd_total',
    'Total Claude API cost in USD',
    ['stage']
)

# System metrics
system_cpu_percent = Gauge(
    'wdfwatch_system_cpu_percent',
    'System CPU usage percentage'
)

system_memory_mb = Gauge(
    'wdfwatch_system_memory_mb',
    'System memory usage in MB'
)

# Database metrics
db_connections = Gauge(
    'wdfwatch_db_connections',
    'Current database connections'
)

db_query_duration = Histogram(
    'wdfwatch_db_query_duration_seconds',
    'Database query duration',
    ['operation'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)


def get_metrics_response() -> Response:
    """Generate Prometheus metrics response."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


class MetricsCollector:
    """Context manager for collecting metrics."""
    
    def __init__(self, metric: Histogram, labels: Dict[str, str]):
        self.metric = metric
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        status = "success" if exc_type is None else "failure"
        labels = {**self.labels, "status": status}
        self.metric.labels(**labels).observe(duration)

