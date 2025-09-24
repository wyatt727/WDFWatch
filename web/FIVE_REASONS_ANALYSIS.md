# 5 Reasons Why Claude Pipeline Works from CLI but Not from WebUI

## Summary of Evidence

### Working (CLI):
- Execution completes in 61-1202 seconds
- Has SSH_TTY=/dev/pts/2
- Has CLAUDECODE=1 and CLAUDE_CODE_ENTRYPOINT=cli
- Full environment with 30+ variables
- Is a direct child of terminal session

### Not Working (WebUI):
- Times out after 180-600 seconds
- No SSH_TTY
- Gets stuck at "=== STARTING FILE-BASED COMMUNICATION ==="
- Claude subprocess never actually produces output
- Minimal environment variables

## The 5 Most Likely Reasons (In Order of Likelihood)

### 1. **TTY/Terminal Requirement** (95% likelihood)
**Evidence:**
- CLI has `SSH_TTY=/dev/pts/2`
- WebUI has no TTY
- Python test shows: `Has controlling terminal: False` from web
- Claude Code may require interactive terminal for file operations

**Why this matters:**
Claude Code appears to check for terminal presence and may enter a different code path when no TTY is detected, possibly waiting for interactive input that never comes.

**Test:**
Use `pty.spawn()` or `script` command to provide pseudo-terminal

### 2. **File-Based I/O Blocking** (90% likelihood)
**Evidence:**
- Process always hangs at "=== STARTING FILE-BASED COMMUNICATION ==="
- Claude uses temporary files for large inputs
- File descriptors show non-TTY for stdout/stderr in web context

**Why this matters:**
Claude may be trying to read from stdin or write to stdout in a way that blocks when not connected to a terminal. The file-based communication might be waiting for EOF or terminal signals.

**Test:**
Explicitly close stdin or redirect to /dev/null

### 3. **Session/Process Group Leader Issue** (75% likelihood)
**Evidence:**
- CLI process: `Is session leader: False, Is process group leader: False`
- Web process spawned differently through Node.js layers
- Signal handling differences between contexts

**Why this matters:**
Claude may expect to be in a certain process group or session configuration. When spawned from web, it's in a different process hierarchy that might affect signal handling or job control.

**Test:**
Use `setsid` to create new session or modify process group

### 4. **Environment Variable Dependencies** (60% likelihood)
**Evidence:**
- CLI has 40+ env vars including:
  - `TERM=xterm-256color`
  - `LANG=C.UTF-8`
  - `LS_COLORS`, `LSCOLORS`
  - `MOTD_SHOWN=pam`
  - `XDG_SESSION_*` variables
- Web has minimal environment

**Why this matters:**
Claude might depend on terminal-related environment variables beyond just CLAUDECODE. The absence of TERM, LANG, or session variables might trigger different behavior.

**Test:**
Copy full environment from CLI session

### 5. **Node.js Process Inheritance Issue** (40% likelihood)
**Evidence:**
- Works when run directly from Python
- Fails when Python is spawned from Node.js
- Even with exec() and shell, still fails

**Why this matters:**
Node.js might be setting process attributes or file descriptor flags that persist even through exec(). The claude binary might detect it's running under Node.js and behave differently.

**Test:**
Use `env -i` to completely clear environment, or spawn through a clean shell script

## Recommended Solution Path

Based on this analysis, the most promising solutions are:

1. **Immediate Fix**: Add PTY support to the subprocess execution
2. **Alternative**: Use `script` command to wrap the execution
3. **Fallback**: Create a daemon/service that runs in proper terminal context

## Key Insight

The critical observation is that claude gets as far as starting file communication but then blocks indefinitely. This strongly suggests it's waiting for terminal input or signals that never arrive in the non-TTY context.