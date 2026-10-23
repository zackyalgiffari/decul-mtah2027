"""Synthetic checks for solution/: no match data involved.

    python tests/test_pipeline.py
"""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from solution import evidence, features  # noqa: E402
from solution.decode import A, D, H, STATES, transition_log_matrix, viterbi, decode_match  # noqa: E402
from solution.tagging import side_of  # noqa: E402

FPS = 25
TRANS = transition_log_matrix(FPS)
HOME, AWAY, NONE = 0, 1, -1
failures = []


def check(name, condition):
    print("{:<55} {}".format(name, "ok" if condition else "FAIL"))
    if not condition:
        failures.append(name)


def decode_codes(codes):
    return "".join(STATES[viterbi(evidence.from_labels(np.array(codes)), TRANS)])


# 1. a short flicker inside a possession is ignored
codes = [HOME] * 200 + [AWAY] * 10 + [HOME] * 200
check("10-frame flicker inside a home possession removed", set(decode_codes(codes)) == {"H"})

# 2. a sustained change is kept, close to where it happens
codes = [HOME] * 300 + [AWAY] * 300
path = decode_codes(codes)
switch = path.index("A") if "A" in path else -1
check("sustained switch kept", path[0] == "H" and path[-1] == "A")
check("switch within 1 s of the truth (frame 300): {}".format(switch), abs(switch - 300) <= FPS)

# 3. a long stretch without the ball becomes dead ball, a short one does not
codes = [HOME] * 300 + [NONE] * 400 + [AWAY] * 300
path = decode_codes(codes)
check("10 s without the ball decoded as D somewhere", "D" in path)
codes = [HOME] * 300 + [NONE] * 15 + [HOME] * 300
check("0.6 s without the ball stays H", set(decode_codes(codes)) == {"H"})

# 4. halves decoded separately, X outside them
emit = evidence.from_labels(np.full(199319, HOME))
labels = decode_match(emit)
check("frames before kickoff are X", labels[0] == "X" and labels[11184] == "X")
check("first and last graded frames labelled", labels[11185] != "X" and labels[190197] != "X")
check("halftime is X", labels[100000] == "X")

# 5. deterministic
check("two decodes identical", np.array_equal(decode_match(emit), labels))

# 6. features on a toy track: ball at a home player's feet, away player far
n = 100
track = {
    "ball": np.tile([[50.0, 30.0]], (n, 1)).astype(np.float32),
    "players": np.tile([[[50.5, 30.0], [60.0, 30.0]]], (n, 1, 1)).astype(np.float32),
    "player_speed": np.full((n, 2), 2.5, dtype=np.float32),
    "team": np.array([0, 1]),
}
track["ball"][40:45] = np.nan          # a 5-frame gap, interpolated
track["ball"][80:100] = np.nan         # a long gap at the end, not interpolated
f = features.compute(track, (105.3, 68.0), FPS)
check("short ball gap interpolated", f["ball_seen"][40:45].all())
check("trailing gap not invented", not f["ball_seen"][85:].any())
check("nearest distances in metres", abs(f["d_home"][0] - 0.5) < 1e-6 and abs(f["d_away"][0] - 10) < 1e-6)
emit = evidence.from_features(f, dead_ball=True)
check("home favoured when home player is at the ball", (emit[:40, H] > emit[:40, A]).all())

# 7. ball over the line pushes towards D
track["ball"][:] = [[-3.0, 30.0]]
f = features.compute(track, (105.3, 68.0), FPS)
emit = evidence.from_features(f, dead_ball=True)
check("ball over the line flagged", f["ball_out"][:80].all())
check("ball over the line favours D", (emit[:80, D] > np.maximum(emit[:80, H], emit[:80, A])).all())

# 8. v5: a fast ball passing a home player gives no team evidence; a slow one does
n = 60
track = {
    "ball": np.stack([np.linspace(30.0, 54.0, n), np.full(n, 30.0)], axis=1).astype(np.float32),
    "players": np.tile([[[42.0, 30.5], [70.0, 30.0]]], (n, 1, 1)).astype(np.float32),
    "player_speed": np.full((n, 2), 2.5, dtype=np.float32),
    "team": np.array([0, 1]),
}  # ball moves 24 m in 59 frames = ~10 m/s, past the home player at x = 42
f = features.compute(track, (105.3, 68.0), FPS)
fast = evidence.from_features(f, fast_ball=True)
slow = evidence.from_features(f, fast_ball=False)
middle = slice(25, 35)
check("ball speed measured (~10 m/s): {:.1f}".format(np.nanmedian(f["ball_speed"])),
      9.0 < np.nanmedian(f["ball_speed"]) < 11.0)
check("v5: fast ball past a home player is not home evidence",
      np.allclose(fast[middle, H], fast[middle, A]))
check("without v5 the same frames favour home", (slow[middle, H] > slow[middle, A]).all())

