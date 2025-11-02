"""
Pipeline service wrapper around orchestrator.py.
Provides high-level interface for running pipeline stages.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.config import settings
from app.services.episodes_repo import episodes_repo

logger = logging.getLogger(__name__)


class PipelineService:
    """Service for pipeline operations."""
    
    def __init__(self):
        """Initialize pipeline service."""
        self.orchestrator_path = settings.ORCHESTRATOR_PATH
        self.episodes_repo = episodes_repo
    
    def validate_episode(self, episode_id: str) -> bool:
        """Validate that episode directory exists or can be created."""
        return True  # Episodes repo will create if needed
    
    def get_pipeline_status(self, episode_id: str) -> Dict[str, Any]:
        """Get pipeline status for an episode."""
        files = self.episodes_repo.get_episode_files(episode_id)
        file_names = {entry["filename"] for entry in files}
        
        # Determine stage completion based on files
        stages = {
            "summarize": "summary.md" in file_names,
            "classify": "classified.json" in file_names,
            "respond": "responses.json" in file_names,
            "moderate": "published.json" in file_names,
        }
        
        completed_stages = [stage for stage, completed in stages.items() if completed]
        
        return {
            "episode_id": episode_id,
            "stages": stages,
            "completed_stages": completed_stages,
            "files": files,
        }
    
    def can_run_stage(self, episode_id: str, stage: str) -> tuple[bool, Optional[str]]:
        """Check if a stage can be run (dependencies met)."""
        files = self.episodes_repo.get_episode_files(episode_id)
        file_names = {entry["filename"] for entry in files}
        
        dependencies = {
            "classify": ["summary.md"],
            "respond": ["classified.json"],
            "moderate": ["responses.json"],
        }
        
        if stage in dependencies:
            required = dependencies[stage]
            missing = [f for f in required if f not in file_names]
            if missing:
                return False, f"Missing required files: {', '.join(missing)}"
        
        return True, None


# Global instance
pipeline_service = PipelineService()

