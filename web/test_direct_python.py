#!/usr/bin/env python3
"""
Direct Python test to invoke claude methods without going through Node.js
This helps isolate whether the issue is with Node.js subprocess handling or Python/Claude itself
"""

import os
import sys
import subprocess
import asyncio
import time
import pty
import signal
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, '/home/debian/Tools/WDFWatch')

def test_1_simple_subprocess():
    """Test 1: Simple subprocess execution to verify claude is available"""
    print("\n" + "="*60)
    print("TEST 1: Simple subprocess - checking claude availability")
    print("="*60)

    # Test if claude is in PATH
    try:
        result = subprocess.run(['which', 'claude'], capture_output=True, text=True)
        print(f"claude location: {result.stdout.strip()}")
        if result.returncode != 0:
            print("ERROR: claude not found in PATH")
            print(f"Current PATH: {os.environ.get('PATH', 'NOT SET')}")
    except Exception as e:
        print(f"ERROR checking claude: {e}")

    # Test claude version
    try:
        result = subprocess.run(['claude', '--version'], capture_output=True, text=True, timeout=5)
        print(f"claude version: {result.stdout.strip()}")
    except subprocess.TimeoutExpired:
        print("ERROR: claude --version timed out")
    except Exception as e:
        print(f"ERROR running claude: {e}")

