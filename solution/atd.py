"""Read the tactical ATD into arrays once, and cache them next to the data.

starter/baseline.py streams the raw file and keeps only the nearest player per frame. The Decul
stages need more -- every tracked position, every speed -- so this reads the same file in the
same format into arrays:

    ball          (n_frames, 2)            metres, NaN where the tracker lost the ball
    players       (n_frames, n_slots, 2)   metres, NaN where a slot is empty
    player_speed  (n_frames, n_slots)      m/s as the tracker reports it
    team          (n_slots,)               0 home, 1 away (starter/baseline.py's convention)

Row i is video frame i: the ATD counts frame_id from 1, submissions from 0 (DATA.md, "Frame
alignment").

The parse takes a minute or two, so the arrays are cached as data/cache/<stem>.npz -- inside the
gitignored, guarded data folder, because they are the data in another shape. The cache is reused
only while the raw file's size and modification time match the ones it was built from.
"""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from games import GAME, GAMES, require, source_frames  # noqa: E402
from starter.baseline import FIELD_SEP, GROUP_SEP, team_of_each_track  # noqa: E402

# Params
CACHE_DIR = "cache"
CACHE_VERSION = 1   # bump when the arrays below change shape or meaning


def _fields(group, count):
    """First `count` comma-separated values of a group as strings; missing or empty -> 'nan'."""
    values = [value if value else "nan" for value in group.split(",")[:count]]
    return values + ["nan"] * (count - len(values))


def parse(raw_path, n_slots, n_frames, pitch):
    """Raw ATD text -> (ball, players, player_speed) arrays, see the module docstring."""
    length, width = pitch
    scale = np.array([length, width], dtype=np.float32)
    ball = np.full((n_frames, 2), np.nan, dtype=np.float32)
    players = np.full((n_frames, n_slots, 2), np.nan, dtype=np.float32)
    speed = np.full((n_frames, n_slots), np.nan, dtype=np.float32)

    with open(raw_path) as handle:
        for line in handle:
            parts = line.rstrip().split(FIELD_SEP)
            if len(parts) != 3:
                continue
            row = int(parts[0]) - 1
            if not 0 <= row < n_frames:
                continue

            groups = parts[1].split(GROUP_SEP)[:n_slots]
            if groups and groups != [""]:
                values = np.array([_fields(group, 3) for group in groups], dtype=np.float32)
                players[row, :len(groups)] = values[:, :2] * scale
                speed[row, :len(groups)] = values[:, 2]

            ball[row] = np.array(_fields(parts[2], 2), dtype=np.float32) * scale
    return ball, players, speed


def _stamp(path):
    status = os.stat(path)
    return np.array([status.st_size, int(status.st_mtime), CACHE_VERSION], dtype=np.int64)


def load(game=GAME, data_dir=None, source="tactical", use_cache=True):
    """Arrays for one source, from the cache when it is current, else parsed and cached."""
    meta_path, raw_path = require(["atd_meta", "atd_raw"], game, data_dir, source)
    team = team_of_each_track(meta_path)
    stamp = _stamp(raw_path)

    cache_dir = os.path.join(os.path.dirname(os.path.dirname(raw_path)), CACHE_DIR)
    cache_path = os.path.join(cache_dir, os.path.splitext(os.path.basename(raw_path))[0] + ".npz")
    if use_cache and os.path.isfile(cache_path):
        cached = np.load(cache_path)
        if np.array_equal(cached["stamp"], stamp):
            return {name: cached[name] for name in ("ball", "players", "player_speed", "team")}

    ball, players, player_speed = parse(raw_path, len(team), source_frames(source, game),
                                        GAMES[game]["pitch"])
    if use_cache:
        os.makedirs(cache_dir, exist_ok=True)
        np.savez(cache_path, ball=ball, players=players, player_speed=player_speed, team=team,
                 stamp=stamp)
    return {"ball": ball, "players": players, "player_speed": player_speed, "team": team}
