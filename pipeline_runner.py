#!/usr/bin/env python3
"""
Pipeline Runner Service
Monitors for pipeline job requests from the web container and executes them on the host.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
import fcntl

# Job directory where web container writes requests
JOB_DIR = Path("/home/debian/Tools/WDFWatch/claude-pipeline/jobs")
JOB_DIR.mkdir(exist_ok=True)

def fix_episode_permissions(episode_id: str):
    """Fix ownership and permissions for episode directory."""
    try:
        episode_dir = f"/home/debian/Tools/WDFWatch/claude-pipeline/episodes/{episode_id}"

        # Fix ownership to debian:nodejs
        subprocess.run(["sudo", "chown", "-R", "debian:nodejs", episode_dir], check=False)

        # Fix group permissions
        subprocess.run(["sudo", "chmod", "-R", "g+w", episode_dir], check=False)

        print(f"Fixed permissions for episode: {episode_id}")
    except Exception as e:
        print(f"Warning: Could not fix permissions for {episode_id}: {e}")

def execute_pipeline(episode_id: str, stage: str):
    """Execute a pipeline stage on the host."""
    print(f"Executing pipeline: episode={episode_id}, stage={stage}")

    # First, fix permissions for the episode directory
    fix_episode_permissions(episode_id)

    # Activate venv and run the appropriate stage
    venv_path = "/home/debian/Tools/WDFWatch/venv/bin/activate"
    pipeline_dir = "/home/debian/Tools/WDFWatch/claude-pipeline"

    # All stages go through the orchestrator
    cmd = f"source {venv_path} && cd {pipeline_dir} && python3 orchestrator.py --episode-id {episode_id} --stages {stage}"

    if stage not in ["summarize", "classify", "respond", "moderate", "full"]:
        print(f"Unknown stage: {stage}")
        return False
    
    # Execute the command with timeout
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               executable='/bin/bash',
                               env={**os.environ, 'PYTHONPATH': pipeline_dir},
                               timeout=300)  # 5 minute timeout
        print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Errors: {result.stderr}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"Pipeline execution timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"Error executing pipeline: {e}")
        return False

def monitor_jobs():
    """Monitor for new job files and execute them."""
    print(f"Monitoring {JOB_DIR} for pipeline jobs...")
    
    while True:
        try:
            # Look for job files
            for job_file in JOB_DIR.glob("job_*.json"):
                try:
                    # Try to acquire exclusive lock (non-blocking)
                    with open(job_file, 'r') as f:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        
                        # Read job data
                        job_data = json.load(f)
                        episode_id = job_data.get('episode_id')
                        stage = job_data.get('stage')
                        
                        if episode_id and stage:
                            # Execute the pipeline
                            success = execute_pipeline(episode_id, stage)
                            
                            # Write result file
                            result_file = job_file.with_suffix('.result')
                            with open(result_file, 'w') as rf:
                                json.dump({'success': success}, rf)
                        
                        # Remove job file after processing
                        job_file.unlink()
                        
                except (IOError, OSError):
                    # File is locked, skip it
                    continue
                except Exception as e:
                    print(f"Error processing job {job_file}: {e}")
                    # Remove problematic job file
                    try:
                        job_file.unlink()
                    except:
                        pass
            
            # Sleep briefly before checking again
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nShutting down pipeline runner...")
            break
        except Exception as e:
            print(f"Monitor error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitor_jobs()