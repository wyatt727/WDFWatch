#!/usr/bin/env python3
"""
Job Status Monitor
Monitors pipeline job result files and updates database episode status.
This bridges the gap between the pipeline runner and web UI database.
"""

import json
import os
import time
import subprocess
from pathlib import Path
from typing import Dict, Optional

# Job directory where result files are written
JOB_DIR = Path("/home/debian/Tools/WDFWatch/claude-pipeline/jobs")
PROCESSED_DIR = JOB_DIR / "processed"
PROCESSED_DIR.mkdir(exist_ok=True)

def update_episode_status(episode_title: str, status: str) -> bool:
    """Update episode status in PostgreSQL database."""
    try:
        # Use docker exec to run psql command
        cmd = [
            "docker", "exec", "wdfwatch-postgres",
            "psql", "-U", "wdfwatch", "-d", "wdfwatch",
            "-c", f"UPDATE podcast_episodes SET status = '{status}', updated_at = NOW() WHERE title = '{episode_title}';"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            print(f"✅ Updated episode '{episode_title}' status to '{status}'")
            return True
        else:
            print(f"❌ Failed to update episode '{episode_title}': {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error updating database: {e}")
        return False

def get_episode_title_from_id(episode_id: str) -> Optional[str]:
    """Get episode title from episode ID."""
    try:
        # Try to find the episode in database by matching directory name pattern
        cmd = [
            "docker", "exec", "wdfwatch-postgres",
            "psql", "-U", "wdfwatch", "-d", "wdfwatch", "-t", "-c",
            f"SELECT title FROM podcast_episodes WHERE lower(replace(title, ' ', '-')) LIKE '%{episode_id.lower().replace('_', '-')}%';"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and result.stdout.strip():
            title = result.stdout.strip()
            return title
        else:
            print(f"⚠️ Could not find episode title for ID: {episode_id}")
            return None

    except Exception as e:
        print(f"❌ Error querying database: {e}")
        return None

def monitor_job_results():
    """Monitor for new job result files and update episode status."""
    print(f"🔍 Monitoring {JOB_DIR} for completed pipeline jobs...")

    while True:
        try:
            # Look for result files
            for result_file in JOB_DIR.glob("job_*.result"):
                try:
                    print(f"📄 Found result file: {result_file.name}")

                    # Read result data
                    with open(result_file, 'r') as f:
                        result_data = json.load(f)

                    # Check if job was successful
                    if result_data.get('success', False):
                        # Try to extract episode ID from job file name or find corresponding job file
                        job_name = result_file.stem  # Remove .result extension
                        job_file = result_file.with_suffix('.json')

                        episode_id = None

                        # If original job file still exists, read episode_id from it
                        if job_file.exists():
                            try:
                                with open(job_file, 'r') as f:
                                    job_data = json.load(f)
                                    episode_id = job_data.get('episode_id')
                            except Exception as e:
                                print(f"⚠️ Could not read job file {job_file}: {e}")

                        # If we couldn't get episode_id from job file, try to parse from filename
                        if not episode_id:
                            # Look for patterns like job_1757863815183_xo8soq6oom.result
                            # We'll need to implement episode ID extraction logic here
                            print(f"⚠️ Could not determine episode_id from {result_file.name}")
                            # Move to processed to avoid reprocessing
                            processed_file = PROCESSED_DIR / result_file.name
                            result_file.rename(processed_file)
                            continue

                        # Get episode title from ID
                        episode_title = get_episode_title_from_id(episode_id)

                        if episode_title:
                            # Update database status
                            if update_episode_status(episode_title, 'processed'):
                                print(f"✅ Successfully processed job for episode: {episode_title}")
                            else:
                                print(f"❌ Failed to update status for episode: {episode_title}")
                        else:
                            print(f"⚠️ Could not find episode title for ID: {episode_id}")

                    else:
                        print(f"❌ Job failed: {result_file.name}")

                    # Move result file to processed directory to avoid reprocessing
                    processed_file = PROCESSED_DIR / result_file.name
                    result_file.rename(processed_file)

                except Exception as e:
                    print(f"❌ Error processing result file {result_file}: {e}")
                    # Move problematic file to processed directory
                    try:
                        processed_file = PROCESSED_DIR / result_file.name
                        result_file.rename(processed_file)
                    except:
                        pass

            # Sleep briefly before checking again
            time.sleep(2)

        except KeyboardInterrupt:
            print("\n🛑 Shutting down job status monitor...")
            break
        except Exception as e:
            print(f"❌ Monitor error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitor_job_results()