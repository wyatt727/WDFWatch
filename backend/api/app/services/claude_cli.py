"""
Claude CLI invocation service.
Provides standardized interface for calling Claude CLI with proper error handling.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)


class ClaudeCLIService:
    """Service for invoking Claude CLI."""
    
    def __init__(self):
        """Initialize Claude CLI service."""
        self.claude_cli = Path(settings.CLAUDE_CLI_PATH)
        self.timeout = settings.CLAUDE_TIMEOUT
    
    def invoke(
        self,
        prompt: str,
        context_files: Optional[list[Path]] = None,
        mode: str = "default",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        cwd: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Invoke Claude CLI with given prompt and context.
        
        Args:
            prompt: Prompt text
            context_files: List of context file paths to include
            mode: Mode (default, respond, classify, etc.)
            temperature: Temperature setting
            max_tokens: Maximum tokens
            cwd: Working directory for command
            
        Returns:
            Dictionary with response and metadata
        """
        if not self.claude_cli.exists():
            raise FileNotFoundError(f"Claude CLI not found at {self.claude_cli}")
        
        # Build command
        cmd = [str(self.claude_cli)]
        
        # Add context files if provided
        if context_files:
            for ctx_file in context_files:
                if ctx_file.exists():
                    cmd.extend(["--context", str(ctx_file)])
        
        # Add prompt via stdin
        logger.debug(f"Invoking Claude CLI: {cmd}")
        logger.debug(f"Prompt length: {len(prompt)} chars")
        
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout,
                cwd=str(cwd) if cwd else None,
            )
            
            if result.returncode != 0:
                error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
                logger.error(f"Claude CLI failed: {error_msg}")
                raise RuntimeError(f"Claude CLI invocation failed: {error_msg}")
            
            return {
                "success": True,
                "response": result.stdout.strip(),
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Claude CLI timed out after {self.timeout}s")
            raise RuntimeError(f"Claude CLI invocation timed out after {self.timeout}s")
        except Exception as e:
            logger.error(f"Claude CLI error: {e}", exc_info=True)
            raise


# Global instance
claude_cli = ClaudeCLIService()

