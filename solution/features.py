"""Per-frame features from the ATD arrays (solution/atd.py), for solution/evidence.py.

    ball_seen      bool   ball position known: observed, or interpolated across a short gap
    d_home, d_away float  metres from the ball to the nearest home / away player (NaN if unknown)
    ball_out       bool   ball beyond the lines by more than OUT_MARGIN_M
    player_speed   float  mean speed of all tracked players, averaged over a centred window
    ball_speed     float  m/s over the last BALL_SPEED_FRAMES (NaN where unknown)
    ball_static    bool   ball seen and barely moving for a whole centred window
    restart_spot   bool   ball static on a line or on the centre spot: waiting for a restart

Short gaps in the ball track are interpolated because the ball vanishes for a few frames in
every crowded moment; long gaps are left alone, because inventing a ball position for seconds
at a time would invent who had it.
"""

import numpy as np

# Params
MAX_GAP_FRAMES = 12        # interpolate ball gaps up to 0.5 s
OUT_MARGIN_M = 0.5         # tracker noise allowance before a ball counts as over the line
SPEED_WINDOW_FRAMES = 50   # +/- 2 s for the mean player speed
STATIC_WINDOW_FRAMES = 12  # +/- 0.5 s with the ball under STATIC_MS counts as standing still
STATIC_MS = 0.5
BALL_SPEED_FRAMES = 5      # ball speed measured over 0.2 s, enough to average out jitter
# A throw-in, corner or kick-off is taken with the ball on a line or on the centre spot. Goal
# kicks and free kicks are left out: a goalkeeper holding the ball in the goal area, or a player
# standing on it in midfield, looks the same and is in possession.
RESTART_ZONE_M = 1.5


def interpolate_gaps(track, max_gap):
    """Linear interpolation of NaN runs no longer than max_gap, between two known points."""
    track = track.copy()
    known = ~np.isnan(track[:, 0])
    index = np.flatnonzero(known)
    if len(index) < 2:
        return track
    gaps = np.diff(index)
    for start, gap in zip(index[:-1][(gaps > 1) & (gaps <= max_gap + 1)],
                          gaps[(gaps > 1) & (gaps <= max_gap + 1)]):
        stop = start + gap
        weights = np.arange(1, gap)[:, None] / float(gap)
        track[start + 1:stop] = track[start] + weights * (track[stop] - track[start])
    return track


def centred_mean(values, half_width):
    """NaN-aware mean over a centred window, via cumulative sums (cost independent of width)."""
    valid = ~np.isnan(values)
    sums = np.concatenate(([0.0], np.cumsum(np.where(valid, values, 0.0))))
    counts = np.concatenate(([0], np.cumsum(valid)))
    index = np.arange(len(values))
    low = np.maximum(0, index - half_width)
    high = np.minimum(len(values), index + half_width + 1)
    count = counts[high] - counts[low]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, (sums[high] - sums[low]) / np.maximum(count, 1), np.nan)


def nearest_distances(ball, players, team):
    """Metres from the ball to the nearest home (team 0) and away (team 1) player, per frame."""
    distance = np.sqrt(((players - ball[:, None, :]) ** 2).sum(axis=2))
    distance = np.where(np.isnan(distance), np.inf, distance)
    d_home = distance[:, team == 0].min(axis=1)
    d_away = distance[:, team == 1].min(axis=1)
    d_home[~np.isfinite(d_home)] = np.nan
    d_away[~np.isfinite(d_away)] = np.nan
    return d_home, d_away


def compute(track, pitch, fps):
    """Feature dict for every frame, from solution.atd.load() output."""
    ball = interpolate_gaps(track["ball"].astype(np.float64), MAX_GAP_FRAMES)
    ball_seen = ~np.isnan(ball[:, 0])
    d_home, d_away = nearest_distances(ball, track["players"].astype(np.float64), track["team"])

    length, width = pitch
    with np.errstate(invalid="ignore"):
        ball_out = ball_seen & ((ball[:, 0] < -OUT_MARGIN_M) | (ball[:, 0] > length + OUT_MARGIN_M)
                                | (ball[:, 1] < -OUT_MARGIN_M) | (ball[:, 1] > width + OUT_MARGIN_M))

    speeds = track["player_speed"].astype(np.float64)
    tracked = ~np.isnan(speeds)
    n_tracked = tracked.sum(axis=1)
    mean_speed = np.where(n_tracked > 0,
                          np.where(tracked, speeds, 0.0).sum(axis=1) / np.maximum(n_tracked, 1),
                          np.nan)
    player_speed = centred_mean(mean_speed, SPEED_WINDOW_FRAMES)

    step = np.full(len(ball), np.nan)
    moved = np.sqrt(((ball[BALL_SPEED_FRAMES:] - ball[:-BALL_SPEED_FRAMES]) ** 2).sum(axis=1))
    step[BALL_SPEED_FRAMES:] = moved * fps / BALL_SPEED_FRAMES
    slow = np.where(np.isnan(step), 0.0, (step < STATIC_MS).astype(float))
    seen = np.where(np.isnan(step), 0.0, 1.0)
    window = 2 * STATIC_WINDOW_FRAMES + 1
    slow_count = np.convolve(slow, np.ones(window), mode="same")
    seen_count = np.convolve(seen, np.ones(window), mode="same")
    ball_static = (seen_count == window) & (slow_count == window)

    with np.errstate(invalid="ignore"):
        to_line = np.fmin(np.fmin(np.abs(ball[:, 0]), np.abs(ball[:, 0] - length)),
                          np.fmin(np.abs(ball[:, 1]), np.abs(ball[:, 1] - width)))
        to_centre = np.hypot(ball[:, 0] - length / 2.0, ball[:, 1] - width / 2.0)
        restart_spot = ball_static & ((to_line <= RESTART_ZONE_M) | (to_centre <= RESTART_ZONE_M))

    return {"ball_seen": ball_seen, "d_home": d_home, "d_away": d_away, "ball_out": ball_out,
            "player_speed": player_speed, "ball_speed": step, "ball_static": ball_static,
            "restart_spot": restart_spot}
