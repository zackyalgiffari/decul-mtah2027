"""Smart Tagging as a per-frame prior on which team has the ball (stage v4).

Every Smart Tagging phase names a team, and most phases imply who has the ball: a Build Up,
Progression or Ball in the Box belongs to the team in possession; a Defending phase or a
Defensive Transition belongs to the team *without* it. That is turned into an odds multiplier on
"home has the ball" for the frames each phase covers, which solution/evidence.py applies on top
of the tracking evidence.

What it is not (DATA.md): ground truth. The tags are automatic, a phase is not a possession, and
36 of them -- every throw-in among them -- carry Team = N/A. Those give no team evidence here.

Tag columns are title case and codes upper case (DATA.md), so everything is compared lower-case.
"""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from games import GAME, GAMES  # noqa: E402
from starter.load_smart_tagging import load  # noqa: E402
from solution.evidence import TAG_TEAM_ODDS  # noqa: E402

# Params
HAS_BALL = ("build up", "progression", "creating chances", "attacking transition",
            "ball in final third", "ball in the box", "players in the box", "long ball",
            "set pieces")
WITHOUT_BALL = ("defending in attacking third", "defending in middle third",
                "defending in defensive third", "defensive transition")
# Team tag values, from DATA.md's table of the file ("Barcelona" 314, "Atletic Club" 288, "N/A"
# 36) and its statement that home is Barcelona. Anything else gives no evidence rather than a
# guessed side.
HOME_TEAMS = ("barcelona", "fc barcelona")
AWAY_TEAMS = ("atletic club", "athletic club")

# v8: restarts as dead-ball evidence. A set piece is a restart, and the ball is dead until it is
# played. The tag marks a window of a few seconds *around* the restart (starter/
# load_smart_tagging.py, checked on the kick-offs), so the dead stretch runs from shortly before
# the tag to its midpoint. Throw-ins carry Team = N/A, which does not matter here: no team needed.
SET_PIECES = "set pieces"
GOALS = "goals"
KICK_OFF_START = "kick off (start)"
KICK_OFF_AFTER_GOAL = "kick off (after goal)"
PRE_RESTART_S = 4.0
SETPIECE_ODDS = 0.1   # odds multiplier on 'alive', as strong as a ball over the line in v3
MAX_GOAL_TO_KICKOFF_S = 180.0   # celebration, walk back, any review: well under three minutes


def side_of(team_tag):
    """'home', 'away' or None for a Team tag value."""
    tag = (team_tag or "").strip().lower()
    if tag in HOME_TEAMS:
        return "home"
    if tag in AWAY_TEAMS:
        return "away"
    return None


def team_prior(n_frames, game=None, data_dir=None):
    """Per-frame odds multiplier on home: >1 favours home, <1 away, 1 says nothing."""
    events = load(data_dir=data_dir) if game is None else load(game=game, data_dir=data_dir)
    log_odds = np.zeros(n_frames)
    for event in events:
        code = (event["code"] or "").strip().lower()
        if code in HAS_BALL:
            sign = 1.0
        elif code in WITHOUT_BALL:
            sign = -1.0
        else:
            continue
        side = side_of(event["tags"].get("Team"))
        if side is None:
            continue
        if side == "away":
            sign = -sign
        start = max(0, event["start_frame"])
        stop = min(n_frames, event["end_frame"])
        # Overlapping phases that agree add up; ones that disagree cancel out.
        log_odds[start:stop] += sign * np.log(TAG_TEAM_ODDS)
    return np.exp(np.clip(log_odds, -2 * np.log(TAG_TEAM_ODDS), 2 * np.log(TAG_TEAM_ODDS)))


def dead_odds_from_events(events, n_frames, fps):
    """v8: per-frame odds multiplier on 'alive' from restarts. 1 says nothing, < 1 means dead.

    - a set piece: dead from PRE_RESTART_S before its tag to the tag's midpoint;
      a kick-off that starts a half: only before its tag (the half starts with the ball in play)
    - a goal followed by a kick-off after the goal: dead from the goal tag's end to that tag's start
    Values are assigned, not multiplied, so overlapping tags do not compound.
    """
    odds = np.ones(n_frames)
    pre = int(round(PRE_RESTART_S * fps))

    def code(event):
        return (event["code"] or "").strip().lower()

    def kind(event):
        return (event["tags"].get("Type") or "").strip().lower()

    set_pieces = sorted((e for e in events if code(e) == SET_PIECES), key=lambda e: e["start_frame"])
    for event in set_pieces:
        start, end = event["start_frame"], event["end_frame"]
        stop = start if kind(event) == KICK_OFF_START else (start + end) // 2
        odds[max(0, start - pre):max(0, min(n_frames, stop))] = SETPIECE_ODDS

    # Pair each goal with the first kick-off after it starts, and only within MAX_GOAL_TO_KICKOFF_S,
    # so a goal tag that overlaps its own kick-off can never be paired with a later goal's.
    kick_offs = [e for e in set_pieces if kind(e) == KICK_OFF_AFTER_GOAL]
    max_gap = int(round(MAX_GOAL_TO_KICKOFF_S * fps))
    for goal in (e for e in events if code(e) == GOALS):
        following = [e for e in kick_offs
                     if goal["start_frame"] <= e["start_frame"] <= goal["end_frame"] + max_gap]
        if following and following[0]["start_frame"] > goal["end_frame"]:
            odds[max(0, goal["end_frame"]):min(n_frames, following[0]["start_frame"])] = SETPIECE_ODDS
    return odds


def dead_odds(n_frames, game=GAME, data_dir=None):
    """v8 restart evidence for the match, from its Smart Tagging file."""
    return dead_odds_from_events(load(game=game, data_dir=data_dir), n_frames, GAMES[game]["fps"])
