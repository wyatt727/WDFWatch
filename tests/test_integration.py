"""
Integration tests for WDFWatch API.
Tests FastAPI endpoints with dockerized Postgres/Redis fixtures.
"""

import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_episode_id():
    """Mock episode ID for testing."""
    return "test-episode-123"


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_check(self, client):
        """Test basic health check."""
        response = client.get("/health/")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_readiness(self, client):
        """Test readiness probe."""
        response = client.get("/health/ready")
        assert response.status_code in [200, 503]  # May be 503 if dependencies not ready
    
    def test_liveness(self, client):
        """Test liveness probe."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"
    
    def test_metrics(self, client):
        """Test Prometheus metrics endpoint."""
        response = client.get("/health/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


class TestEpisodeEndpoints:
    """Test episode management endpoints."""
    
    def test_run_pipeline(self, client, mock_episode_id):
        """Test pipeline run endpoint."""
        response = client.post(
            f"/episodes/{mock_episode_id}/pipeline/run",
            json={"stages": ["summarize"]}
        )
        # May return 404 if episode not found, or 200 if queued
        assert response.status_code in [200, 404]
    
    def test_get_pipeline_status(self, client, mock_episode_id):
        """Test pipeline status endpoint."""
        response = client.get(f"/episodes/{mock_episode_id}/pipeline/status")
        assert response.status_code in [200, 404]
    
    def test_get_episode_files(self, client, mock_episode_id):
        """Test episode files endpoint."""
        response = client.get(f"/episodes/{mock_episode_id}/files")
        assert response.status_code in [200, 404]
    
    def test_get_pipeline_cache(self, client, mock_episode_id):
        """Test pipeline cache endpoint."""
        response = client.get(f"/episodes/{mock_episode_id}/pipeline/cache")
        assert response.status_code == 200
        assert "entries" in response.json()
    
    def test_clear_pipeline_cache(self, client, mock_episode_id):
        """Test cache clearing endpoint."""
        response = client.delete(f"/episodes/{mock_episode_id}/pipeline/cache")
        assert response.status_code == 200
        assert "deleted" in response.json()


class TestQueueEndpoints:
    """Test queue management endpoints."""
    
    def test_process_queue(self, client):
        """Test queue processing endpoint."""
        response = client.post(
            "/queue/process",
            json={"batch_size": 10}
        )
        assert response.status_code == 200
        assert "processed_count" in response.json()
    
    def test_list_jobs(self, client):
        """Test job listing endpoint."""
        response = client.get("/queue/jobs")
        assert response.status_code == 200
        assert "jobs" in response.json()


class TestSSEEvents:
    """Test SSE event streaming."""
    
    def test_sse_endpoint(self, client, mock_episode_id):
        """Test SSE endpoint."""
        with client.stream("GET", f"/events/{mock_episode_id}") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")


class TestPipelineCache:
    """Test pipeline caching functionality."""
    
    def test_cache_workflow(self, client, mock_episode_id):
        """Test complete cache workflow."""
        # Clear cache
        clear_response = client.delete(f"/episodes/{mock_episode_id}/pipeline/cache")
        assert clear_response.status_code == 200
        
        # Get cache (should be empty)
        get_response = client.get(f"/episodes/{mock_episode_id}/pipeline/cache")
        assert get_response.status_code == 200
        assert get_response.json()["count"] == 0