# 9. v6: a ball standing still on the touchline waits for a restart; mid-pitch it does not
n = 100
track = {
    "ball": np.tile([[50.0, 0.3]], (n, 1)).astype(np.float32),
    "players": np.tile([[[50.0, 1.0], [52.0, 3.0]]], (n, 1, 1)).astype(np.float32),
    "player_speed": np.full((n, 2), 1.5, dtype=np.float32),
    "team": np.array([0, 1]),
}
f = features.compute(track, (105.3, 68.0), FPS)
with_cue = evidence.from_features(f, dead_ball=True, restart=True)
without = evidence.from_features(f, dead_ball=True, restart=False)
check("v6: static ball on the touchline flagged", f["restart_spot"][20:80].all())
check("v6: restart cue raises D", (with_cue[20:80, D] > without[20:80, D]).all())
track["ball"][:] = [[30.0, 20.0]]
f = features.compute(track, (105.3, 68.0), FPS)
check("v6: static ball mid-pitch not a restart spot", not f["restart_spot"].any())

# 10. v7: EM sharpens a weak but correct dead-ball signal, deterministically
from solution import adapt  # noqa: E402

S_ALIVE, S_DEAD = 20, 4
truth = np.concatenate([np.r_[np.zeros(500), np.ones(250)] for _ in range(8)]).astype(bool)  # True = dead
symbol = np.where(truth, S_DEAD, S_ALIVE)
symbol[::5] = np.where(truth[::5], S_ALIVE, S_DEAD)   # 20% of frames show the other regime's symbol
p_home = np.full(len(symbol), 0.5)
weak_alive = np.full(adapt.N_SYMBOLS, 1e-3)
weak_dead = np.full(adapt.N_SYMBOLS, 1e-3)
weak_alive[[S_ALIVE, S_DEAD]] = [0.52, 0.48]      # barely tells the regimes apart
weak_dead[[S_ALIVE, S_DEAD]] = [0.48, 0.52]
init = evidence.combine_logs(np.log(weak_alive)[symbol], np.log(weak_dead)[symbol], p_home)
blocks = [(0, len(symbol) - 1)]
log_alive, log_dead = adapt.fit(symbol, p_home, init, blocks, FPS)
learned = evidence.combine_logs(log_alive[symbol], log_dead[symbol], p_home)


def dead_recall(log_emit):
    path = viterbi(log_emit, TRANS)
    return float(np.mean(path[truth] == D))


before, after = dead_recall(init), dead_recall(learned)
check("v7: EM learns the dead symbol (log ratio {:+.2f})".format(log_dead[S_DEAD] - log_alive[S_DEAD]),
      log_dead[S_DEAD] - log_alive[S_DEAD] > 1.0)
check("v7: dead-ball recall {:.2f} -> {:.2f}".format(before, after), after > before and after > 0.9)
again = adapt.fit(symbol, p_home, init, blocks, FPS)
check("v7: EM is deterministic", np.array_equal(again[0], log_alive) and np.array_equal(again[1], log_dead))

# 11. v8: restarts from Smart Tagging
from solution.tagging import SETPIECE_ODDS, dead_odds_from_events  # noqa: E402


def tag(code, start, end, **tags):
    return {"code": code, "start_frame": start, "end_frame": end, "tags": tags}


events = [
    tag("SET PIECES", 50, 175, Type="Kick Off (Start)", Team="Barcelona"),
    tag("SET PIECES", 1000, 1125, Type="Throw-in", Team="N/A"),
    tag("GOALS", 1300, 1350, Team="Barcelona"),
    tag("SET PIECES", 1700, 1825, Type="Kick Off (After Goal)", Team="Atletic Club"),
    tag("BUILD UP", 400, 900, Team="Barcelona"),
]
odds = dead_odds_from_events(events, 2000, FPS)
check("v8: dead before a set piece and up to its midpoint",
      (odds[900:1062] == SETPIECE_ODDS).all() and odds[899] == 1 and odds[1062] == 1)
check("v8: throw-in with Team N/A still counts", odds[1000] == SETPIECE_ODDS)
check("v8: goal to kick-off after goal is dead", (odds[1350:1762] == SETPIECE_ODDS).all())
check("v8: half-opening kick-off is dead only before its tag", odds[0] == SETPIECE_ODDS
      and odds[49] == SETPIECE_ODDS and (odds[50:200] == 1).all())
check("v8: other tags give no dead-ball evidence", (odds[400:899] == 1).all())
far = [tag("GOALS", 100, 300), tag("SET PIECES", 250, 375, Type="Kick Off (After Goal)"),
       tag("GOALS", 5000, 5050), tag("SET PIECES", 5800, 5925, Type="Kick Off (After Goal)")]
odds = dead_odds_from_events(far, 20000, FPS)
check("v8: a goal overlapping its kick-off never pairs with a later one",
      (odds[400:4900] == 1).all() and (odds[5050:5800] == SETPIECE_ODDS).all())

# 12. Smart Tagging team names
check("tag team names mapped", side_of("Barcelona") == "home" and side_of("Atletic Club") == "away"
      and side_of("N/A") is None)

print("\n{} failure(s)".format(len(failures)))
sys.exit(1 if failures else 0)