def test_2_direct_import():
    """Test 2: Direct import of claude_adapter to see if it works"""
    print("\n" + "="*60)
    print("TEST 2: Direct import of claude_adapter")
    print("="*60)

    try:
        from claude_pipeline.core.models.claude_adapter import ClaudeAdapter
        print("✓ Successfully imported ClaudeAdapter")

        # Try to instantiate
        adapter = ClaudeAdapter(
            model="claude-3-5-haiku-20241022",
            temperature=0.7,
            max_tokens=8192
        )
        print("✓ Successfully instantiated ClaudeAdapter")

        # Test simple generation
        print("Testing simple generation...")
        try:
            result = asyncio.run(adapter.generate_async("Say 'test successful' and nothing else"))
            print(f"✓ Generation result: {result}")
        except Exception as e:
            print(f"✗ Generation failed: {e}")

    except ImportError as e:
        print(f"✗ Failed to import: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

def test_3_subprocess_with_pty():
    """Test 3: Run subprocess with pseudo-terminal (PTY)"""
    print("\n" + "="*60)
    print("TEST 3: Subprocess with PTY (pseudo-terminal)")
    print("="*60)

    # Claude might require a terminal for interactive features
    master, slave = pty.openpty()

    cmd = [
        '/home/debian/Tools/WDFWatch/venv/bin/python',
        '-c',
        'import subprocess; result = subprocess.run(["claude", "--version"], capture_output=True, text=True); print(f"From PTY: {result.stdout}")'
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True
        )

        os.close(slave)

        # Read output
        output = b""
        start_time = time.time()
        while time.time() - start_time < 5:
            try:
                chunk = os.read(master, 1024)
                if chunk:
                    output += chunk
                else:
                    break
            except OSError:
                break

        process.wait(timeout=1)
        print(f"PTY output: {output.decode('utf-8', errors='ignore')}")

    except Exception as e:
        print(f"✗ PTY test failed: {e}")
    finally:
        os.close(master)

def test_4_environment_differences():
    """Test 4: Check environment variable differences"""
    print("\n" + "="*60)
    print("TEST 4: Environment variable analysis")
    print("="*60)

    critical_vars = [
        'PATH', 'HOME', 'USER', 'SHELL', 'TERM',
        'CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT',
        'PYTHONPATH', 'PYTHONUNBUFFERED'
    ]

    print("Current environment:")
    for var in critical_vars:
        value = os.environ.get(var, 'NOT SET')
        if var == 'PATH':
            # Check if claude paths are present
            has_claude_path = '/home/debian/.claude/local' in value
            print(f"  {var}: {'✓' if has_claude_path else '✗'} Has claude path: {has_claude_path}")
            if not has_claude_path:
                print(f"    Full PATH: {value}")
        else:
            print(f"  {var}: {value[:50]}..." if len(value) > 50 else f"  {var}: {value}")

    # Test with different environment setups
    print("\nTesting with Claude Code environment variables:")
    test_env = os.environ.copy()
    test_env['CLAUDECODE'] = '1'
    test_env['CLAUDE_CODE_ENTRYPOINT'] = 'cli'

    try:
        result = subprocess.run(
            ['claude', '--version'],
            env=test_env,
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"  With CLAUDECODE=1: {result.stdout.strip() if result.returncode == 0 else 'FAILED'}")
    except Exception as e:
        print(f"  With CLAUDECODE=1: ERROR - {e}")

def test_5_process_hierarchy():
    """Test 5: Check process group and session leader status"""
    print("\n" + "="*60)
    print("TEST 5: Process hierarchy and session analysis")
    print("="*60)

    import os

    pid = os.getpid()
    pgid = os.getpgid(pid)
    sid = os.getsid(pid)
    ppid = os.getppid()

    print(f"Current process info:")
    print(f"  PID: {pid}")
    print(f"  PPID: {ppid}")
    print(f"  PGID: {pgid}")
    print(f"  SID: {sid}")
    print(f"  Is session leader: {pid == sid}")
    print(f"  Is process group leader: {pid == pgid}")

    # Check if we're in a terminal
    print(f"  Has controlling terminal: {os.isatty(sys.stdin.fileno())}")
    print(f"  Terminal name: {os.ttyname(sys.stdin.fileno()) if os.isatty(sys.stdin.fileno()) else 'None'}")

def test_6_signal_handling():
    """Test 6: Test signal handling differences"""
    print("\n" + "="*60)
    print("TEST 6: Signal handling test")
    print("="*60)

    # Check current signal handlers
    signals = [signal.SIGINT, signal.SIGTERM, signal.SIGPIPE, signal.SIGHUP]

    print("Current signal handlers:")
    for sig in signals:
        handler = signal.getsignal(sig)
        if handler == signal.SIG_DFL:
            handler_name = "DEFAULT"
        elif handler == signal.SIG_IGN:
            handler_name = "IGNORED"
        else:
            handler_name = str(handler)
        print(f"  {sig.name}: {handler_name}")

def test_7_file_descriptors():
    """Test 7: Check file descriptor status"""
    print("\n" + "="*60)
    print("TEST 7: File descriptor analysis")
    print("="*60)

    import fcntl
    import stat

    for fd in [0, 1, 2]:  # stdin, stdout, stderr
        try:
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            is_nonblock = bool(flags & os.O_NONBLOCK)

            fd_stat = os.fstat(fd)
            is_tty = stat.S_ISCHR(fd_stat.st_mode)

            print(f"FD {fd} ({'stdin' if fd==0 else 'stdout' if fd==1 else 'stderr'}):")
            print(f"  Is TTY: {is_tty}")
            print(f"  Non-blocking: {is_nonblock}")
            print(f"  Mode: {oct(fd_stat.st_mode)}")
        except Exception as e:
            print(f"FD {fd}: ERROR - {e}")

def test_8_orchestrator_direct():
    """Test 8: Call orchestrator.py directly from Python"""
    print("\n" + "="*60)
    print("TEST 8: Direct orchestrator.py invocation")
    print("="*60)

    cmd = [
        '/home/debian/Tools/WDFWatch/venv/bin/python',
        'claude-pipeline/orchestrator.py',
        '--episode-id', 'it-wasnt-the-last',
        '--stages', 'summarize'
    ]

    # Test with minimal environment
    minimal_env = {
        'PATH': os.environ.get('PATH', ''),
        'HOME': '/home/debian',
        'USER': 'debian',
        'PYTHONUNBUFFERED': '1',
    }

    # Add Claude Code vars if they exist
    if 'CLAUDECODE' in os.environ:
        minimal_env['CLAUDECODE'] = os.environ['CLAUDECODE']
        minimal_env['CLAUDE_CODE_ENTRYPOINT'] = os.environ.get('CLAUDE_CODE_ENTRYPOINT', 'cli')

    print(f"Running: {' '.join(cmd)}")
    print(f"Environment keys: {list(minimal_env.keys())}")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=minimal_env,
            cwd='/home/debian/Tools/WDFWatch'
        )

        # Monitor for 10 seconds
        start_time = time.time()
        output_lines = []

        while time.time() - start_time < 10:
            line = process.stdout.readline()
            if line:
                output_lines.append(line.strip())
                if len(output_lines) <= 5 or 'ERROR' in line or 'claude' in line.lower():
                    print(f"  [{time.time()-start_time:.1f}s] {line.strip()}")

            if process.poll() is not None:
                break

        if process.poll() is None:
            print("  Process still running after 10s, terminating...")
            process.terminate()
            process.wait(timeout=2)

        print(f"  Exit code: {process.returncode}")

    except Exception as e:
        print(f"  ERROR: {e}")

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("DIRECT PYTHON TESTS - Claude Pipeline Investigation")
    print("="*80)
    print(f"Running from: {os.getcwd()}")
    print(f"Python: {sys.executable}")
    print(f"Script PID: {os.getpid()}")

    # Run all tests
    test_1_simple_subprocess()
    test_2_direct_import()
    test_3_subprocess_with_pty()
    test_4_environment_differences()
    test_5_process_hierarchy()
    test_6_signal_handling()
    test_7_file_descriptors()
    test_8_orchestrator_direct()

    print("\n" + "="*80)
    print("ALL TESTS COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()