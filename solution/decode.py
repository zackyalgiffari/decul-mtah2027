"""Turn per-frame evidence into whole possessions: a three-state Viterbi decoder, half by half.

The baseline smooths with a fixed window, which treats a 0.8 s possession and a 0.8 s flicker
the same way. A hidden Markov model does not: every change of state has a price, and a change is
made only when the evidence for it outweighs that price. Strong, sustained evidence switches
fast; weak or missing evidence leaves the current state alone -- which is exactly the rule that
a loose ball stays with the team that last had it (CHALLENGE.md).

States are H, A and D. The decoder never sees halftime: each half is decoded on its own, from
games.half_video_blocks, and every frame outside the two halves is written as X, which is never
graded (DATA.md, "Which frames are graded").
"""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from games import GAME, GAMES, half_video_blocks  # noqa: E402

# Params
STATES = np.array(["H", "A", "D"])
H, A, D = 0, 1, 2

# Football priors, in seconds, not fitted to the public window. They set the price of a change
# of state (a per-frame switch probability of 1 / (duration * fps)), so they only need the right
# order of magnitude: a possession lasts around ten seconds, a stoppage -- throw-in, free kick,
# goal kick -- around a quarter of a minute.
POSSESSION_S = 12.0
DEAD_S = 15.0
# Of the possessions that end, the share that end in a turnover in open play rather than in a
# stoppage. Most do: interceptions, tackles and misplaced passes outnumber the ball going out.
TURNOVER_SHARE = 0.75


def transition_log_matrix(fps):
    """3x3 log transition matrix, rows = from-state, columns = to-state, in H A D order."""
    end_possession = 1.0 / (POSSESSION_S * fps)
    end_stoppage = 1.0 / (DEAD_S * fps)
    trans = np.array([
        [1.0 - end_possession, end_possession * TURNOVER_SHARE, end_possession * (1 - TURNOVER_SHARE)],
        [end_possession * TURNOVER_SHARE, 1.0 - end_possession, end_possession * (1 - TURNOVER_SHARE)],
        [end_stoppage / 2.0, end_stoppage / 2.0, 1.0 - end_stoppage],
    ])
    return np.log(trans)


def viterbi(log_emit, log_trans, log_init=None):
    """Most likely state path for one contiguous block. log_emit is (n_frames, n_states).

    Ties go to the lower state index (np.argmax), so the result is deterministic.
    """
    n_frames, n_states = log_emit.shape
    if log_init is None:
        log_init = np.full(n_states, -np.log(n_states))

    back = np.empty((n_frames, n_states), dtype=np.int8)
    columns = np.arange(n_states)
    score = log_init + log_emit[0]
    for t in range(1, n_frames):
        candidates = score[:, None] + log_trans          # [from, to]
        back[t] = np.argmax(candidates, axis=0)
        score = candidates[back[t], columns] + log_emit[t]

    path = np.empty(n_frames, dtype=np.int8)
    path[-1] = np.argmax(score)
    for t in range(n_frames - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def decode_match(log_emit, game=GAME, log_trans=None):
    """Labels for every video frame: Viterbi inside each half, X everywhere else."""
    if log_trans is None:
        log_trans = transition_log_matrix(GAMES[game]["fps"])
    labels = np.full(len(log_emit), "X", dtype="<U1")
    for _, first, last in half_video_blocks(game):
        block = slice(first, last + 1)   # half_video_blocks is inclusive at both ends
        labels[block] = STATES[viterbi(log_emit[block], log_trans)]
    return labels
