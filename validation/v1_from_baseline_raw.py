"""Stage v1 on public input only: Viterbi over the organisers' baseline_raw.csv.

baseline_raw.csv is the unsmoothed nearest-player label for every frame, published in the
starter repository -- the exact signal make_submission.py --stage v1 computes from the ATD. So
this measures the decoder without touching the match data.

    python validation/v1_from_baseline_raw.py
    python evaluation/run_evaluation.py --bootstrap 1000
"""

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from solution import evidence  # noqa: E402
from solution.decode import decode_match  # noqa: E402
from starter.baseline import write_submission  # noqa: E402

SOURCE = os.path.join(ROOT, "evaluation", "results", "baseline_raw.csv")
OUT = os.path.join(ROOT, "evaluation", "results", "decul_v1_public.csv")

raw = pd.read_csv(SOURCE)["label"].values
codes = np.where(raw == "H", 0, np.where(raw == "A", 1, -1))
labels = decode_match(evidence.from_labels(codes))
write_submission(OUT, labels)
print("wrote", os.path.relpath(OUT, ROOT), {k: int((labels == k).sum()) for k in "HADX"})
