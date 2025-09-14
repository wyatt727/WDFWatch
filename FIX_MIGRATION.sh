#!/bin/bash

# Fix Migration Script for New Server
# Run this on the NEW server after extracting migration package

echo "=== WDFWatch Migration Fix Script ==="
echo ""

# Step 1: Create fresh Python virtual environment
echo "Step 1: Creating fresh virtual environment..."
rm -rf venv
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install poetry

# Step 2: Install dependencies
echo "Step 2: Installing Python dependencies..."
./venv/bin/poetry install

# Step 3: Fix database - create proper constraints
echo "Step 3: Fixing database schema..."
docker exec wdfwatch-postgres psql -U wdfwatch -d wdfwatch <<'EOF'
-- Add missing unique constraint for episodes
ALTER TABLE podcast_episodes DROP CONSTRAINT IF EXISTS podcast_episodes_episode_dir_key;
ALTER TABLE podcast_episodes ADD CONSTRAINT podcast_episodes_episode_dir_key UNIQUE (episode_dir);

-- Clear any partial data
TRUNCATE TABLE podcast_episodes CASCADE;
TRUNCATE TABLE keywords CASCADE;
TRUNCATE TABLE tweet_queue CASCADE;
TRUNCATE TABLE draft_replies CASCADE;
-- Keep tweets since they imported successfully
EOF

# Step 4: Import episodes from JSON files
echo "Step 4: Importing episode data..."
cat > /tmp/import_episodes.py <<'PYTHON'
#!/usr/bin/env python3
import json
import os
import psycopg2
from datetime import datetime

# Database connection
conn = psycopg2.connect(
    host="localhost",
    port=5433,
    database="wdfwatch",
    user="wdfwatch",
    password="wdfwatch123"
)
cur = conn.cursor()

# Import episodes from directories
episodes_dir = "claude-pipeline/episodes"
if os.path.exists(episodes_dir):
    for episode_dir in os.listdir(episodes_dir):
        episode_path = os.path.join(episodes_dir, episode_dir)
        if os.path.isdir(episode_path):
            print(f"Importing episode: {episode_dir}")

            # Read summary if exists
            summary_file = os.path.join(episode_path, "summary.md")
            summary = ""
            if os.path.exists(summary_file):
                with open(summary_file, 'r') as f:
                    summary = f.read()

            # Read transcript if exists
            transcript_file = os.path.join(episode_path, "transcript.txt")
            transcript = ""
            if os.path.exists(transcript_file):
                with open(transcript_file, 'r') as f:
                    transcript = f.read()[:5000]  # First 5000 chars

            # Extract title from directory name
            title = episode_dir.replace('_', ' ').replace('episode ', 'Episode ').title()

            try:
                cur.execute("""
                    INSERT INTO podcast_episodes
                    (episode_dir, title, description, transcript_summary, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, 'processed', NOW(), NOW())
                    ON CONFLICT (episode_dir) DO UPDATE
                    SET title = EXCLUDED.title,
                        transcript_summary = EXCLUDED.transcript_summary,
                        updated_at = NOW()
                """, (episode_dir, title, transcript[:500], summary[:2000]))

                # Import keywords for this episode
                keywords_file = os.path.join(episode_path, "keywords.json")
                if os.path.exists(keywords_file):
                    with open(keywords_file, 'r') as f:
                        keywords = json.load(f)
                        for keyword in keywords[:20]:  # Limit to 20 keywords
                            cur.execute("""
                                INSERT INTO keywords (keyword, relevance_score, created_at, updated_at)
                                VALUES (%s, 1.0, NOW(), NOW())
                                ON CONFLICT (keyword) DO NOTHING
                            """, (keyword,))

                conn.commit()
                print(f"  ✓ Imported {episode_dir}")
            except Exception as e:
                print(f"  ✗ Failed {episode_dir}: {e}")
                conn.rollback()

print(f"\nImported {cur.rowcount} episodes")
cur.close()
conn.close()
PYTHON

python3 /tmp/import_episodes.py

# Step 5: Verify migration
echo ""
echo "Step 5: Verifying migration..."
docker exec wdfwatch-postgres psql -U wdfwatch -d wdfwatch -t <<'EOF'
SELECT 'Episodes: ' || COUNT(*) FROM podcast_episodes;
SELECT 'Tweets: ' || COUNT(*) FROM tweets;
SELECT 'Keywords: ' || COUNT(*) FROM keywords;
EOF

echo ""
echo "=== Migration Fix Complete ==="
echo ""
echo "Next steps:"
echo "1. Start web UI: cd web && npm run dev"
echo "2. Access at: http://localhost:8888"
echo "3. Run pipeline: ./venv/bin/python main.py"