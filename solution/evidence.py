"""Per-frame evidence for H, A and D, as the (n_frames, 3) log-likelihoods solution/decode.py reads.

Every stage answers two questions per frame and combines them:

    P(alive)            is the ball in play?           from the ball being seen, its position,
                                                        how fast everyone is moving
    P(home | alive)     if so, which team has it?      from who is nearest the ball

    log H = log P(alive) + log P(home | alive)
    log A = log P(alive) + log(1 - P(home | alive))
    log D = log(1 - P(alive)) + log 0.5           (a dead ball carries no team information)

so a frame that says nothing about the team (P(home | alive) = 0.5) compares H and A against D
on the alive question alone. Probabilities are clipped away from 0 and 1: one frame is never
proof.

Everything is multiplied by TEMPER before decoding. Consecutive frames are not independent
witnesses -- the same occlusion or the same player standing near the ball produces the same
reading 25 times a second -- so without it a single second of noise would outvote the decoder's
switching price. With TEMPER = 0.3 and the default priors, about a second of consistent evidence
is needed to change state.
"""

import numpy as np

from solution.decode import A, D, H

# Params
TEMPER = 0.3
CLIP = 0.03

# v1: P(observed | state) for the baseline's hard nearest-player label. Rows are the true state
# (H, A, D); columns the observation (home nearest, away nearest, ball not found). Priors, not
# fits: the nearest player belongs to the team in possession roughly three times in four when the
# ball is seen, the ball goes unseen for part of live play (41% of graded frames, DATA.md), and
# far more often when it is dead.
LABEL_EMISSION = np.array([
    [0.55, 0.15, 0.30],
    [0.15, 0.55, 0.30],
    [0.10, 0.10, 0.80],
])
OBS_HOME, OBS_AWAY, OBS_NONE = 0, 1, 2

# v2: P(alive) from the ball being seen or not, the same odds the v1 table implies, so v2 differs
# from v1 only in how it reads the team.
P_ALIVE_SEEN = (LABEL_EMISSION[H, OBS_HOME] + LABEL_EMISSION[H, OBS_AWAY]) / (
    LABEL_EMISSION[H, OBS_HOME] + LABEL_EMISSION[H, OBS_AWAY]
    + LABEL_EMISSION[D, OBS_HOME] + LABEL_EMISSION[D, OBS_AWAY])
P_ALIVE_UNSEEN = LABEL_EMISSION[H, OBS_NONE] / (LABEL_EMISSION[H, OBS_NONE] + LABEL_EMISSION[D, OBS_NONE])

# v2: who controls the ball. Beyond CONTROL_M from every player the ball is in flight or loose and
# says nothing about the team -- possession stays with whoever had it, which is the decoder's job.
# Inside it, each metre by which the nearest home player is closer than the nearest away player
# multiplies the home odds by e^(1 / SCALE_M).
CONTROL_M = 3.0
SCALE_M = 1.0

# v3: dead-ball odds multipliers. A ball outside the lines is dead; a stoppage is when players
# walk; a ball standing still is waiting for a restart. Mean player speed is centred on
# SPEED_PIVOT_MS (players average about 2 m/s over a match, and walk during stoppages).
OUT_ODDS = 0.1
SPEED_PIVOT_MS = 1.5
SPEED_WEIGHT = 1.0           # log-odds per m/s of mean player speed
STATIC_BALL_ODDS = 0.5

# v4: Smart Tagging odds multiplier for the team a tag says has the ball. Modest on purpose: the
# tags are automatic and a phase is not a possession (DATA.md).
TAG_TEAM_ODDS = 2.0

# v5: control needs a ball that is being controlled. A dribbled ball rarely moves faster than a
# sprinting player; passes, clearances and shots do. Above FAST_BALL_MS the ball is travelling,
# and the player it passes says nothing about who has it (CHALLENGE.md: a touch or a deflection
# without control is not a change of possession).
FAST_BALL_MS = 7.0

# v6: a ball standing still on a line or on the centre spot is waiting for a throw-in, corner or
# kick-off (solution/features.py, restart_spot).
RESTART_ODDS = 0.2


