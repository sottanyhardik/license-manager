#!/usr/bin/env python3
"""
Django Development Server Manager
Handles port conflicts and clean startup across platforms (macOS, Linux, Windows)
"""

import os
import sys
import time
import socket
import subprocess
import signal
import platform
from pathlib import Path


class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


def print_status(message, color=Colors.NC):
    """Print colored status message"""
    print(f"{color}{message}{Colors.NC}")


def is_port_in_use(port, host='127.0.0.1'):
    """Check if a port is in use"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_pids_on_port(port):
    """Get PIDs of processes listening on a port"""
    pids = []
    system = platform.system()

    try:
        if system == 'Darwin' or system == 'Linux':
            result = subprocess.run(
                f'lsof -ti:{port}',
                shell=True,
                capture_output=True,
                text=True
            )
            if result.stdout:
                pids = [int(pid) for pid in result.stdout.strip().split('\n') if pid.isdigit()]
        elif system == 'Windows':
            result = subprocess.run(
                f'netstat -ano | findstr :{port}',
                shell=True,
                capture_output=True,
                text=True
            )
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    parts = line.split()
                    if parts:
                        pids.append(int(parts[-1]))
    except Exception as e:
        print(f"Warning: Could not determine processes on port {port}: {e}")

    return pids


def kill_pids(pids):
    """Kill processes by PID"""
    system = platform.system()

    for pid in pids:
        try:
            if system == 'Windows':
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
            else:
                os.kill(pid, signal.SIGKILL)
            print_status(f"  Killed process {pid}", Colors.GREEN)
        except Exception as e:
            print_status(f"  Failed to kill {pid}: {e}", Colors.RED)


def kill_port(port):
    """Kill all processes using a port"""
    print_status(f"Checking for processes on port {port}...", Colors.YELLOW)

    pids = get_pids_on_port(port)

    if pids:
        print_status(f"Found {len(pids)} process(es) on port {port}:", Colors.RED)
        for pid in pids:
            print(f"  PID: {pid}")

        print_status("Killing processes...", Colors.YELLOW)
        kill_pids(pids)

        time.sleep(2)

        # Verify port is free
        if is_port_in_use(port):
            print_status(f"Failed to free port {port}!", Colors.RED)
            return False
        else:
            print_status(f"Port {port} is now free", Colors.GREEN)
    else:
        print_status(f"Port {port} is free", Colors.GREEN)

    return True


def check_environment(venv_python, backend_dir):
    """Check Python environment"""
    print_status("Checking Python environment...", Colors.YELLOW)

    if not Path(venv_python).exists():
        print_status(f"Error: Virtual environment not found at {venv_python}", Colors.RED)
        print_status("Create virtual environment first:", Colors.YELLOW)
        print("  python3 -m venv .venv")
        print("  .venv/bin/pip install -r backend/requirements.txt")
        return False

    try:
        result = subprocess.run(
            [venv_python, '--version'],
            capture_output=True,
            text=True
        )
        print(result.stdout.strip())
        print_status("Environment OK", Colors.GREEN)
        return True
    except Exception as e:
        print_status(f"Error checking environment: {e}", Colors.RED)
        return False


def start_django(venv_python, backend_dir, host, port):
    """Start Django development server"""
    print_status(f"Starting Django runserver on {host}:{port}", Colors.YELLOW)
    print_status("Press Ctrl+C to stop", Colors.BLUE)
    print("-" * 50)

    os.chdir(backend_dir)

    cmd = [
        venv_python,
        'manage.py',
        'runserver',
        f'{host}:{port}',
        '--settings=config.settings',
    ]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print_status("\nShutting down gracefully...", Colors.YELLOW)
        sys.exit(0)


def main():
    """Main entry point"""
    # Get project root
    project_root = Path(__file__).parent.resolve()
    backend_dir = project_root / 'backend'
    venv_python = project_root / '.venv' / 'bin' / 'python'

    # Parse arguments
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    host = sys.argv[2] if len(sys.argv) > 2 else '0.0.0.0'

    print_status("=" * 50, Colors.YELLOW)
    print_status("Django Development Server Manager", Colors.YELLOW)
    print_status("=" * 50, Colors.YELLOW)
    print(f"Project root: {project_root}")
    print(f"Backend dir: {backend_dir}")
    print(f"Python: {venv_python}")
    print(f"Configuration: {host}:{port}")
    print("-" * 50)

    # Check environment
    if not check_environment(str(venv_python), str(backend_dir)):
        sys.exit(1)

    # Free up the port
    if not kill_port(port):
        sys.exit(1)

    # Wait for system to release resources
    time.sleep(1)

    # Final check
    if is_port_in_use(port):
        print_status(f"Error: Port {port} is still in use!", Colors.RED)
        sys.exit(1)

    # Start Django
    start_django(str(venv_python), str(backend_dir), host, port)


if __name__ == '__main__':
    main()
