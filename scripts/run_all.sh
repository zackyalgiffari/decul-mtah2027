#!/usr/bin/env bash
# Rebuild every Decul stage (v0-v8) from the match data, validate each file, and score them all
# against the public five minutes -- the source of the stage tables in docs/Decul.md.
#
#     bash scripts/run_all.sh
#
# Needs the match data (./data or MTAH_DATA_DIR). Within the team it is run by hand: it reads
# the data, so the project's AI data guard (.claude/hooks/guard_data.py) blocks Claude Code
# from it. It prints only aggregates -- per-stage label counts, validation summaries and the
# scoreboard. Errors go to data/cache/run_all.log instead, because a traceback can quote a line
# of the data.

set -u
cd "$(dirname "$0")/.."
PY="${PY:-$HOME/venvs/mtah/bin/python}"
LOG_DIR="${MTAH_DATA_DIR:-data}/cache"
LOG="$LOG_DIR/run_all.log"
mkdir -p "$LOG_DIR"
: > "$LOG"

for stage in v0 v1 v2 v3 v4 v5 v6 v7 v8; do
    out="evaluation/results/decul_${stage}.csv"
    echo "== stage ${stage}"
    start=$(date +%s)
    if "$PY" make_submission.py --stage "$stage" --out "$out" > "$LOG_DIR/stage.out" 2>> "$LOG"; then
        grep '^Decul' "$LOG_DIR/stage.out"
        echo "   $(( $(date +%s) - start )) s"
        "$PY" evaluation/validate_submission.py "$out" | grep -E '^OK|^FAIL|^        [HADX] |possessions of mean'
    else
        echo "   FAILED -- see $LOG (do not paste it; describe the error instead)"
        rm -f "$out"
    fi
done
rm -f "$LOG_DIR/stage.out"

echo
echo "== scoreboard (public 5 minutes, 1000 bootstrap draws)"
"$PY" evaluation/run_evaluation.py --bootstrap 1000
