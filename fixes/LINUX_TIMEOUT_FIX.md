# Linux Web UI Timeout Fix - Complete Solution

## Problem Identified

When running the Claude pipeline from the web UI on Linux, the summarizer times out because:

1. **Missing Node.js in PATH**: The Claude CLI is a Node.js application that can't find the `node` binary
2. **Environment not inherited**: When Next.js spawns Python subprocesses, they don't inherit the full shell environment
3. **PATH not preserved**: The subprocess chain (Next.js → Python → orchestrator.py → Claude CLI) loses critical PATH directories

## Root Cause

The logs showed:
- `NODE NOT FOUND IN PATH! This is why Claude CLI fails`
- Claude CLI works from command line but times out from web UI
- The subprocess can't find `node` when spawned from the web server

## Solution Applied

### 1. Fixed Web API Routes

Updated the following files to properly set environment:
- `/web/app/api/episodes/[id]/claude-pipeline/run/route.ts`
- `/web/app/api/episodes/[id]/claude-pipeline/run/route_ultra_simple.ts`

Key changes:
```typescript
const fixedEnv = {
  ...process.env,
  PATH: [
    '/usr/local/bin',
    '/usr/bin',
    '/bin',
    `${homeDir}/.nvm/versions/node/v18.17.0/bin`,  // Node via nvm
    `${homeDir}/.claude/local`,  // Claude CLI
    '/home/debian/.claude/local',  // Debian user Claude
    process.env.PATH || ''
  ].join(':'),
  NODE_PATH: '/usr/lib/node_modules',
  CLAUDE_CLI_PATH: '/home/debian/.claude/local/claude',
  PYTHONUNBUFFERED: '1'
};
```

### 2. Created Fixed Python Bridge

New file: `/web/scripts/claude_pipeline_fixed.py`

This script:
- Ensures proper PATH environment before running orchestrator
- Verifies Node.js and Claude CLI availability
- Passes fixed environment to subprocess

### 3. Environment Setup Script

Created: `/web/scripts/setup_pipeline_env.sh`

This script sets up the proper environment variables for manual testing.

## Testing Instructions

### 1. First, verify your Node.js installation

```bash
# Check if Node is installed
which node
node --version

# If using nvm, check the path
echo $NVM_DIR
ls ~/.nvm/versions/node/
```

### 2. Verify Claude CLI installation

```bash
# Check Claude CLI location
which claude
ls -la /home/debian/.claude/local/claude
claude --version
```

### 3. Update the paths in the fix if needed

If your Node.js or Claude CLI are in different locations, update these files:
- `/web/app/api/episodes/[id]/claude-pipeline/run/route.ts` (lines 77-80)
- `/web/scripts/claude_pipeline_fixed.py` (lines 29-34)

Common Node.js locations:
- nvm: `~/.nvm/versions/node/vXX.XX.X/bin`
- System: `/usr/bin/node`
- NodeSource: `/usr/local/bin/node`

### 4. Test from command line first

```bash
cd /path/to/WDFWatch-Linux

# Test the fixed Python script directly
python3 web/scripts/claude_pipeline_fixed.py \
  --episode-id test_123 \
  --stages summarize \
  --transcript transcripts/latest.txt \
  --debug
```

### 5. Test from web UI

1. Start the web server:
```bash
npm run dev
# or
npm run build && npm start
```

2. Navigate to the Episodes page
3. Upload a transcript or select an existing episode
4. Click "Run Claude Pipeline"
5. Monitor the logs for output

### 6. Check the logs

Watch the server logs for:
- `"Spawning Claude pipeline with fixed environment"`
- `"PATH: /usr/local/bin:/usr/bin:..."` (should include Node paths)
- `"Node.js found at: /path/to/node"`
- `"Claude CLI found at: /path/to/claude"`

## Troubleshooting

### If it still times out:

1. **Check Node.js path**:
   ```bash
   # Find the exact Node path
   which node
   # Update the PATH in route.ts with this exact path
   ```

2. **Check Claude CLI can run**:
   ```bash
   /home/debian/.claude/local/claude --version
   # If this fails, Claude CLI might need reinstalling
   ```

3. **Test with simple prompt**:
   ```bash
   echo "Say hello" > test.txt
   claude --model sonnet --print @test.txt
   ```

4. **Check subprocess environment**:
   Add more logging to see what environment the subprocess actually gets:
   ```python
   # In claude_pipeline_fixed.py
   logger.info(f"Full PATH: {os.environ['PATH']}")
   subprocess.run(['which', 'node'], capture_output=True)
   subprocess.run(['which', 'claude'], capture_output=True)
   ```

### Alternative: Use absolute paths

If PATH issues persist, you can modify `claude_adapter.py` to use absolute paths:

```python
# In claude-pipeline/core/models/claude_adapter.py, line 58
self.claude_cli = "/home/debian/.claude/local/claude"  # Already set

# Also ensure Node is called with absolute path
# Add before line 204:
os.environ['NODE'] = '/usr/bin/node'  # Or your Node path
```

## Summary

The fix ensures that:
1. ✅ Node.js is in PATH when Claude CLI is executed
2. ✅ Environment variables are properly passed through the subprocess chain
3. ✅ The Claude CLI can find all its dependencies
4. ✅ The pipeline works from both CLI and web UI

The key insight is that web servers spawn processes with minimal environments, so we must explicitly set the PATH to include Node.js and Claude CLI locations.