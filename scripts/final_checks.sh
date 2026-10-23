#!/usr/bin/env bash
# The reproduction check behind docs/Decul.md: build the submission, prove it is deterministic,
# rebuild it from a clean checkout of main with a fresh environment, validate it, and prepare
# the two files uploaded to the submission form in ~/decul-upload/.
#
#     bash scripts/final_checks.sh
#
# Needs the match data (./data or MTAH_DATA_DIR), git and uv. Within the team it is run by hand:
# it reads the data, so the project's AI data guard (.claude/hooks/guard_data.py) blocks Claude
# Code from it. It prints only OK / DIFFERENT / FAILED lines, short SHA-256 hashes and the
# validation summary; command output and errors go to data/cache/final_checks.log, because a
# traceback can quote a line of the data.

set -u
cd "$(dirname "$0")/.."
REPO="$(pwd)"
PY="${PY:-$HOME/venvs/mtah/bin/python}"
DATA="$(cd "${MTAH_DATA_DIR:-$REPO/data}" && pwd)"   # absolute, so the clean checkout finds it
LOG="$DATA/cache/final_checks.log"
SUBMISSION="evaluation/results/Decul.csv"
UPLOAD="$HOME/decul-upload"
SCRATCH="$(mktemp -d /tmp/decul-final.XXXXXX)"
trap 'rm -rf "$SCRATCH"' EXIT
mkdir -p "$DATA/cache"
: > "$LOG"
status=0

quiet() {   # run a command with all its output in the log
    "$@" >> "$LOG" 2>&1
}
hash16() {
    sha256sum "$1" | cut -c1-16
}
same() {    # same <label> <file> <file>
    if cmp -s "$2" "$3"; then
        echo "OK         $1"
    else
        echo "DIFFERENT  $1"
        status=1
    fi
}

echo "== 1. submission, default stage"
if quiet "$PY" make_submission.py; then
    echo "OK         $SUBMISSION  sha256 $(hash16 "$SUBMISSION")"
else
    echo "FAILED     make_submission.py -- see $LOG (do not paste it)"
    exit 1
fi

echo "== 2. determinism: second run, raw ATD parsed again (no cache)"
if quiet "$PY" make_submission.py --no-cache --out "$SCRATCH/second.csv"; then
    same "second run is byte-identical" "$SUBMISSION" "$SCRATCH/second.csv"
else
    echo "FAILED     second run -- see $LOG"
    status=1
fi

echo "== 3. clean checkout of main, fresh environment from requirements-lock.txt"
quiet git fetch --quiet origin
if [ "$(git rev-parse main)" = "$(git rev-parse origin/main)" ]; then
    echo "OK         local main = origin/main ($(git rev-parse --short main)), what judges clone"
else
    echo "DIFFERENT  local main != origin/main -- push main before submitting"
    status=1
fi
if quiet git clone --quiet --branch main "$REPO" "$SCRATCH/clean" \
        && quiet uv venv --quiet --python 3.11 "$SCRATCH/venv" \
        && quiet uv pip sync --quiet --python "$SCRATCH/venv/bin/python" \
                 "$SCRATCH/clean/requirements-lock.txt" \
        && (cd "$SCRATCH/clean" && export MTAH_DATA_DIR="$DATA" \
            && quiet "$SCRATCH/venv/bin/python" make_submission.py --no-cache \
                     --out "$SCRATCH/clean.csv"); then
    same "clean checkout rebuilds the same file" "$SUBMISSION" "$SCRATCH/clean.csv"
else
    echo "FAILED     clean checkout -- see $LOG"
    status=1
fi

echo "== 4. validation"
report="$("$PY" evaluation/validate_submission.py "$SUBMISSION")"
echo "$report" | grep -E '^OK|^FAIL|^        [HADX] |possessions of mean'
echo "$report" | grep -q '^OK' || status=1

echo "== 5. upload files"
if [ "$status" -eq 0 ]; then
    mkdir -p "$UPLOAD"
    cp "$SUBMISSION" "$UPLOAD/Decul.csv"
    cp docs/Decul.md "$UPLOAD/Decul.md"
    same "upload copy matches the checked file" "$SUBMISSION" "$UPLOAD/Decul.csv"
    echo "           $UPLOAD/Decul.csv  sha256 $(hash16 "$UPLOAD/Decul.csv")"
    echo "           $UPLOAD/Decul.md   sha256 $(hash16 "$UPLOAD/Decul.md")"
else
    echo "SKIPPED    upload files not prepared, a check above did not pass"
fi

echo
if [ "$status" -eq 0 ]; then
    echo "ALL CHECKS PASSED"
else
    echo "SOME CHECKS FAILED"
fi
exit "$status"
