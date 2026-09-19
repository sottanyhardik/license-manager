#!/bin/bash

# Django Development Server Manager
# Handles port conflicts and clean startup

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
PORT=${1:-8000}
HOST=${2:-0.0.0.0}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Django Development Server Manager${NC}"
echo "=================================="

# Function to kill existing processes on port
kill_port() {
    local port=$1
    echo -e "${YELLOW}Checking for processes on port $port...${NC}"

    # Get PIDs listening on the port
    local pids=$(lsof -ti:$port 2>/dev/null)

    if [ -n "$pids" ]; then
        echo -e "${RED}Found processes on port $port:${NC}"
        lsof -i :$port -n -P
        echo -e "${YELLOW}Killing processes...${NC}"
        echo "$pids" | xargs kill -9 2>/dev/null
        sleep 2

        # Verify port is free
        if lsof -i :$port >/dev/null 2>&1; then
            echo -e "${RED}Failed to free port $port${NC}"
            return 1
        else
            echo -e "${GREEN}Port $port is now free${NC}"
        fi
    else
        echo -e "${GREEN}Port $port is free${NC}"
    fi
    return 0
}

# Function to check Python environment
check_env() {
    echo -e "${YELLOW}Checking Python environment...${NC}"

    if [ ! -f "$VENV_PYTHON" ]; then
        echo -e "${RED}Error: Virtual environment not found at $VENV_PYTHON${NC}"
        echo "Please create a virtual environment first:"
        echo "  cd $PROJECT_ROOT"
        echo "  python3 -m venv .venv"
        echo "  .venv/bin/pip install -r backend/requirements.txt"
        return 1
    fi

    $VENV_PYTHON --version
    echo -e "${GREEN}Environment OK${NC}"
    return 0
}

# Function to start Django
start_django() {
    echo -e "${YELLOW}Starting Django runserver on $HOST:$PORT${NC}"

    cd "$BACKEND_DIR"

    # Run with: auto-reload, color output, and proper host/port
    exec $VENV_PYTHON manage.py runserver $HOST:$PORT \
        --settings=config.settings \
        --use-threading
}

# Main execution
main() {
    # Check environment
    check_env || exit 1

    # Free up the port
    kill_port $PORT || exit 1

    # Wait a moment for system to release resources
    sleep 1

    # Verify port is still free before starting
    if lsof -i :$PORT >/dev/null 2>&1; then
        echo -e "${RED}Error: Port $PORT is still in use${NC}"
        exit 1
    fi

    # Start Django
    start_django
}

# Trap Ctrl+C for clean shutdown
trap 'echo -e "\n${YELLOW}Shutting down...${NC}"; exit 0' INT TERM

# Run main function
main
