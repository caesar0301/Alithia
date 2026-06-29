#!/usr/bin/env bash
#
# verify_finally.sh - Run all verification checks before committing
#
# This script runs the complete verification suite for alithia:
# 1. Workspace sync (uv sync --extra dev)
# 2. Import boundary validation (no direct soothe-daemon / soothe-cli imports)
# 3. Code formatting check (ruff format)
# 4. Linting (ruff check)
# 5. Unit tests (pytest)
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed
#
# Usage:
#   ./scripts/verify_finally.sh              # Run all checks
#   ./scripts/verify_finally.sh --fix        # Auto-fix formatting and linting issues
#   ./scripts/verify_finally.sh --quick      # Skip tests (format + lint only)
#   ./scripts/verify_finally.sh --deps       # Dependency validation only
#
# Integration with git hooks (optional):
#   echo './scripts/verify_finally.sh' > .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

OVERALL_STATUS=0
FAILED_CHECKS=()
FAILED_LOGS=()

AUTO_FIX=false
SKIP_TESTS=false
DEPS_ONLY=false

for arg in "$@"; do
    case $arg in
        --fix)
            AUTO_FIX=true
            ;;
        --quick)
            SKIP_TESTS=true
            ;;
        --deps)
            DEPS_ONLY=true
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --fix     Auto-fix formatting and linting issues"
            echo "  --quick   Skip tests (format + lint only)"
            echo "  --deps    Dependency validation only (skip format/lint/tests)"
            echo "  --help    Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Source paths checked by ruff (matches Makefile layout)
FORMAT_PATHS="alithia_agent/ tests/"

# Sync command kept in lockstep with `make sync`, plus dev extras for lint/test tools.
# Use UV_PYPI_MIRROR to override the default PyPI index (for networks with connectivity issues).
# Usage: UV_PYPI_MIRROR=https://mirrors.aliyun.com/pypi/simple ./scripts/verify_finally.sh
if [[ -n "${UV_PYPI_MIRROR:-}" ]]; then
    export UV_DEFAULT_INDEX="$UV_PYPI_MIRROR"
fi
UV_SYNC_CMD=(uv sync --extra dev)

