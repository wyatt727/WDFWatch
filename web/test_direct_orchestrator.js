#!/usr/bin/env node
/**
 * Test spawning orchestrator directly from Node.js
 * This isolates the subprocess spawning from the Next.js API layer
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

console.log('[TEST] Direct Orchestrator Test Starting');
console.log('[TEST] Time:', new Date().toISOString());
console.log('[TEST] CWD:', process.cwd());
console.log('[TEST] Node version:', process.version);

// Configuration
const episodeId = 'it-wasnt-the-last';
const stage = 'summarize';
const projectRoot = path.join(__dirname, '..');
const orchestratorPath = path.join(projectRoot, 'claude-pipeline', 'orchestrator.py');
const venvPythonPath = path.join(projectRoot, 'venv', 'bin', 'python');
const pythonPath = fs.existsSync(venvPythonPath) ? venvPythonPath : 'python3';

console.log('[TEST] Python path:', pythonPath);
console.log('[TEST] Orchestrator path:', orchestratorPath);
console.log('[TEST] Episode ID:', episodeId);
console.log('[TEST] Stage:', stage);

// Check if files exist
console.log('[TEST] Python exists?', fs.existsSync(pythonPath));
console.log('[TEST] Orchestrator exists?', fs.existsSync(orchestratorPath));

// Build command
const args = [
  orchestratorPath,
  '--episode-id', episodeId,
  '--stages', stage
];

// Build environment
const env = {
  ...process.env,
  PATH: '/usr/bin:/home/debian/.claude/local:/home/debian/.npm-global/bin:/home/debian/.local/bin:/usr/local/bin:/bin:/usr/games',
  PYTHONPATH: path.join(projectRoot, 'claude-pipeline'),
  PYTHON_PATH: pythonPath,
  WDF_WEB_MODE: 'true',
  WDF_EPISODE_ID: '46',
  WEB_URL: 'http://localhost:8888',
  DATABASE_URL: 'postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch',
  NODE_PATH: '/usr/lib/node_modules',
  CLAUDE_CLI_PATH: '/home/debian/.claude/local/claude',
  PYTHONUNBUFFERED: '1',
  HOME: process.env.HOME || '/home/debian',
  USER: process.env.USER || 'debian',
  SHELL: process.env.SHELL || '/usr/bin/zsh',
  TERM: process.env.TERM || 'xterm',
  TMPDIR: process.env.TMPDIR || '/tmp',
};

console.log('[TEST] Environment PATH:', env.PATH);
console.log('[TEST] Starting subprocess...');

// Spawn process
const startTime = Date.now();
const child = spawn(pythonPath, args, {
  cwd: projectRoot,
  env: env,
  stdio: ['pipe', 'pipe', 'pipe']
});

console.log('[TEST] Process spawned with PID:', child.pid);

// Monitor stdout
child.stdout.on('data', (data) => {
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  process.stdout.write(`[${elapsed}s STDOUT] ${data}`);
});

// Monitor stderr
child.stderr.on('data', (data) => {
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  process.stderr.write(`[${elapsed}s STDERR] ${data}`);
});

// Monitor process state every 5 seconds
const monitor = setInterval(() => {
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`[TEST ${elapsed}s] Process still running - PID: ${child.pid}, killed: ${child.killed}, exitCode: ${child.exitCode}`);
}, 5000);

// Handle close
child.on('close', (code, signal) => {
  clearInterval(monitor);
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`[TEST] Process closed after ${elapsed}s - Code: ${code}, Signal: ${signal}`);
  process.exit(code || 0);
});

// Handle error
child.on('error', (err) => {
  clearInterval(monitor);
  console.error('[TEST] Process error:', err);
  process.exit(1);
});

// Handle timeout (10 minutes)
setTimeout(() => {
  console.error('[TEST] Timeout after 10 minutes - killing process');
  child.kill('SIGTERM');
  setTimeout(() => {
    child.kill('SIGKILL');
    process.exit(1);
  }, 5000);
}, 600000);