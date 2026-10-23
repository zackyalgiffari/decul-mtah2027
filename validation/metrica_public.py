"""Validate the Decul stages on Metrica's public sample matches, where hundreds of possessions exist.

The competition gives five minutes of ground truth: 17 possessions, too few to choose between
two versions (EVALUATION.md). Metrica publishes full sample matches with tracking *and* event
data (github.com/metrica-sports/sample-data, Sample_Game_1 and _2). From the events a possession
label can be derived for every frame, which gives a second, much larger yardstick. It is public
data -- nothing here reads the competition match.

    ~/venvs/mtah/bin/python -I validation/metrica_public.py ~/mtah-public/metrica_sample/Sample_Game_1

Event-derived labels (mechanical, and NOT the competition's definition, which comes from
corrected tracking -- CHALLENGE.md):

    D   from a stoppage -- the end of a BALL OUT, a SHOT that goes out or in, a FAULT RECEIVED --
        until the next restart (a SET PIECE or a GOAL KICK pass), or the next on-ball event if
        no restart is logged
    H/A otherwise the team of the latest on-ball event (PASS, SHOT, SET PIECE, RECOVERY,
        BALL LOST at its start): a loose ball stays with the last team until another team
        recovers it, the same rule CHALLENGE.md states. Duels (CHALLENGE) are ignored.
    X   frames outside the two periods

So the numbers below compare stages with each other; they do not predict the competition score.
The sample tracking is also cleaner than the competition's automatic tracking, and it has no
speeds (computed here from positions) and no Smart Tagging (so v4 and v6 cannot be run).
"""

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402
from solution import evidence, features  # noqa: E402
from solution.decode import decode_blocks, transition_log_matrix  # noqa: E402
from starter.baseline import smooth  # noqa: E402

# Params
FPS = 25
PITCH = (105.0, 68.0)   # the sample data is normalised to a 105 x 68 m pitch
BOOTSTRAP_N = 1000
SENSITIVITY_BOOTSTRAP_N = 300
ON_BALL = ("PASS", "SHOT", "SET PIECE", "RECOVERY", "BALL LOST")
SENSITIVITY = {"possession_s": (6.0, 12.0, 24.0), "temper": (0.15, 0.3, 0.6)}


def read_tracking(path):
    """(period, frame, positions (n, n_players, 2) in metres, ball (n, 2) in metres)."""
    table = pd.read_csv(path, skiprows=3, header=None)
    values = table.to_numpy(dtype=np.float64)
    pairs = values[:, 3:].reshape(len(values), -1, 2) * np.array(PITCH)
    return values[:, 0].astype(int), values[:, 1].astype(int), pairs[:, :-1], pairs[:, -1]


def load_game(folder):
    stem = os.path.join(folder, os.path.basename(os.path.normpath(folder)))
    period, frame, home, ball = read_tracking(stem + "_RawTrackingData_Home_Team.csv")
    _, frame_away, away, _ = read_tracking(stem + "_RawTrackingData_Away_Team.csv")
    if not np.array_equal(frame, frame_away) or not np.array_equal(frame, np.arange(1, len(frame) + 1)):
        raise ValueError("home and away tracking are not the same contiguous frames")

    players = np.concatenate([home, away], axis=1)
    team = np.array([0] * home.shape[1] + [1] * away.shape[1])
    # No speeds in the sample: metres per frame times fps, NaN where a player is not tracked.
    speed = np.full(players.shape[:2], np.nan)
    speed[1:] = np.sqrt(((players[1:] - players[:-1]) ** 2).sum(axis=2)) * FPS
    track = {"ball": ball.astype(np.float32), "players": players.astype(np.float32),
             "player_speed": speed.astype(np.float32), "team": team}

    blocks = [(int(np.flatnonzero(period == p)[0]), int(np.flatnonzero(period == p)[-1]))
              for p in np.unique(period)]
    events = pd.read_csv(stem + "_RawEventsData.csv")
    return track, blocks, events


def event_labels(events, n_frames, blocks):
    """Per-frame 'H' / 'A' / 'D' / 'X' from the event log, as described in the module docstring."""
    labels = np.full(n_frames, "X", dtype="<U1")
    kind = events["Type"].fillna("").str.upper()
    sub = events["Subtype"].fillna("").str.upper()
    start = events["Start Frame"].to_numpy(dtype=int) - 1
    end = events["End Frame"].to_numpy(dtype=int) - 1
    team = np.where(events["Team"].str.lower() == "home", "H", "A")

    on_ball = kind.isin(ON_BALL).to_numpy()
    restart = ((kind == "SET PIECE") | ((kind == "PASS") & sub.str.contains("GOAL KICK"))).to_numpy()
    stop_at = np.full(len(events), -1)
    stop_at[(kind == "BALL OUT").to_numpy()] = end[(kind == "BALL OUT").to_numpy()]
    shot_dead = ((kind == "SHOT") & (sub.str.contains("OUT") | sub.str.contains("GOAL"))).to_numpy()
    stop_at[shot_dead] = end[shot_dead]
    foul = (kind == "FAULT RECEIVED").to_numpy()
    stop_at[foul] = start[foul]

    for first, last in blocks:
        inside = (start >= first) & (start <= last)
        anchors = np.flatnonzero(inside & on_ball)
        if not len(anchors):
            continue
        anchor_frames = start[anchors]
        order = np.argsort(anchor_frames, kind="stable")
        anchor_frames, anchor_teams = anchor_frames[order], team[anchors][order]
        frames = np.arange(first, last + 1)
        which = np.searchsorted(anchor_frames, frames, side="right") - 1
        labels[first:last + 1] = anchor_teams[np.maximum(which, 0)]

        for index in np.flatnonzero(inside & (stop_at >= 0)):
            dead_from = max(first, min(last, stop_at[index]))
            later = np.flatnonzero((start > dead_from) & (start <= last) & (restart | on_ball))
            restarts = later[restart[later]]
            dead_to = start[restarts[0]] if len(restarts) else (start[later[0]] if len(later) else last + 1)
            labels[dead_from:dead_to] = "D"
    return labels


