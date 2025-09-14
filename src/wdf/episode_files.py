"""
Episode-based file management for the WDF pipeline.

This module provides utilities for managing files in an episode-centric way,
ensuring each episode has its own isolated set of input and output files.
"""

import os
import json
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Union
from datetime import datetime

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

# Default base directory for episodes
EPISODES_BASE_DIR = os.environ.get('EPISODES_DIR', './episodes')


class FileConfig(BaseModel):
    """Configuration for episode file paths"""
    episode_dir: str
    pipeline_type: str = Field(default='legacy')
    files: Dict[str, str] = Field(default_factory=dict)
    
    def __init__(self, **data):
        super().__init__(**data)
        # Set default file mappings if not provided
        if not self.files:
            if self.pipeline_type == 'claude':
                # Claude pipeline structure - flatter directory layout
                self.files = {
                    # User input files - directly in episode directory
                    'transcript': 'transcript.txt',
                    'video_url': 'video_url.txt',
                    # Context files - copied or generated
                    'overview': 'podcast_overview.txt',
                    'episode_context': 'EPISODE_CONTEXT.md',
                    # Output files - also directly in episode directory
                    'summary': 'summary.md',
                    'keywords': 'keywords.json',
                    'tweets': 'tweets.json',
                    'classified': 'classified.json',
                    'responses': 'responses.json',
                    'published': 'published.json',
                    # No cache files for Claude pipeline - it uses different caching
                }
            else:
                # Legacy pipeline structure - subdirectories
                self.files = {
                    # Input files
                    'transcript': 'inputs/transcript.txt',
                    'overview': 'inputs/podcast_overview.txt',
                    'video_url': 'inputs/video_url.txt',
                    # Output files
                    'summary': 'outputs/summary.md',
                    'keywords': 'outputs/keywords.json',
                    'fewshots': 'outputs/fewshots.json',
                    'tweets': 'outputs/tweets.json',
                    'classified': 'outputs/classified.json',
                    'responses': 'outputs/responses.json',
                    'published': 'outputs/published.json',
                    # Cache files
                    'summary_hash': 'cache/summary.hash',
                    'fewshots_hash': 'cache/fewshots.hash'
                }


