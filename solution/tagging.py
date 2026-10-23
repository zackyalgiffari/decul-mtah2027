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