def nearest_codes(track):
    """Stage v0/v1 input: the baseline's nearest-player team per frame, -1 where no ball."""
    d_home, d_away = features.nearest_distances(track["ball"].astype(np.float64),
                                                track["players"].astype(np.float64), track["team"])
    codes = np.where(d_home <= d_away, 0, 1)
    codes[np.isnan(d_home) & np.isnan(d_away)] = -1
    codes[np.isnan(d_home) & ~np.isnan(d_away)] = 1
    codes[np.isnan(track["ball"][:, 0])] = -1
    return codes


def stage_labels(track, blocks, stage, feats, log_trans=None, temper=evidence.TEMPER):
    codes = nearest_codes(track)
    if stage == "v0":
        labels = smooth(codes, 50).astype("<U1")
        outside = np.ones(len(labels), dtype=bool)
        for first, last in blocks:
            outside[first:last + 1] = False
        labels[outside] = "X"
        return labels
    if stage == "v1":
        emit = evidence.from_labels(codes)
    else:
        emit = evidence.from_features(feats, dead_ball=stage in ("v3", "v5"), fast_ball=stage == "v5")
    emit = emit * (temper / evidence.TEMPER)   # evidence is linear in TEMPER
    return decode_blocks(emit, blocks, FPS, log_trans)


def summarise(result):
    d = result["per_class"]["D"]
    return ("{macro:.4f}  {spell:.4f} [{lo:.3f}, {hi:.3f}]  {npred:>4}/{ngt:<4}  {trans:.3f}  "
            "{ad:.3f}  {team:.3f}  {drec:.3f}").format(
        macro=result["macro_f1"], spell=result["spell_f1_mean"],
        lo=result["spell_bootstrap_low"], hi=result["spell_bootstrap_high"],
        npred=result["n_pred_spells"], ngt=result["n_gt_spells"],
        trans=result["transitions"][25]["f1"], ad=result["alive_dead_f1"],
        team=result["team_acc_gt_alive"], drec=d["recall"])


def main():
    folder = os.path.expanduser(sys.argv[1])
    track, blocks, events = load_game(folder)
    n_frames = len(track["ball"])
    truth = event_labels(events, n_frames, blocks)
    gt = pm.label_codes(truth)

    runs = pm.valid_runs(gt)
    stats = pm.possession_stats(gt, runs)
    graded = truth != "X"
    print("{}: {} frames, ball seen {:.1%}, event-derived truth: alive {:.1%}, "
          "{} possessions of mean {:.1f} s".format(
              os.path.basename(os.path.normpath(folder)), n_frames,
              np.mean(~np.isnan(track["ball"][:, 0])),
              np.mean(np.isin(truth[graded], ["H", "A"])),
              len(pm.possession_spells(gt, runs)), stats["mean_duration_s"]))

    feats = features.compute(track, PITCH, FPS)
    header = "{:<22} macroF1  spellF1 [5-95%]          pred/gt  trans  a/d    team   Drec"
    print("\n" + header.format("stage"))
    for stage in ("v0", "v1", "v2", "v3", "v5"):
        labels = stage_labels(track, blocks, stage, feats)
        print("{:<22} {}".format(stage, summarise(pm.evaluate(gt, pm.label_codes(labels),
                                                               bootstrap_n=BOOTSTRAP_N))))

    print("\nprior sensitivity on v3 (bootstrap {})".format(SENSITIVITY_BOOTSTRAP_N))
    print(header.format("setting"))
    for possession_s in SENSITIVITY["possession_s"]:
        for temper in SENSITIVITY["temper"]:
            log_trans = transition_log_matrix(FPS, possession_s=possession_s)
            labels = stage_labels(track, blocks, "v3", feats, log_trans, temper)
            name = "poss {:>4.0f}s temper {:.2f}".format(possession_s, temper)
            print("{:<22} {}".format(name, summarise(pm.evaluate(
                gt, pm.label_codes(labels), bootstrap_n=SENSITIVITY_BOOTSTRAP_N))))


if __name__ == "__main__":
    main()
