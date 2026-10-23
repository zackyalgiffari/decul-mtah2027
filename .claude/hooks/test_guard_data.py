"""Tests for guard_data.py: every case is a synthetic hook payload, so no test ever opens the data.

    python3 .claude/hooks/test_guard_data.py

Exits non-zero if any case gets the wrong decision.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
GUARD = os.path.join(HERE, "guard_data.py")

ALLOW, BLOCK = 0, 2

D = "da" + "ta"  # spelled apart so this file never matches the guard's own patterns when shown

CASES = [
    # file tools
    (BLOCK, "Read", {"file_path": D + "/tactical/BAR-ATH_tactical_atd.txt"}),
    (BLOCK, "Read", {"file_path": os.path.join(PROJECT, D, "tactical", "x.xml")}),
    (BLOCK, "Read", {"file_path": "~/mtah-" + D + "/tactical/x.txt"}),
    (BLOCK, "Read", {"file_path": D + "/cache/atd.npz"}),
    (BLOCK, "Read", {"file_path": "evaluation/results/Decul.csv"}),
    (BLOCK, "Read", {"file_path": "evaluation/results/decul_v1.csv"}),
    (BLOCK, "Read", {"file_path": "experiments/sweep/out.csv"}),
    (BLOCK, "Read", {"file_path": "experiments/explore.ipynb"}),
    (BLOCK, "Write", {"file_path": D + "/tactical/x.txt"}),
    (ALLOW, "Read", {"file_path": D + "/README.md"}),
    (ALLOW, "Read", {"file_path": "README.md"}),
    (ALLOW, "Read", {"file_path": "evaluation/results/baseline_raw.csv"}),
    (ALLOW, "Read", {"file_path": "experiments/score_v1.py"}),
    (ALLOW, "Read", {"file_path": "experiments/README.md"}),
    (ALLOW, "Edit", {"file_path": "solution/decode.py"}),
    # search tools
    (BLOCK, "Grep", {"pattern": "Barcelona", "path": D}),
    (BLOCK, "Grep", {"pattern": "Barcelona"}),
    (BLOCK, "Grep", {"pattern": "x", "glob": "*.xml"}),
    (BLOCK, "Glob", {"pattern": D + "/**/*.txt"}),
    (ALLOW, "Grep", {"pattern": "def smooth", "glob": "*.py"}),
    (ALLOW, "Grep", {"pattern": "def smooth", "path": "starter"}),
    (ALLOW, "Glob", {"pattern": "**/*.py"}),
    # shell: naming or listing the data
    (BLOCK, "Bash", {"command": "cat " + D + "/tactical/BAR-ATH_tactical_atd.txt"}),
    (BLOCK, "Bash", {"command": "head -c 100 ./" + D + "/tactical/x.xml"}),
    (BLOCK, "Bash", {"command": "ls " + D}),
    (BLOCK, "Bash", {"command": "find " + D + " -type f"}),
    (BLOCK, "Bash", {"command": "test -e " + D + "/tactical/x.xml && echo exists"}),
    (BLOCK, "Bash", {"command": "echo $MTAH_" + D.upper() + "_DIR"}),
    (BLOCK, "Bash", {"command": "cat '" + os.path.join(PROJECT, D, "x.txt") + "'"}),
    (BLOCK, "Bash", {"command": "cat evaluation/results/Decul.csv | head"}),
    (BLOCK, "Bash", {"command": "head experiments/out/features.csv"}),
    # shell: running code that reads the data
    (BLOCK, "Bash", {"command": "python make_submission.py"}),
    (BLOCK, "Bash", {"command": "~/venvs/mtah/bin/python make_submission.py --stage v1"}),
    (BLOCK, "Bash", {"command": "python starter/baseline.py"}),
    (BLOCK, "Bash", {"command": "python -m starter.load_atd"}),
    (BLOCK, "Bash", {"command": "python3 -c 'from games import asset_paths; print(asset_paths())'"}),
    (BLOCK, "Bash", {"command": "bash experiments/run_all.sh"}),
    (BLOCK, "Bash", {"command": "bash experiments/final_checks.sh"}),
    (BLOCK, "Bash", {"command": "./experiments/final_checks.sh"}),
    (BLOCK, "Bash", {"command": "sh experiments/some_new_runner.sh"}),
    (BLOCK, "Bash", {"command": "cd experiments && bash final_checks.sh"}),
    (ALLOW, "Bash", {"command": "sed -n 1,40p experiments/final_checks.sh"}),
    (BLOCK, "Bash", {"command": "jupyter nbconvert --execute starter/02_tracking_atd.ipynb"}),
    # shell: recursive readers that would walk into the data
    (BLOCK, "Bash", {"command": "grep -rn Barcelona ."}),
    (BLOCK, "Bash", {"command": "rg -uu Barcelona"}),
    (BLOCK, "Bash", {"command": "find . -name '*.xml' -exec cat {} +"}),
    (BLOCK, "Bash", {"command": "find . -name '*.txt' | xargs head"}),
    (BLOCK, "Bash", {"command": "git grep --no-index Barcelona"}),
    # shell: allowed
    (ALLOW, "Bash", {"command": "python evaluation/run_evaluation.py --bootstrap 1000"}),
    (ALLOW, "Bash", {"command": "python evaluation/validate_submission.py evaluation/results/Decul.csv"}),
    (ALLOW, "Bash", {"command": "git ls-files -- " + D}),
    (ALLOW, "Bash", {"command": "git check-ignore -v " + D + "/tactical/x.txt"}),
    (ALLOW, "Bash", {"command": "git status --short"}),
    (ALLOW, "Bash", {"command": "git add make_submission.py solution/decode.py"}),
    (ALLOW, "Bash", {"command": "git diff make_submission.py"}),
    (ALLOW, "Bash", {"command": "grep -rn 'def smooth' starter evaluation"}),
    (ALLOW, "Bash", {"command": "grep -rn --exclude-dir=" + D + " 'def smooth' ."}),
    (ALLOW, "Bash", {"command": "git grep -n asset_paths"}),
    (ALLOW, "Bash", {"command": "cat make_submission.py"}),
    (ALLOW, "Bash", {"command": "sed -n 1,40p starter/baseline.py"}),
    (ALLOW, "Bash", {"command": "python experiments/score_v1.py"}),
    (ALLOW, "Bash", {"command": "ls evaluation/results"}),
    (ALLOW, "Bash", {"command": "echo 'match data stays local'"}),
    # quotes: a '|' inside a quoted regex is not a pipe...
    (ALLOW, "Bash", {"command": "git log --all --name-only --format= | sort -u | "
                                "grep -v -E '^(solution/|CLAUDE.md$|make_submission.py$)'"}),
    (ALLOW, "Bash", {"command": "grep -n 'cat|head|make_submission' README.md"}),
    # ...but quoting must not hide a command from the guard
    (BLOCK, "Bash", {"command": "bash -c 'python make_submission.py'"}),
    (BLOCK, "Bash", {"command": "sh -c 'cd /tmp; ls " + D + "'"}),
    (BLOCK, "Bash", {"command": "eval \"cat " + D + "/tactical/x.txt\""}),
    (BLOCK, "Bash", {"command": "echo ok; python make_submission.py"}),
    (BLOCK, "Bash", {"command": "python3 -c \"print(open('" + D + "/tactical/x.txt').read())\""}),
]


def run(payload_text):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=PROJECT)
    env.pop("MTAH_DATA_DIR", None)
    result = subprocess.run([sys.executable, GUARD], input=payload_text, env=env,
                            capture_output=True, text=True)
    return result.returncode


def main():
    failures = 0
    for expected, tool, tool_input in CASES:
        payload = json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": PROJECT})
        got = run(payload)
        if got != expected:
            failures += 1
            print("FAIL expected {} got {}: {} {}".format(expected, got, tool, tool_input))
    got = run("this is not json")
    if got == 0:
        failures += 1
        print("FAIL malformed input was allowed")
    print("{} of {} cases correct".format(len(CASES) + 1 - failures, len(CASES) + 1))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
