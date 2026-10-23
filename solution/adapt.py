"""Stage v7: learn what a dead ball looks like in *this* match's tracking, without any labels.

The alive/dead evidence of v3 is hand-set from football knowledge. It fits cleaner tracking well
(dead-ball recall 0.75-0.90 on Metrica's public matches) and this match's automatic tracking
badly (0.32 on the public window): how often the ball vanishes, how still a placed ball reads,
how fast players appear to move during a stoppage all depend on the tracker. Rather than
re-tuning by hand, v7 lets the hidden Markov model fit those quantities to the match itself with
Baum-Welch (expectation-maximisation):

    1. describe every frame by a symbol: ball seen x over the line x player-speed bin x ball still
    2. E-step: forward-backward over each half gives P(H), P(A), P(D) per frame
    3. M-step: P(symbol | alive) and P(symbol | dead) are the posterior-weighted symbol counts
    4. repeat a fixed number of times, then decode with Viterbi as every other stage does

Only the two symbol tables are learned. The team evidence (distances, Smart Tagging) and the
transition priors stay fixed -- the priors were shown to be stable (docs/Decul.md), and freeing
them would let EM trade whole possessions for per-frame fit, which spellF1 punishes. The first
E-step uses the v4 evidence, so state D keeps meaning "dead ball" throughout.

No ground truth and no hand labels are involved: the labels still come out of an algorithm run
on the provided data. Fixed initialisation and a fixed number of iterations keep it
deterministic. Nothing learned is printed -- it would be a summary of the data.
"""

import numpy as np

from solution import evidence
from solution.decode import A, D, H, transition_log_matrix

# Params
N_ITER = 10
# Mean player speed bins, m/s. Live play averages about 2 m/s; players walk during stoppages.
SPEED_EDGES = (1.0, 1.5, 2.5)
N_SPEED = len(SPEED_EDGES) + 1
N_SYMBOLS = 2 * 2 * N_SPEED * 2
SMOOTHING = 1.0   # add-one: a symbol never seen in one state is rare there, not impossible


def symbols(features):
    """Per-frame symbol in 0..N_SYMBOLS-1: ball seen, ball over the line, speed bin, ball still."""
    speed = np.nan_to_num(features["player_speed"], nan=SPEED_EDGES[1])
    speed_bin = np.searchsorted(np.array(SPEED_EDGES), speed, side="right")
    return (((features["ball_seen"].astype(int) * 2 + features["ball_out"].astype(int)) * N_SPEED
             + speed_bin) * 2 + features["ball_static"].astype(int))


def posteriors(log_emit, blocks, log_trans):
    """P(state | all frames) for every frame inside the blocks, by scaled forward-backward."""
    gamma = np.zeros_like(log_emit)
    trans = np.exp(log_trans)
    for first, last in blocks:
        block = log_emit[first:last + 1]
        emit = np.exp(block - block.max(axis=1, keepdims=True))   # per-frame scale cancels
        n = len(emit)
        alpha = np.empty_like(emit)
        alpha[0] = emit[0] / emit[0].sum()
        for t in range(1, n):
            a = (alpha[t - 1] @ trans) * emit[t]
            alpha[t] = a / a.sum()
        beta = np.ones_like(emit)
        for t in range(n - 2, -1, -1):
            b = trans @ (emit[t + 1] * beta[t + 1])
            beta[t] = b / b.sum()
        post = alpha * beta
        gamma[first:last + 1] = post / post.sum(axis=1, keepdims=True)
    return gamma


def symbol_tables(symbol, gamma, blocks):
    """M-step: log P(symbol | alive) and log P(symbol | dead) from posterior-weighted counts."""
    inside = np.zeros(len(symbol), dtype=bool)
    for first, last in blocks:
        inside[first:last + 1] = True
    alive = np.bincount(symbol[inside], weights=gamma[inside, H] + gamma[inside, A],
                        minlength=N_SYMBOLS) + SMOOTHING
    dead = np.bincount(symbol[inside], weights=gamma[inside, D], minlength=N_SYMBOLS) + SMOOTHING
    return np.log(alive / alive.sum()), np.log(dead / dead.sum())


def fit(symbol, p_home, init_log_emit, blocks, fps, n_iter=N_ITER):
    """Learned (log P(symbol | alive), log P(symbol | dead)), starting from init_log_emit's E-step."""
    log_trans = transition_log_matrix(fps)
    gamma = posteriors(init_log_emit, blocks, log_trans)
    for _ in range(n_iter):
        log_alive, log_dead = symbol_tables(symbol, gamma, blocks)
        gamma = posteriors(evidence.combine_logs(log_alive[symbol], log_dead[symbol], p_home),
                           blocks, log_trans)
    return symbol_tables(symbol, gamma, blocks)


def from_features(features, blocks, fps, team_prior=None, n_iter=N_ITER):
    """v7 log-likelihoods: learned alive/dead evidence, v4 team evidence."""
    symbol = symbols(features)
    p_home = evidence.team_probability(features, team_prior)
    init = evidence.from_features(features, dead_ball=True, team_prior=team_prior)
    log_alive, log_dead = fit(symbol, p_home, init, blocks, fps, n_iter)
    return evidence.combine_logs(log_alive[symbol], log_dead[symbol], p_home)
