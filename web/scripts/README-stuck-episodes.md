# Stuck Episodes Migration Guide

## Problem
Episodes that started processing before the process tracking system was implemented can get stuck in "processing" status without any actual running processes. These episodes cannot be deleted through the normal UI flow.

## Solutions

### Option 1: Web API (Recommended)

**Check for stuck episodes:**
```bash
curl "http://localhost:3000/api/episodes/reset-stuck?olderThanHours=24"
```

**Reset stuck episodes (dry run first):**
```bash
curl -X POST "http://localhost:3000/api/episodes/reset-stuck" \
  -H "Content-Type: application/json" \
  -d '{"dryRun": true, "olderThanHours": 24}'
```

**Actually reset them:**
```bash
curl -X POST "http://localhost:3000/api/episodes/reset-stuck" \
  -H "Content-Type: application/json" \
  -d '{"dryRun": false, "olderThanHours": 24}'
```

### Option 2: Node.js Script

**Install dependencies:**
```bash
cd web
npm install dotenv  # If not already installed
```

**Run the migration script:**
```bash
# From the web directory
cd web

# Dry run to see what would be reset
npx tsx scripts/reset-stuck-episodes.ts --dry-run

# Actually reset episodes older than 24 hours
npx tsx scripts/reset-stuck-episodes.ts

# Reset episodes older than 1 hour
npx tsx scripts/reset-stuck-episodes.ts --older-than-hours=1
```

### Option 3: Direct Database (If needed)

```sql
-- Check for stuck episodes
SELECT id, title, status, updated_at,
       EXTRACT(EPOCH FROM (NOW() - updated_at))/3600 as hours_stuck
FROM podcast_episodes 
WHERE status = 'processing'
ORDER BY updated_at ASC;

-- Reset them to 'ready' status
UPDATE podcast_episodes 
SET status = 'ready', updated_at = NOW()
WHERE status = 'processing' 
  AND updated_at < NOW() - INTERVAL '24 hours';
```

## What the migration does

1. **Finds stuck episodes** - Episodes in 'processing' status without running processes
2. **Age check** - Only resets episodes older than specified threshold (default 24 hours)
3. **Safety check** - Verifies no actual processes are running for the episode
4. **Reset status** - Changes status from 'processing' to 'ready'
5. **Audit logging** - Records all changes for traceability
6. **Real-time updates** - Emits SSE events to update the UI

## After migration

- Episodes will show as "ready" status in the UI
- You can now delete them normally through the web interface
- You can re-run the pipeline if needed
- All future episodes use the new process tracking system

## Prevention

The new process tracking system prevents this issue by:
- Tracking all running processes in memory
- Graceful process termination on episode deletion
- Automatic cleanup when processes exit
- Stuck episode detection and handling

## Troubleshooting

**If reset doesn't work:**
1. Check logs for error messages
2. Verify database connectivity
3. Try direct database approach as fallback
4. Contact admin if episodes are critical

**If episodes keep getting stuck:**
1. Check for long-running processes not being tracked
2. Verify process tracker is working correctly
3. Check system resources (memory, disk space)
4. Review pipeline logs for hanging operations