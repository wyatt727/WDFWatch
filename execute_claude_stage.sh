#!/bin/bash

# Host-side Claude Pipeline Executor
# This script runs on the host system with proper permissions and environment

set -e

# Parse arguments
STAGE=""
EPISODE_ID=""
EPISODE_DB_ID=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --stage)
      STAGE="$2"
      shift 2
      ;;
    --episode-id)
      EPISODE_ID="$2"
      shift 2
      ;;
    --episode-db-id)
      EPISODE_DB_ID="$2"
      shift 2
      ;;
    *)
      echo "Unknown parameter: $1"
      exit 1
      ;;
  esac
done

if [[ -z "$STAGE" || -z "$EPISODE_ID" ]]; then
    echo "Error: --stage and --episode-id are required"
    exit 1
fi

echo "[$(date)] Claude Pipeline Executor: stage=$STAGE, episode=$EPISODE_ID, db_id=$EPISODE_DB_ID"

# Fix permissions for episode directory FIRST
EPISODE_DIR="/home/debian/Tools/WDFWatch/claude-pipeline/episodes/$EPISODE_ID"
if [[ -d "$EPISODE_DIR" ]]; then
    echo "[$(date)] Fixing permissions for $EPISODE_DIR"
    sudo chown -R debian:nodejs "$EPISODE_DIR" 2>/dev/null || true
    sudo chmod -R g+w "$EPISODE_DIR" 2>/dev/null || true
    echo "[$(date)] Permissions fixed"
else
    echo "[$(date)] Warning: Episode directory $EPISODE_DIR does not exist"
fi

# Set up environment
export PYTHONPATH="/home/debian/Tools/WDFWatch/claude-pipeline:/home/debian/Tools/WDFWatch"
export WDF_WEB_MODE="true"
export WDF_EPISODE_ID="$EPISODE_DB_ID"

# Change to project directory
cd /home/debian/Tools/WDFWatch/claude-pipeline

# Activate virtual environment if it exists
if [[ -f "/home/debian/Tools/WDFWatch/venv/bin/activate" ]]; then
    echo "[$(date)] Activating virtual environment"
    source /home/debian/Tools/WDFWatch/venv/bin/activate
fi

# Execute Claude orchestrator
echo "[$(date)] Executing Claude orchestrator: python3 orchestrator.py --episode-id $EPISODE_ID --stages $STAGE"

python3 orchestrator.py --episode-id "$EPISODE_ID" --stages "$STAGE"

RESULT=$?

if [[ $RESULT -eq 0 ]]; then
    echo "[$(date)] Claude pipeline completed successfully"
else
    echo "[$(date)] Claude pipeline failed with exit code $RESULT"
fi

exit $RESULT