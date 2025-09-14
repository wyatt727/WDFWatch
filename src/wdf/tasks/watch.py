"""
Transcript watch task

This module watches for changes to the transcript file and triggers the pipeline
when a new transcript is detected.
"""

import hashlib
import logging
import time
from pathlib import Path

import structlog
from prefect import flow
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..settings import settings

# Set up structured logging
logger = structlog.get_logger()

# Path to watch
TRANSCRIPT_PATH = Path(settings.transcript_dir) / "latest.txt"


class TranscriptHandler(FileSystemEventHandler):
    """Watchdog handler for transcript file changes"""
    
    def __init__(self, flow_runner):
        """Initialize with a function to call when the transcript changes"""
        self.flow_runner = flow_runner
        self.last_modified = None
        
    def on_modified(self, event):
        """Called when the transcript file is modified"""
        if not event.is_directory and Path(event.src_path).resolve() == TRANSCRIPT_PATH.resolve():
            # Debounce multiple events
            current_time = time.time()
            if self.last_modified and current_time - self.last_modified < 2:
                return
                
            self.last_modified = current_time
            
            # Calculate SHA-256 of the file for run_id
            try:
                content = TRANSCRIPT_PATH.read_text(encoding="utf-8")
                run_id = hashlib.sha256(content.encode()).hexdigest()[:10]
                
                logger.info(
                    "Transcript changed, triggering flow",
                    path=str(TRANSCRIPT_PATH),
                    run_id=run_id
                )
                
                # Trigger the flow with the run_id
                self.flow_runner(run_id)
                
            except Exception as e:
                logger.error(
                    "Error processing transcript change",
                    path=str(TRANSCRIPT_PATH),
                    error=str(e)
                )


def trigger_flow(run_id: str):
    """Trigger the Prefect flow with the given run_id"""
    # This will be implemented when we create the flow.py module
    from ..flow import wdf_pipeline_flow
    
    logger.info("Triggering flow", run_id=run_id)
    wdf_pipeline_flow.submit(run_id=run_id)


def run(blocking: bool = True):
    """
    Start watching for transcript changes
    
    Args:
        blocking: If True, run in the foreground and block until interrupted
    """
    logger.info("Starting transcript watcher", path=str(TRANSCRIPT_PATH))
    
    # Create an observer
    observer = Observer()
    handler = TranscriptHandler(trigger_flow)
    
    # Schedule the observer to watch the transcript directory
    observer.schedule(handler, str(TRANSCRIPT_PATH.parent), recursive=False)
    observer.start()
    
    if blocking:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping transcript watcher")
            observer.stop()
        observer.join()
    
    return observer  # Return the observer so it can be stopped later if not blocking


if __name__ == "__main__":
    # Configure logging when run directly
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    # Run the watcher
    run() 