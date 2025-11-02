"""Compat shim for the legacy ``src.wdf`` package.

Episode file management now lives in ``backend.api.app.services.episodes_repo``.
This module re-exports the shared implementation so remaining legacy imports
continue to function while we complete the migration away from ``src.wdf``.
"""

from backend.api.app.services.episodes_repo import (  # noqa: F401
    CLAUDE_FILE_MAP,
    DEFAULT_OUTPUT_KEYS,
    INPUT_KEYS,
    EpisodeFileManager,
    EpisodesRepository,
    episodes_repo,
    get_episode_file_manager,
)

__all__ = [
    "CLAUDE_FILE_MAP",
    "DEFAULT_OUTPUT_KEYS",
    "INPUT_KEYS",
    "EpisodeFileManager",
    "EpisodesRepository",
    "episodes_repo",
    "get_episode_file_manager",
]


