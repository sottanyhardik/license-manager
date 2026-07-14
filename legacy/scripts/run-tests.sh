#!/bin/bash
#
# License Manager - Automated Test Suite
# Run all tests with fake database
#
# Usage:
#   ./run-tests.sh              # Run all tests
#   ./run-tests.sh --fast       # Run fast tests only (skip slow)
#   ./run-tests.sh --coverage   # Run with detailed coverage report
#   ./run-tests.sh --api        # Run API tests only
#   ./run-tests.sh --unit       # Run unit tests only
#   ./run-tests.sh --clean      # Clean test artifacts first
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   License Manager - Automated Test Suite${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Parse arguments
RUN_MODE="all"
CLEAN_FIRST=false
COVERAGE_DETAIL=false

for arg in "$@"; do
    case $arg in
        --fast)
            RUN_MODE="fast"
            ;;
        --api)
            RUN_MODE="api"
            ;;
        --unit)
            RUN_MODE="unit"
            ;;
        --integration)
            RUN_MODE="integration"
            ;;
        --clean)
            CLEAN_FIRST=true
            ;;
        --coverage)
            COVERAGE_DETAIL=true
            ;;
        --help)
            echo "Usage: ./run-tests.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --fast          Run fast tests only (skip slow tests)"
            echo "  --api           Run API tests only"
            echo "  --unit          Run unit tests only"
            echo "  --integration   Run integration tests only"
            echo "  --clean         Clean test artifacts before running"
            echo "  --coverage      Generate detailed coverage report"
            echo "  --help          Show this help message"
            echo ""
            exit 0
            ;;
    esac
done

# Function to print section headers
print_section() {
    echo ""
    echo -e "${YELLOW}━━━ $1 ━━━${NC}"
    echo ""
}

# Function to print success message
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error message
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Clean test artifacts
clean_test_artifacts() {
    print_section "Cleaning Test Artifacts"
    
    cd "$BACKEND_DIR"
    
    # Remove coverage files
    rm -f .coverage
    rm -rf htmlcov/
    rm -rf .pytest_cache/
    rm -rf __pycache__/
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    print_success "Cleaned test artifacts"
}

# Setup test environment
setup_test_environment() {
    print_section "Setting Up Test Environment"
    
    cd "$BACKEND_DIR"
    
    # Check if virtual environment exists
    if [ ! -d "venv" ] && [ ! -d "../venv" ]; then
        print_error "No virtual environment found. Creating one..."
        python3 -m venv venv
        source venv/bin/activate
    else
        if [ -d "venv" ]; then
            source venv/bin/activate
        else
            source ../venv/bin/activate
        fi
    fi
    
    # Install test dependencies if needed
    if ! pip show pytest > /dev/null 2>&1; then
        print_section "Installing Test Dependencies"
        pip install -q -r requirements-test.txt
        print_success "Test dependencies installed"
    fi
    
    # Check PostgreSQL connection
    print_section "Checking Database Connection"
    if command_exists psql; then
        print_success "PostgreSQL client available"
    else
        print_error "PostgreSQL client not found. Install with: brew install postgresql (macOS)"
        exit 1
    fi
    
    # Set test database environment variables
    export DJANGO_SETTINGS_MODULE=lmanagement.settings
    export TESTING=true
    
    print_success "Test environment ready"
}

# Run backend API tests
run_backend_tests() {
    print_section "Running Backend Tests"
    
    cd "$BACKEND_DIR"
    
    # Build pytest command based on mode
    PYTEST_CMD="pytest"
    PYTEST_ARGS="-v --tb=short"
    
    case $RUN_MODE in
        fast)
            PYTEST_ARGS="$PYTEST_ARGS -m 'not slow'"
            echo -e "${YELLOW}Mode: Fast tests only${NC}"
            ;;
        api)
            PYTEST_ARGS="$PYTEST_ARGS -m api"
            echo -e "${YELLOW}Mode: API tests only${NC}"
            ;;
        unit)
            PYTEST_ARGS="$PYTEST_ARGS -m unit"
            echo -e "${YELLOW}Mode: Unit tests only${NC}"
            ;;
        integration)
            PYTEST_ARGS="$PYTEST_ARGS -m integration"
            echo -e "${YELLOW}Mode: Integration tests only${NC}"
            ;;
        all)
            echo -e "${YELLOW}Mode: All tests${NC}"
            ;;
    esac
    
    # Add coverage if requested
    if [ "$COVERAGE_DETAIL" = true ]; then
        PYTEST_ARGS="$PYTEST_ARGS --cov=. --cov-report=html --cov-report=term-missing"
    else
        PYTEST_ARGS="$PYTEST_ARGS --cov=. --cov-report=term --no-cov-on-fail"
    fi
    
    # Run tests
    echo ""
    echo -e "${BLUE}Running: $PYTEST_CMD $PYTEST_ARGS${NC}"
    echo ""
    
    if $PYTEST_CMD $PYTEST_ARGS tests/; then
        print_success "Backend tests passed"
        BACKEND_STATUS=0
    else
        print_error "Backend tests failed"
        BACKEND_STATUS=1
    fi
    
    # Show coverage report location
    if [ "$COVERAGE_DETAIL" = true ] && [ -d "htmlcov" ]; then
        echo ""
        echo -e "${BLUE}Coverage report: file://$BACKEND_DIR/htmlcov/index.html${NC}"
    fi
    
    return $BACKEND_STATUS
}

# Run frontend tests (if they exist)
run_frontend_tests() {
    print_section "Checking Frontend Tests"
    
    cd "$FRONTEND_DIR"
    
    # Check if test setup exists
    if [ ! -f "package.json" ]; then
        print_error "No package.json found"
        return 1
    fi
    
    # Check if test script exists
    if grep -q '"test"' package.json; then
        echo "Running frontend tests..."
        npm test
        print_success "Frontend tests passed"
    else
        echo -e "${YELLOW}ℹ No frontend tests configured (add test script to package.json)${NC}"
    fi
    
    return 0
}

# Generate test report
generate_test_report() {
    print_section "Test Summary"
    
    echo "Test Results:"
    echo "─────────────────────────────────────"
    
    if [ $BACKEND_STATUS -eq 0 ]; then
        echo -e "Backend Tests:  ${GREEN}✓ PASSED${NC}"
    else
        echo -e "Backend Tests:  ${RED}✗ FAILED${NC}"
    fi
    
    echo "─────────────────────────────────────"
    echo ""
    
    if [ $BACKEND_STATUS -eq 0 ]; then
        echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║   ALL TESTS PASSED SUCCESSFULLY! ✓   ║${NC}"
        echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
        return 0
    else
        echo -e "${RED}╔═══════════════════════════════════════╗${NC}"
        echo -e "${RED}║      SOME TESTS FAILED! ✗             ║${NC}"
        echo -e "${RED}╚═══════════════════════════════════════╝${NC}"
        return 1
    fi
}

# Main execution
main() {
    # Clean if requested
    if [ "$CLEAN_FIRST" = true ]; then
        clean_test_artifacts
    fi
    
    # Setup environment
    setup_test_environment
    
    # Run backend tests
    BACKEND_STATUS=0
    run_backend_tests || BACKEND_STATUS=$?
    
    # Note: Frontend tests skipped for now (no test framework installed)
    # Uncomment when frontend tests are added:
    # FRONTEND_STATUS=0
    # run_frontend_tests || FRONTEND_STATUS=$?
    
    # Generate report
    generate_test_report
    
    exit $?
}

# Run main function
main
