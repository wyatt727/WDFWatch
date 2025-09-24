# WebUI Timeout Issue - Investigation and Solution

## Problem Statement
The WebUI pipeline execution for Claude episodes would consistently timeout after 180-600 seconds, while the exact same command worked perfectly from CLI, completing in 60-90 seconds.

## Investigation Process

### Initial Symptoms
- ✅ **CLI Execution**: Always successful (60-90 seconds)
- ❌ **WebUI Execution**: Always timeout (180-600 seconds)
- Process would hang at "=== STARTING FILE-BASED COMMUNICATION ==="
- Claude CLI subprocess never actually started processing

### Debugging Steps Taken

1. **Environment Variable Analysis**
   - Added CLAUDECODE=1 and CLAUDE_CODE_ENTRYPOINT=cli
   - Found CLI had 40+ env vars vs WebUI's minimal set
   - **Result**: Important but not sufficient

2. **Path and Binary Verification**
   - Confirmed claude binary location: `/home/debian/.claude/local/claude`
   - Added path to subprocess environment
   - **Result**: Binary was accessible but still hanging

3. **Timeout Adjustments**
   - Increased from 180s to 600s
   - **Result**: No improvement, just longer hangs

4. **Process Execution Method Changes**
   - Tried different Node.js spawn options
   - Used exec() instead of spawn()
   - **Result**: No improvement

5. **Comprehensive Python Testing**
   - Created `test_direct_python.py` with 8 different tests
   - Found key differences in process hierarchy and TTY status
   - **Critical Discovery**: WebUI processes had no controlling terminal

### Root Cause Analysis

The comprehensive Python tests revealed the smoking gun:

#### CLI Environment (Working)
```
SSH_TTY=/dev/pts/2
Has controlling terminal: True
Is session leader: False
Process started from terminal session
```

#### WebUI Environment (Failing)
```
SSH_TTY: NOT SET
Has controlling terminal: False
Is session leader: False
Process started from Node.js daemon
```

### The Solution: PTY (Pseudo-Terminal)

**Root Cause**: Claude CLI requires a pseudo-terminal (TTY) to function properly. Without it, the process hangs indefinitely waiting for terminal signals that never arrive.

**Fix**: Wrap the Python execution with the `script` command to provide a PTY:

```javascript
// Before (failing)
const shellCommand = `
  source ~/.zshrc && \
  cd /home/debian/Tools/WDFWatch && \
  /home/debian/Tools/WDFWatch/venv/bin/python claude-pipeline/orchestrator.py \
    --episode-id ${episodeDirName} \
    --stages ${claudeStage}
`.trim();

// After (working)
const pythonCommand = `/home/debian/Tools/WDFWatch/venv/bin/python claude-pipeline/orchestrator.py --episode-id ${episodeDirName} --stages ${claudeStage}`;

const shellCommand = `
  source ~/.zshrc && \
  cd /home/debian/Tools/WDFWatch && \
  script -q -c "${pythonCommand}" /dev/null
`.trim();
```

## Results

### Before Fix
- ❌ **WebUI**: Always timeout (180-600s)
- ❌ **User Experience**: Broken pipeline execution
- ❌ **Error Messages**: "Claude CLI timeout after X seconds"

### After Fix
- ✅ **WebUI**: Completes successfully (~72s)
- ✅ **User Experience**: Fully functional pipeline
- ✅ **Performance**: Same speed as CLI execution
- ✅ **Reliability**: No more timeouts

## Technical Details

### Why This Works
- `script -q -c "command" /dev/null` provides a pseudo-terminal to the command
- `-q`: Quiet mode (no start/stop messages)
- `-c`: Execute the command
- `/dev/null`: Don't save typescript output file
- The command now believes it's running in a terminal environment

### Environment Variables Still Important
The solution required both PTY provision AND proper environment:
```javascript
env: {
  HOME: process.env.HOME || '/home/debian',
  USER: process.env.USER || 'debian',
  WDF_WEB_MODE: 'true',
  WDF_EPISODE_ID: episodeId.toString(),
  WDF_RUN_ID: runId,
  DATABASE_URL: (process.env.DATABASE_URL || '').split('?')[0],
  WEB_URL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
  PYTHONUNBUFFERED: '1',
  CLAUDECODE: '1',
  CLAUDE_CODE_ENTRYPOINT: 'cli',
  TERM: 'xterm-256color',  // Terminal type
  LANG: 'C.UTF-8',         // Locale
}
```

### Timeout Adjusted
Updated timeout to 140 seconds as requested (was 600s).

## Files Modified

1. **`/home/debian/Tools/WDFWatch/web/app/api/episodes/[id]/pipeline/run/route.ts`**
   - Implemented PTY solution using `script` command
   - Updated timeout to 140 seconds
   - Added proper environment variables

## Lessons Learned

1. **TTY Dependencies**: Some CLI tools expect terminal environments even in non-interactive use
2. **Process Hierarchy Matters**: How a process is spawned affects its capabilities
3. **Environment Debugging**: Comprehensive environment comparison is crucial
4. **Test Isolation**: Direct Python testing helped isolate the Node.js subprocess issue
5. **PTY Solutions**: The `script` command is a powerful tool for providing TTY to headless processes

## Prevention

- Always test subprocess execution in both interactive and daemon contexts
- Consider TTY requirements when spawning CLI tools from web services
- Use tools like `script`, `pty.spawn()`, or similar when CLI tools need terminals
- Document TTY dependencies for future maintenance

## Impact

This fix completely resolves the WebUI timeout issue and makes the web interface fully functional for Claude pipeline execution. Users can now reliably run summarization and other pipeline stages from the web interface without timeouts.