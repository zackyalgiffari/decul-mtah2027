"""Team Decul's submission: one command, from the provided data to Decul.csv.

    uv venv --python 3.11 && uv pip sync requirements-lock.txt   # or: pip install -r requirements-lock.txt
    export MTAH_DATA_DIR=/path/to/mtah2027      # or unpack the bundle into ./data
    python make_submission.py
    python evaluation/validate_submission.py evaluation/results/Decul.csv

This is the command the rules ask for: running it against the provided data must reproduce the
submitted file exactly, not approximately. So everything here is deterministic -- no random
state, no network, no hosted model -- and the versions are pinned in requirements-lock.txt.

v0 is the published baseline_smooth50 under Decul's name, so the loop from data to a scored file
works end to end before the real pipeline exists. The Decul pipeline will live in solution/ and
replace the two lines in main() that build the labels; this command does not change.
"""

import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from starter.baseline import LABELS, build, smooth, write_submission  # noqa: E402

# Params
TEAM = "Decul"
RESULTS_DIR = os.path.join(ROOT, "evaluation", "results")
WINDOW = 50  # half-width of the baseline's majority vote, in frames; 50 is the published floor


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=os.path.join(RESULTS_DIR, TEAM + ".csv"),
                        help="where to write the submission")
    args = parser.parse_args()

    labels = smooth(build(), WINDOW)

    path = write_submission(args.out, labels)
    counts = {label: int(np.sum(labels == label)) for label in LABELS}
    print("{}  H {}  A {}  D {}".format(TEAM, counts["H"], counts["A"], counts["D"]))
    print("-> {}".format(os.path.relpath(path, ROOT)))
    print("\nValidate it:  python evaluation/validate_submission.py {}".format(
        os.path.relpath(path, ROOT)))


if __name__ == '__main__':
    main()
