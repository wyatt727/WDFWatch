#!/bin/bash
# Run pipeline on host instead of in Docker container
# This script is called by the web container

# Load environment
cd /home/debian/Tools/WDFWatch
source venv/bin/activate

# Get arguments
EPISODE_ID=$1
STAGE=$2

echo "Running pipeline on host for episode $EPISODE_ID, stage $STAGE"

# Set Python path
export PYTHONPATH=/home/debian/Tools/WDFWatch/claude-pipeline:$PYTHONPATH

# Run the appropriate stage
case "$STAGE" in
  "summarize")
    cd claude-pipeline
    python3 -m stages.summarize --episode-id "$EPISODE_ID"
    ;;
  "classify")
    cd claude-pipeline
    python3 -m stages.classify --episode-id "$EPISODE_ID"
    ;;
  "respond")
    cd claude-pipeline
    python3 -m stages.respond --episode-id "$EPISODE_ID"
    ;;
  "moderate")
    cd claude-pipeline
    python3 -m stages.moderate --episode-id "$EPISODE_ID"
    ;;
  "full")
    cd claude-pipeline
    python3 orchestrator.py --episode-id "$EPISODE_ID" --stages full
    ;;
  *)
    echo "Unknown stage: $STAGE"
    exit 1
    ;;
esac
