// Test using 'script' command to provide PTY for claude execution
const { exec } = require('child_process');

async function testPTYSolution() {
  console.log('Testing PTY Solution: Using script command to provide terminal');
  console.log('Episode: it-wasnt-the-last');
  console.log('Stage: summarization');
  console.log('Time:', new Date().toISOString());
  console.log('----------------------------');

  // Use 'script' command to provide a PTY
  // -q: quiet mode (no start/stop messages)
  // -c: command to run
  // /dev/null: don't save typescript file
  const shellCommand = `
    source ~/.zshrc && \
    cd /home/debian/Tools/WDFWatch && \
    script -q -c "/home/debian/Tools/WDFWatch/venv/bin/python claude-pipeline/orchestrator.py --episode-id it-wasnt-the-last --stages summarize" /dev/null
  `.trim();

  console.log('=== PTY SOLUTION COMMAND ===');
  console.log('Using script to provide PTY');
  console.log('Command:', shellCommand);
  console.log('============================');

  const execOptions = {
    shell: '/bin/zsh',
    timeout: 140000, // 140 seconds max
    maxBuffer: 10 * 1024 * 1024, // 10MB buffer
    env: {
      HOME: process.env.HOME || '/home/debian',
      USER: process.env.USER || 'debian',
      PATH: process.env.PATH || '/home/debian/.claude/local:/home/debian/.npm-global/bin:/home/debian/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/games',
      PYTHONUNBUFFERED: '1',
      // Claude Code environment variables
      CLAUDECODE: '1',
      CLAUDE_CODE_ENTRYPOINT: 'cli',
      // Terminal-related
      TERM: 'xterm-256color',
      LANG: 'C.UTF-8',
    }
  };

  return new Promise((resolve, reject) => {
    const startTime = Date.now();

    const childProcess = exec(shellCommand, execOptions, (error, stdout, stderr) => {
      const duration = Date.now() - startTime;
      const timestamp = new Date().toISOString();

      if (error) {
        console.error(`[${timestamp}] [PTY ERROR] After ${duration}ms:`, error.message);
        if (stderr) console.error(`[${timestamp}] [PTY STDERR]`, stderr);
        reject(error);
      } else {
        console.log(`[${timestamp}] [PTY SUCCESS] Completed in ${duration}ms`);
        if (stdout) {
          const lines = stdout.split('\n').slice(-10); // Last 10 lines
          console.log(`[${timestamp}] [PTY OUTPUT (last 10 lines)]:`);
          lines.forEach(line => console.log(`  ${line}`));
        }
        resolve({ success: true, duration, output: stdout });
      }
    });

    console.log('Process started with PID:', childProcess.pid);

    // Monitor progress
    let lastOutput = Date.now();

    if (childProcess.stdout) {
      childProcess.stdout.on('data', (data) => {
        lastOutput = Date.now();
        const output = data.toString();

        // Only show key progress indicators
        if (output.includes('HEARTBEAT') ||
            output.includes('FILE-BASED') ||
            output.includes('completed') ||
            output.includes('ERROR')) {
          console.log(`[PROGRESS] ${output.trim().substring(0, 100)}`);
        }
      });
    }

    // Check for stalls
    const stallChecker = setInterval(() => {
      const stallTime = Date.now() - lastOutput;
      if (stallTime > 30000) { // 30 seconds without output
        console.log(`[WARNING] No output for ${Math.round(stallTime/1000)}s`);
      }
    }, 10000);

    // Cleanup on completion
    childProcess.on('exit', () => {
      clearInterval(stallChecker);
    });
  });
}

// Run the test
testPTYSolution()
  .then(result => {
    console.log('✅ PTY Solution Test Successful!');
    console.log(`Completed in ${result.duration}ms`);
    process.exit(0);
  })
  .catch(error => {
    console.log('❌ PTY Solution Test Failed:', error.message);
    process.exit(1);
  });