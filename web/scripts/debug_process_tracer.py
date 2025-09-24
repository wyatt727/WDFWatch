#!/usr/bin/env python3
"""
Process Execution Tracer - Debug tool to trace subprocess execution
Wraps the orchestrator to capture all timing and environment information
"""

import sys
import os
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime

def log(msg):
    """Log with timestamp"""
    timestamp = datetime.now().isoformat()
    print(f"[TRACER {timestamp}] {msg}", flush=True)

def capture_environment():
    """Capture current environment details"""
    return {
        'PATH': os.environ.get('PATH', ''),
        'PYTHONPATH': os.environ.get('PYTHONPATH', ''),
        'WDF_WEB_MODE': os.environ.get('WDF_WEB_MODE', ''),
        'NODE_PATH': os.environ.get('NODE_PATH', ''),
        'CLAUDE_CLI_PATH': os.environ.get('CLAUDE_CLI_PATH', ''),
        'cwd': os.getcwd(),
        'pid': os.getpid(),
        'ppid': os.getppid(),
        'uid': os.getuid(),
        'gid': os.getgid(),
    }

def check_command_availability():
    """Check if key commands are available"""
    commands = ['python', 'python3', 'node', 'claude', 'which']
    results = {}

    for cmd in commands:
        try:
            result = subprocess.run(['which', cmd], capture_output=True, text=True, timeout=1)
            results[cmd] = result.stdout.strip() if result.returncode == 0 else 'NOT FOUND'
        except Exception as e:
            results[cmd] = f'ERROR: {e}'

    return results

def run_orchestrator(args):
    """Run the orchestrator with detailed logging"""

    # Find orchestrator path
    orchestrator_path = Path(__file__).parent.parent.parent / 'claude-pipeline' / 'orchestrator.py'
    if not orchestrator_path.exists():
        log(f"ERROR: Orchestrator not found at {orchestrator_path}")
        return 1

    # Build command
    cmd = [sys.executable, str(orchestrator_path)] + args

    log(f"Command: {' '.join(cmd)}")
    log(f"Working directory: {os.getcwd()}")

    # Start timing
    start_time = time.time()

    # Create process with monitoring
    try:
        log("Creating subprocess...")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        log(f"Process started with PID: {process.pid}")

        # Monitor output in real-time
        import select
        import fcntl

        # Make stdout/stderr non-blocking
        if hasattr(select, 'poll'):
            # Set non-blocking mode
            for pipe in [process.stdout, process.stderr]:
                if pipe:
                    fd = pipe.fileno()
                    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Create poll object
            poll = select.poll()
            if process.stdout:
                poll.register(process.stdout, select.POLLIN)
            if process.stderr:
                poll.register(process.stderr, select.POLLIN)

            # Read output while process runs
            while process.poll() is None:
                ready = poll.poll(100)  # 100ms timeout

                for fd, event in ready:
                    if process.stdout and fd == process.stdout.fileno():
                        try:
                            line = process.stdout.readline()
                            if line:
                                print(f"[STDOUT] {line}", end='', flush=True)
                        except:
                            pass
                    elif process.stderr and fd == process.stderr.fileno():
                        try:
                            line = process.stderr.readline()
                            if line:
                                print(f"[STDERR] {line}", end='', flush=True)
                        except:
                            pass

                # Log periodic status
                elapsed = time.time() - start_time
                if int(elapsed) % 10 == 0:
                    log(f"Process still running after {elapsed:.1f}s")
        else:
            # Fallback: simple wait
            log("Using simple wait (no real-time output)")
            stdout, stderr = process.communicate()
            if stdout:
                print(f"[STDOUT]\n{stdout}")
            if stderr:
                print(f"[STDERR]\n{stderr}")

        # Get final status
        return_code = process.wait()
        elapsed = time.time() - start_time

        log(f"Process completed with return code: {return_code}")
        log(f"Total execution time: {elapsed:.2f}s")

        return return_code

    except subprocess.TimeoutExpired:
        log("Process timed out!")
        process.kill()
        return -1
    except Exception as e:
        log(f"Error running orchestrator: {e}")
        return -1

def main():
    """Main entry point"""
    log("=== PROCESS EXECUTION TRACER STARTED ===")

    # Capture initial state
    log("Environment:")
    env = capture_environment()
    for key, value in env.items():
        log(f"  {key}: {value}")

    log("Command availability:")
    commands = check_command_availability()
    for cmd, path in commands.items():
        log(f"  {cmd}: {path}")

    # Run orchestrator with all arguments
    log("Starting orchestrator...")
    return_code = run_orchestrator(sys.argv[1:])

    log(f"=== TRACER COMPLETED WITH CODE {return_code} ===")
    return return_code

if __name__ == "__main__":
    sys.exit(main())