print_header() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           $1${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_failure() {
    echo -e "${RED}✗ $1${NC}"
    FAILED_CHECKS+=("$1")
    OVERALL_STATUS=1
}

record_failure_log() {
    local category="$1"
    local details="$2"
    FAILED_LOGS+=("${BOLD}${category}:${NC}\n${details}")
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

_verify_critical_deps() {
    .venv/bin/python - <<'PY'
import importlib.util

pkgs = ("soothe", "soothe_sdk", "pytest", "ruff")
missing = [p for p in pkgs if importlib.util.find_spec(p) is None]
assert not missing, f"Missing packages after sync: {missing}"
PY
}

validate_package_dependencies() {
    print_header "Import Boundary Validation"

    cd "$WORKSPACE_ROOT"

    print_info "Checking: alithia_agent must not import soothe_daemon or soothe_cli..."

    local forbidden_imports
    forbidden_imports=$(
        grep -rEl 'from soothe_daemon|import soothe_daemon|from soothe_cli|import soothe_cli' \
            alithia_agent/ --include='*.py' 2>/dev/null || true
    )

    if [ -n "$forbidden_imports" ]; then
        print_failure "alithia_agent imports soothe_daemon/soothe_cli (violations found)"
        local violations
        violations=$(
            grep -rE 'from soothe_daemon|import soothe_daemon|from soothe_cli|import soothe_cli' \
                alithia_agent/ --include='*.py' | head -10
        )
        record_failure_log "Import boundary" "$violations"
        return 1
    fi
    print_success "alithia_agent does not import soothe_daemon or soothe_cli"

    print_info "Checking: workspace integrity..."

    if ! command -v uv >/dev/null 2>&1; then
        print_warning "uv not found, skipping workspace sync check"
        return 0
    fi

    local sync_output
    sync_output=$("${UV_SYNC_CMD[@]}" --dry-run 2>&1) || true
    if echo "$sync_output" | grep -qE "error|would update|would install"; then
        print_failure "Workspace sync would fail (run 'make sync' or 'uv sync --extra dev' to resolve)"
        record_failure_log "Workspace sync" "$(echo "$sync_output" | head -20)"
        return 1
    fi
    print_success "Workspace dependencies are in sync"

    return 0
}

setup_workspace() {
    print_header "Workspace Setup"

    cd "$WORKSPACE_ROOT"

    if ! command -v uv >/dev/null 2>&1; then
        print_failure "uv is not installed. Please install uv first."
        exit 1
    fi

    print_info "Syncing workspace with dev dependencies (equivalent to 'uv sync --extra dev')..."
    if ! "${UV_SYNC_CMD[@]}" 2>&1; then
        print_failure "uv sync failed - cannot continue verification"
        print_info "Try running 'uv sync --extra dev' manually"
        exit 1
    fi
    print_success "Workspace synced (runtime + dev extras)"

    print_info "Verifying critical dependencies (soothe, soothe_sdk, pytest, ruff)..."
    if ! _verify_critical_deps; then
        print_failure "Critical dependencies missing after sync"
        print_info "Try: 'uv sync --extra dev' to re-sync"
        exit 1
    fi
    print_success "Critical dependencies present"
}

ensure_deps_installed() {
    cd "$WORKSPACE_ROOT"
    if _verify_critical_deps >/dev/null 2>&1; then
        return 0
    fi
    print_warning "Critical deps missing mid-run; re-syncing workspace..."
    if ! "${UV_SYNC_CMD[@]}" >/dev/null 2>&1; then
        print_failure "Re-sync failed"
        return 1
    fi
    _verify_critical_deps
}

check_formatting() {
    print_header "Code Formatting Check"

    cd "$WORKSPACE_ROOT"

    if $AUTO_FIX; then
        print_info "Auto-fixing formatting..."
        if make format >/dev/null 2>&1; then
            print_success "Formatting auto-fixed"
        else
            print_failure "Formatting auto-fix failed"
        fi
    else
        print_info "Checking code formatting..."
        local output
        local exit_code
        output=$(uv run ruff format --check $FORMAT_PATHS 2>&1) && exit_code=0 || exit_code=$?
        if [ $exit_code -eq 0 ]; then
            print_success "Formatting OK"
        else
            print_failure "Formatting issues found (run with --fix to auto-fix)"
            record_failure_log "Formatting" "$output"
            return 1
        fi
    fi

    return 0
}

check_linting() {
    print_header "Linting Check"

    cd "$WORKSPACE_ROOT"

    if $AUTO_FIX; then
        print_info "Auto-fixing linting issues..."
        if make lint-fix >/dev/null 2>&1; then
            print_success "Linting auto-fixed"
        else
            print_failure "Linting auto-fix failed"
        fi
    else
        print_info "Running linter..."
        local output
        local exit_code
        output=$(make lint 2>&1) && exit_code=0 || exit_code=$?
        if [ $exit_code -eq 0 ]; then
            print_success "Linting OK"
        else
            print_failure "Linting errors found (run with --fix to auto-fix)"
            record_failure_log "Linting" "$output"
            return 1
        fi
    fi

    return 0
}

run_tests() {
    if $SKIP_TESTS; then
        print_info "Skipping tests (--quick mode)"
        return 0
    fi

    print_header "Unit Tests"

    cd "$WORKSPACE_ROOT"

    if ! ensure_deps_installed; then
        print_failure "Cannot run tests: dependency state could not be restored"
        return 1
    fi

    print_info "Running tests..."
    local output
    local exit_code
    output=$(uv run pytest tests/ -v --tb=short 2>&1) && exit_code=0 || exit_code=$?
    if [ $exit_code -eq 0 ]; then
        print_success "All tests passed"
    else
        print_failure "Tests failed"
        local test_details
        test_details=$(echo "$output" | grep -E "^FAILED|short test summary|failed [0-9]+," | head -30)
        record_failure_log "Tests" "$test_details"
        local failed_test_files
        failed_test_files=$(echo "$output" | grep -oE "tests/[^:]+\.py" | sort -u | tr '\n' ' ')
        if [ -n "$failed_test_files" ]; then
            record_failure_log "Failed test files" "$failed_test_files"
        fi
        return 1
    fi

    return 0
}

cd "$WORKSPACE_ROOT"

print_header "Alithia Pre-Commit Verification Suite"

setup_workspace

if $DEPS_ONLY; then
    validate_package_dependencies
    exit $OVERALL_STATUS
fi

validate_package_dependencies || true
check_formatting || true
check_linting || true
run_tests || true

print_header "Verification Summary"

if [ $OVERALL_STATUS -eq 0 ]; then
    print_success "All checks passed! Ready to commit."
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some checks failed:${NC}"
    for check in "${FAILED_CHECKS[@]}"; do
        echo "  - $check"
    done
    echo ""

    if [ ${#FAILED_LOGS[@]} -gt 0 ]; then
        echo -e "${BOLD}━━━━━━━━━━━━ Failure Details ━━━━━━━━━━━━${NC}"
        echo ""
        for log in "${FAILED_LOGS[@]}"; do
            echo -e "$log"
            echo ""
        done
    fi

    print_info "Fix the issues above and run this script again."
    echo ""
    exit 1
fi