def _clip(p):
    return np.clip(p, CLIP, 1.0 - CLIP)


def _odds(p):
    return p / (1.0 - p)


def _prob(odds):
    return odds / (1.0 + odds)


def combine_logs(log_alive, log_dead, p_home):
    """(n, 3) tempered log-likelihoods from per-frame log evidence for alive / dead and P(home | alive).

    solution/adapt.py (v7) passes learned log-probabilities here; combine() passes log P(alive).
    """
    p_home = _clip(p_home)
    out = np.empty((len(p_home), 3))
    out[:, H] = log_alive + np.log(p_home)
    out[:, A] = log_alive + np.log(1.0 - p_home)
    out[:, D] = log_dead + np.log(0.5)
    return TEMPER * out


def combine(p_alive, p_home):
    """(n, 3) tempered log-likelihoods from P(alive) and P(home | alive)."""
    p_alive = _clip(p_alive)
    return combine_logs(np.log(p_alive), np.log(1.0 - p_alive), p_home)


def from_labels(codes, home=0, away=1):
    """v1: log-likelihoods from the baseline's per-frame codes (home, away, anything else = no ball)."""
    observed = np.full(len(codes), OBS_NONE)
    observed[codes == home] = OBS_HOME
    observed[codes == away] = OBS_AWAY
    return TEMPER * np.log(LABEL_EMISSION[:, observed].T)


def p_home_from_distances(d_home, d_away):
    """P(home | alive) from metres to the nearest home and away player. NaN -> no information."""
    nearest = np.fmin(d_home, d_away)
    margin = np.nan_to_num(d_away - d_home, nan=0.0)
    p_home = 1.0 / (1.0 + np.exp(-margin / SCALE_M))
    contested = np.isnan(nearest) | (nearest > CONTROL_M)
    p_home[contested] = 0.5
    return p_home


def alive_odds_dead_ball(features):
    """v3: odds multiplier on 'alive' from the dead-ball cues."""
    odds = np.ones(len(features["ball_seen"]))
    odds[features["ball_out"]] *= OUT_ODDS
    speed = np.nan_to_num(features["player_speed"], nan=SPEED_PIVOT_MS)
    odds *= np.exp(np.clip(SPEED_WEIGHT * (speed - SPEED_PIVOT_MS), -3.0, 3.0))
    odds[features["ball_static"]] *= STATIC_BALL_ODDS
    return odds


def from_features(features, dead_ball=False, team_prior=None, fast_ball=False, restart=False,
                  alive_prior=None):
    """v2-v6, v8: log-likelihoods from solution/features.py output.

    dead_ball    add the v3 dead-ball cues to P(alive)
    team_prior   per-frame odds multiplier on home (v4, from solution/tagging.py), or None
    fast_ball    v5: no team evidence while the ball travels faster than FAST_BALL_MS
    restart      v6: a ball waiting on a line or the centre spot counts towards a dead ball
    alive_prior  v8: per-frame odds multiplier on alive (solution/tagging.py dead_odds), or None
    """
    p_alive = np.where(features["ball_seen"], P_ALIVE_SEEN, P_ALIVE_UNSEEN)
    if dead_ball:
        p_alive = _prob(_odds(p_alive) * alive_odds_dead_ball(features))
    if restart:
        p_alive = _prob(_odds(p_alive) * np.where(features["restart_spot"], RESTART_ODDS, 1.0))
    if alive_prior is not None:
        p_alive = _prob(_odds(p_alive) * alive_prior)
    return combine(p_alive, team_probability(features, team_prior, fast_ball))


def team_probability(features, team_prior=None, fast_ball=False):
    """P(home | alive) per frame: distances, optionally the v5 fast-ball rule and the v4 tag prior."""
    p_home = p_home_from_distances(features["d_home"], features["d_away"])
    if fast_ball:
        p_home[np.nan_to_num(features["ball_speed"], nan=0.0) > FAST_BALL_MS] = 0.5
    if team_prior is not None:
        p_home = _prob(_odds(_clip(p_home)) * team_prior)
    return p_home
