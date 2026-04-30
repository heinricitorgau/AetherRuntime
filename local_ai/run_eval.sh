#!/usr/bin/env bash
# local_ai/run_eval.sh
# Run C exam offline evaluation pack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EVAL_DIR="$SCRIPT_DIR/eval_cases/c_exam"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { printf "${CYAN}  ->${RESET} %s\n" "$1"; }
ok()    { printf "${GREEN}  ok${RESET} %s\n" "$1"; }
warn()  { printf "${YELLOW}  !!${RESET} %s\n" "$1"; }
fail()  { printf "${RED}  xx${RESET} %s\n" "$1"; exit 1; }
header(){ printf "\n${BOLD}== %s ==${RESET}\n" "$1"; }

# Check if eval cases exist
if [[ ! -d "$EVAL_DIR" ]]; then
    fail "Eval cases not found at $EVAL_DIR"
fi

# Find Python
find_python() {
    if [[ -x "/usr/bin/python3" ]]; then
        printf "%s" "/usr/bin/python3"
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    return 1
}

if ! PYTHON_BIN="$(find_python)"; then
    fail "python3 not found"
fi

header "C Exam Offline Evaluation Pack"

# Parse arguments
USE_AI=0
FILTER=""
OUTPUT=""
ANSWERS_DIR=""

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --use-ai)
            USE_AI=1
            info "Will generate code using local AI"
            shift
            ;;
        --filter)
            FILTER="$2"
            info "Filtering cases: $FILTER"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            info "Output file: $OUTPUT"
            shift 2
            ;;
        --answers-dir)
            ANSWERS_DIR="$2"
            info "Using answer files from: $ANSWERS_DIR"
            shift 2
            ;;
        --help|-h)
            cat <<EOF
Usage: bash local_ai/run_eval.sh [options]

Options:
  --use-ai              Ask the bundled/local model to answer each case.
  --answers-dir DIR     Use DIR/<case_id>.c answers instead of the model.
  --filter TEXT         Run cases whose id, filename, year, or topic matches TEXT.
  --output FILE         Write eval_report.json to FILE.
EOF
            exit 0
            ;;
        *)
            warn "Unknown argument: $1"
            shift
            ;;
    esac
done

# Build eval runner command
eval_cmd=("$PYTHON_BIN" "$SCRIPT_DIR/eval_runner.py")
eval_cmd+=(--eval-dir "$EVAL_DIR")

if [[ "$USE_AI" -eq 1 ]]; then
    eval_cmd+=(--use-ai)
fi

if [[ -n "$FILTER" ]]; then
    eval_cmd+=(--filter "$FILTER")
fi

if [[ -n "$OUTPUT" ]]; then
    eval_cmd+=(--output "$OUTPUT")
fi

if [[ -n "$ANSWERS_DIR" ]]; then
    eval_cmd+=(--answers-dir "$ANSWERS_DIR")
fi

# Run evaluation
header "Running Evaluation"
"${eval_cmd[@]}"

ok "Evaluation complete"
