"""Team Decul's submission: one command, from the provided data to Decul.csv.

    uv venv --python 3.11 && uv pip sync requirements-lock.txt   # or: pip install -r requirements-lock.txt
    export MTAH_DATA_DIR=/path/to/mtah2027      # or unpack the bundle into ./data
    python make_submission.py
    python evaluation/validate_submission.py evaluation/results/Decul.csv

This is the command the rules ask for: running it against the provided data must reproduce the
submitted file exactly, not approximately. So everything here is deterministic -- no random
state, no network, no hosted model -- and the versions are pinned in requirements-lock.txt.

The pipeline is built in stages, each adding one layer so its contribution can be measured on
its own (--stage; the default is the full pipeline):

    v0  the published baseline_smooth50: nearest player, majority vote +/- 2 s
    v1  the same nearest-player label, decoded by Viterbi instead of a vote   (solution/decode.py)
    v2  team evidence from metres to the nearest home and away player         (solution/features.py)
    v3  + dead-ball evidence: ball over the line, players walking, ball still (solution/evidence.py)
    v4  + Smart Tagging as a prior on which team has the ball                 (solution/tagging.py)
"""

import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from games import GAME, GAMES  # noqa: E402
from starter.baseline import AWAY, HOME, LABELS, build, smooth, write_submission  # noqa: E402
from solution import atd, evidence, features, tagging  # noqa: E402
from solution.decode import decode_match  # noqa: E402

# Params
TEAM = "Decul"
RESULTS_DIR = os.path.join(ROOT, "evaluation", "results")
STAGES = ("v0", "v1", "v2", "v3", "v4")
DEFAULT_STAGE = "v4"
WINDOW = 50  # v0: half-width of the baseline's majority vote, in frames; 50 is the published floor


def labels_for(stage, game=GAME):
    """Per-frame labels for one stage of the pipeline."""
    if stage == "v0":
        return smooth(build(game), WINDOW)
    if stage == "v1":
        return decode_match(evidence.from_labels(build(game), home=HOME, away=AWAY), game)

    track = atd.load(game)
    feats = features.compute(track, GAMES[game]["pitch"], GAMES[game]["fps"])
    prior = tagging.team_prior(len(track["ball"]), game) if stage == "v4" else None
    log_emit = evidence.from_features(feats, dead_ball=stage in ("v3", "v4"), team_prior=prior)
    return decode_match(log_emit, game)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", choices=STAGES, default=DEFAULT_STAGE,
                        help="pipeline stage to run (default: {}, the full pipeline)".format(
                            DEFAULT_STAGE))
    parser.add_argument("--out", default=os.path.join(RESULTS_DIR, TEAM + ".csv"),
                        help="where to write the submission")
    args = parser.parse_args()

    labels = labels_for(args.stage)

    path = write_submission(args.out, labels)
    counts = {label: int(np.sum(labels == label)) for label in tuple(LABELS) + ("X",)}
    print("{} {}  H {}  A {}  D {}  X {}".format(TEAM, args.stage, counts["H"], counts["A"],
                                                 counts["D"], counts["X"]))
    print("-> {}".format(os.path.relpath(path, ROOT)))
    print("\nValidate it:  python evaluation/validate_submission.py {}".format(
        os.path.relpath(path, ROOT)))


if __name__ == '__main__':
    main()