class EpisodeFileManager:
    """
    Manages files for a specific episode, providing easy access to input/output paths
    and ensuring proper directory structure.
    """
    
    def __init__(self, episode_id: Union[int, str], episode_dir: Optional[str] = None, pipeline_type: Optional[str] = None):
        """
        Initialize file manager for an episode.
        
        Args:
            episode_id: The episode ID
            episode_dir: Optional custom episode directory. If not provided,
                        will be loaded from database or generated.
            pipeline_type: Pipeline type ('claude' or 'legacy'). If not provided,
                          will be detected from environment or database.
        """
        self.episode_id = str(episode_id)
        
        # Determine pipeline type
        if pipeline_type:
            self.pipeline_type = pipeline_type
        else:
            self.pipeline_type = self._detect_pipeline_type()
        
        if episode_dir:
            self.episode_dir = episode_dir
        else:
            # Try to load from database if web mode
            if os.environ.get('WDF_WEB_MODE', 'false').lower() == 'true':
                episode_info = self._load_episode_info_from_db()
                
                # Check if this is a Claude pipeline episode
                if episode_info.get('claude_episode_dir'):
                    # Use Claude pipeline configuration
                    self.episode_dir = episode_info['claude_episode_dir']
                    self.pipeline_type = 'claude'
                    # Override base path to use claude-pipeline/episodes directory
                    self.base_path = Path(os.getcwd()) / "claude-pipeline" / "episodes" / self.episode_dir
                else:
                    self.episode_dir = episode_info.get('episode_dir', self._generate_default_dir())
                    if not self.pipeline_type:
                        self.pipeline_type = episode_info.get('pipeline_type', 'legacy')
                    self.base_path = Path(EPISODES_BASE_DIR) / self.episode_dir
            else:
                self.episode_dir = self._generate_default_dir()
                self.base_path = Path(EPISODES_BASE_DIR) / self.episode_dir
        
        # Set base path if not already set
        if not hasattr(self, 'base_path'):
            self.base_path = Path(EPISODES_BASE_DIR) / self.episode_dir
            
        self.file_config = self._load_or_create_config()
        
        # Ensure base directories exist
        self._ensure_directories()
        
        logger.info(
            "Initialized episode file manager",
            episode_id=self.episode_id,
            episode_dir=self.episode_dir,
            pipeline_type=self.pipeline_type,
            base_path=str(self.base_path)
        )
    
    def _detect_pipeline_type(self) -> str:
        """Detect pipeline type from environment or configuration"""
        # Check environment variable first
        if os.environ.get('WDF_USE_CLAUDE_PIPELINE', 'false').lower() == 'true':
            return 'claude'
        
        # Check for Claude-specific environment
        if os.environ.get('WDF_CLAUDE_EPISODE_DIR'):
            return 'claude'
        
        return 'legacy'
    
    def _generate_default_dir(self) -> str:
        """Generate default directory name based on pipeline type"""
        if self.pipeline_type == 'claude':
            # Claude uses episode_YYYYMMDD_HHMMSS format
            timestamp = datetime.now()
            date_str = timestamp.strftime('%Y%m%d')
            time_str = timestamp.strftime('%H%M%S')
            return f"episode_{date_str}_{time_str}"
        else:
            # Legacy uses YYYY-MM-DD-title format
            timestamp = datetime.now().strftime('%Y%m%d')
            return f"{timestamp}-ep{self.episode_id}"
    
    def _load_episode_info_from_db(self) -> Dict[str, Any]:
        """Load episode info from database"""
        try:
            # Try web bridge first
            try:
                from web.scripts.web_bridge import WebUIBridge
                bridge = WebUIBridge()
                episode = bridge.get_episode(int(self.episode_id))
                if episode:
                    # Map database fields to our expected format
                    result = {
                        'episode_dir': episode.get('episode_dir'),
                        'claude_episode_dir': episode.get('claude_episode_dir'),
                        'pipeline_type': episode.get('pipeline_type', 'legacy')
                    }
                    # If Claude episode directory is set, mark as Claude pipeline
                    if episode.get('claude_episode_dir'):
                        result['pipeline_type'] = 'claude'
                    return result
            except ImportError:
                pass
            
            # Fallback to legacy approach
            from src.wdf.web_bridge import load_episode_config
            config = load_episode_config(self.episode_id)
            if config:
                return {
                    'episode_dir': config.get('episode_dir'),
                    'claude_episode_dir': config.get('claude_episode_dir'),
                    'pipeline_type': config.get('pipeline_type', 'legacy')
                }
        except Exception as e:
            logger.warning(
                "Failed to load episode info from database",
                episode_id=self.episode_id,
                error=str(e)
            )
        
        return {
            'episode_dir': self._generate_default_dir(),
            'pipeline_type': self.pipeline_type
        }
    
    def _load_episode_dir_from_db(self) -> str:
        """Load episode directory from database (legacy method)"""
        episode_info = self._load_episode_info_from_db()
        return episode_info.get('episode_dir', self._generate_default_dir())
    
    def _load_or_create_config(self) -> FileConfig:
        """Load existing config or create default"""
        config_path = self.base_path / 'pipeline-config.json'
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                # Ensure pipeline_type is set correctly
                data.setdefault('pipeline_type', self.pipeline_type)
                return FileConfig(**data)
            except Exception as e:
                logger.warning(
                    "Failed to load pipeline config",
                    error=str(e)
                )
        
        # Create default config
        config = FileConfig(
            episode_dir=self.episode_dir,
            pipeline_type=self.pipeline_type
        )
        self._save_config(config)
        return config
    
    def _save_config(self, config: FileConfig):
        """Save config to file"""
        config_path = self.base_path / 'pipeline-config.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(config.dict(), f, indent=2)
    
    def _ensure_directories(self):
        """Ensure all required directories exist"""
        # Always ensure the base episode directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Only create subdirectories for legacy pipeline
        if self.pipeline_type == 'legacy':
            dirs = ['inputs', 'outputs', 'cache']
            for dir_name in dirs:
                dir_path = self.base_path / dir_name
                dir_path.mkdir(parents=True, exist_ok=True)
    
    def get_input_path(self, key: str) -> Path:
        """
        Get the full path for an input file.
        
        Args:
            key: File key (e.g., 'transcript', 'overview')
            
        Returns:
            Path object for the file
        """
        relative_path = self.file_config.files.get(key)
        if not relative_path:
            raise ValueError(f"Unknown input file key: {key}")
        
        return self.base_path / relative_path
    
    def get_output_path(self, key: str) -> Path:
        """
        Get the full path for an output file.
        
        Args:
            key: File key (e.g., 'summary', 'keywords')
            
        Returns:
            Path object for the file
        """
        relative_path = self.file_config.files.get(key)
        if not relative_path:
            raise ValueError(f"Unknown output file key: {key}")
        
        return self.base_path / relative_path
    
    def read_input(self, key: str, encoding: str = 'utf-8') -> str:
        """Read an input file"""
        path = self.get_input_path(key)
        
        if not path.exists():
            # Try legacy path as fallback
            legacy_path = self._get_legacy_path(key)
            if legacy_path and legacy_path.exists():
                logger.info(
                    "Using legacy file path",
                    key=key,
                    legacy_path=str(legacy_path)
                )
                return legacy_path.read_text(encoding=encoding)
            
            raise FileNotFoundError(f"Input file not found: {key} at {path}")
        
        return path.read_text(encoding=encoding)
    
    def write_output(self, key: str, content: Union[str, dict, list], encoding: str = 'utf-8'):
        """Write an output file"""
        path = self.get_output_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(content, (dict, list)):
            # JSON content
            with open(path, 'w', encoding=encoding) as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
        else:
            # Text content
            path.write_text(content, encoding=encoding)
        
        logger.info(
            "Wrote output file",
            key=key,
            path=str(path),
            size=len(content) if isinstance(content, str) else len(json.dumps(content))
        )
    
    def _get_legacy_path(self, key: str) -> Optional[Path]:
        """Get legacy file path for backward compatibility"""
        legacy_paths = {
            'transcript': Path('transcripts/latest.txt'),
            'overview': Path('transcripts/podcast_overview.txt'),
            'video_url': Path('transcripts/VIDEO_URL.txt'),
            'summary': Path('transcripts/summary.md'),
            'keywords': Path('transcripts/keywords.json'),
            'fewshots': Path('transcripts/fewshots.json'),
            'tweets': Path('transcripts/tweets.json'),
            'classified': Path('transcripts/classified.json'),
            'responses': Path('transcripts/responses.json'),
            'published': Path('transcripts/published.json')
        }
        return legacy_paths.get(key)
    
    def copy_from_legacy(self, key: str) -> bool:
        """
        Copy a file from legacy location to episode directory.
        
        Returns:
            True if file was copied, False if not found
        """
        legacy_path = self._get_legacy_path(key)
        if not legacy_path or not legacy_path.exists():
            return False
        
        target_path = self.get_input_path(key) if key in ['transcript', 'overview', 'video_url'] else self.get_output_path(key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(legacy_path, target_path)
        logger.info(
            "Copied legacy file to episode directory",
            key=key,
            source=str(legacy_path),
            target=str(target_path)
        )
        return True
    
    def get_file_hash(self, key: str) -> str:
        """Get SHA256 hash of a file"""
        try:
            # User input files differ by pipeline type
            if self.file_config.pipeline_type == 'claude':
                input_keys = ['transcript', 'video_url']  # Only user inputs for Claude
            else:
                input_keys = ['transcript', 'overview', 'video_url']  # Legacy inputs
            
            path = self.get_input_path(key) if key in input_keys else self.get_output_path(key)
            
            if not path.exists():
                return ""
            
            content = path.read_bytes()
            return hashlib.sha256(content).hexdigest()[:16]
        except Exception as e:
            logger.warning(
                "Failed to compute file hash",
                key=key,
                error=str(e)
            )
            return ""
    
    def file_exists(self, key: str) -> bool:
        """Check if a file exists"""
        try:
            # User input files differ by pipeline type
            if self.file_config.pipeline_type == 'claude':
                input_keys = ['transcript', 'video_url']  # Only user inputs for Claude
            else:
                input_keys = ['transcript', 'overview', 'video_url']  # Legacy inputs
            
            path = self.get_input_path(key) if key in input_keys else self.get_output_path(key)
            return path.exists()
        except ValueError:
            return False
    
    def list_files(self) -> Dict[str, Dict[str, Any]]:
        """List all files with their status"""
        files = {}
        
        for key, relative_path in self.file_config.files.items():
            full_path = self.base_path / relative_path
            
            if full_path.exists():
                stat = full_path.stat()
                files[key] = {
                    'exists': True,
                    'path': relative_path,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'hash': self.get_file_hash(key)
                }
            else:
                files[key] = {
                    'exists': False,
                    'path': relative_path
                }
        
        return files
    
    def cleanup_outputs(self, stage: Optional[str] = None):
        """
        Clean up output files for a specific stage or all stages.
        
        Args:
            stage: Pipeline stage name (e.g., 'summarization', 'classification')
                  If None, cleans all outputs
        """
        if self.file_config.pipeline_type == 'claude':
            # Claude pipeline stages
            stage_outputs = {
                'summarization': ['summary', 'keywords', 'episode_context'],
                'classification': ['classified'],
                'response': ['responses'],
                'moderation': ['published']
            }
            default_outputs = ['summary', 'keywords', 'classified', 'responses', 'published']
        else:
            # Legacy pipeline stages
            stage_outputs = {
                'summarization': ['summary', 'keywords'],
                'fewshot': ['fewshots'],
                'scraping': ['tweets'],
                'classification': ['classified'],
                'response': ['responses'],
                'moderation': ['published']
            }
            default_outputs = ['summary', 'keywords', 'fewshots', 'tweets', 
                              'classified', 'responses', 'published']
        
        if stage:
            outputs_to_clean = stage_outputs.get(stage, [])
        else:
            outputs_to_clean = default_outputs
        
        for key in outputs_to_clean:
            try:
                # Skip if this file key doesn't exist in the current pipeline configuration
                if key not in self.file_config.files:
                    continue
                    
                path = self.get_output_path(key)
                if path.exists():
                    path.unlink()
                    logger.info(
                        "Cleaned up output file",
                        key=key,
                        path=str(path)
                    )
            except Exception as e:
                logger.warning(
                    "Failed to clean up file",
                    key=key,
                    error=str(e)
                )


# Convenience function for backward compatibility
def get_episode_file_manager(episode_id: Optional[Union[int, str]] = None) -> EpisodeFileManager:
    """
    Get file manager for current episode.
    
    If episode_id is not provided, tries to get from environment variable.
    """
    if episode_id is None:
        episode_id = os.environ.get('WDF_EPISODE_ID', 'default')
    
    return EpisodeFileManager(episode_id)