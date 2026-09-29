#!/bin/bash

# License Manager UI QA Test Suite Runner
# Complete end-to-end test execution

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_DIR="$PROJECT_ROOT/tests"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts"

# Environment
export LM_BASE_URL="${LM_BASE_URL:-http://localhost:5173}"
export LM_TEST_USERNAME="${LM_TEST_USERNAME:-admin}"
export LM_TEST_PASSWORD="${LM_TEST_PASSWORD:-admin}"
export LM_ENVIRONMENT="${LM_ENVIRONMENT:-development}"

echo "=========================================="
echo "License Manager UI QA Test Suite"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Base URL: $LM_BASE_URL"
echo "  Test User: $LM_TEST_USERNAME"
echo "  Environment: $LM_ENVIRONMENT"
echo "  Artifacts: $ARTIFACTS_DIR"
echo ""

# Ensure artifacts directory exists
mkdir -p "$ARTIFACTS_DIR/screenshots"
mkdir -p "$ARTIFACTS_DIR/console"
mkdir -p "$ARTIFACTS_DIR/network"
mkdir -p "$ARTIFACTS_DIR/data_snapshots"
mkdir -p "$ARTIFACTS_DIR/reports"
mkdir -p "$ARTIFACTS_DIR/failures"

# Change to tests directory
cd "$TESTS_DIR"

# Activate venv if available
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Determine test mode
TEST_MODE="${1:-full}"

case $TEST_MODE in
    smoke)
        echo "Running SMOKE tests..."
        pytest -v -m smoke --html="$ARTIFACTS_DIR/reports/report_smoke.html" --self-contained-html
        ;;

    regression)
        echo "Running REGRESSION tests..."
        pytest -v -m regression --html="$ARTIFACTS_DIR/reports/report_regression.html" --self-contained-html
        ;;

    filters)
        echo "Running FILTER tests..."
        pytest -v -m filters --html="$ARTIFACTS_DIR/reports/report_filters.html" --self-contained-html
        ;;

    forms)
        echo "Running FORM tests..."
        pytest -v -m forms --html="$ARTIFACTS_DIR/reports/report_forms.html" --self-contained-html
        ;;

    crud)
        echo "Running CRUD tests..."
        pytest -v -m crud --html="$ARTIFACTS_DIR/reports/report_crud.html" --self-contained-html
        ;;

    ux)
        echo "Running UX/Accessibility tests..."
        pytest -v -m ux --html="$ARTIFACTS_DIR/reports/report_ux.html" --self-contained-html
        ;;

    reports)
        echo "Running REPORT tests..."
        pytest -v -m reports --html="$ARTIFACTS_DIR/reports/report_tests.html" --self-contained-html
        ;;

    full)
        echo "Running FULL test suite..."
        pytest -v \
            --html="$ARTIFACTS_DIR/reports/report_full.html" \
            --self-contained-html \
            --tb=short \
            2>&1 | tee "$ARTIFACTS_DIR/reports/test_output.log"
        ;;

    *)
        echo "Usage: $0 [smoke|regression|filters|forms|crud|ux|reports|full]"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "Test Suite Complete"
echo "Report: $ARTIFACTS_DIR/reports/report_*.html"
echo "=========================================="
