# Team Decul — Technical document

More than a Hack 2027, Phase 1: frame-level ball possession.
Submission file: `Decul.csv` (stage v4). Repository: https://github.com/zackyalgiffari/decul-mtah2027

**Summary.** We separate what each frame says (evidence) from which sequence of possessions best
explains the whole half (decoding), and decode with a three-state hidden Markov model (H, A, D)
solved exactly by Viterbi. Evidence comes from the tracking — metres from the ball to the nearest
home and away player, whether the ball is seen, over the line, or still, and how fast the players
move — plus a Smart Tagging prior. On two public Metrica matches (≈330 possessions each) the
decoder with distance evidence beats the published baseline by 0.13 spellF1 with
non-overlapping bootstrap intervals; on the competition's public five minutes the submitted
stage scores spellF1 0.4316 against the baseline's 0.3256 (17 possessions, so those intervals
still overlap; that window is a correctness check and chose nothing). The submitted stage was
fixed before any score existed, and nothing in it is trained or tuned on the provided game.

---

## 1. Approach

The ranking metric scores whole possessions, so the failure to avoid is flicker: a per-frame
rule that switches team for a few frames invents possessions and scores near zero even when most
frames are right. Hence the split between evidence and decoding.

- **Decoding** (`solution/decode.py`). Every change of state has a price set by football priors —
  a possession lasts around 12 s, a stoppage around 15 s, and three in four possessions end in an
  open-play turnover rather than a stoppage. A change happens only when the evidence outweighs
  the price, so strong sustained evidence switches within a second while missing evidence leaves
  the state alone. Unlike a fixed smoothing window, this keeps short real possessions and removes
  short false ones. Each half is decoded on its own; frames outside the halves are `X`.
- **Evidence** (`solution/evidence.py`, `solution/features.py`, `solution/tagging.py`). Per frame,
  P(ball alive) and P(home | alive), combined into log-likelihoods and tempered by 0.3, because
  consecutive frames are not independent witnesses.

The pipeline was built in stages so each layer's contribution could be measured on its own
(`make_submission.py --stage`):

| stage | adds | status |
|---|---|---|
| v0 | published baseline: nearest player, majority vote ±2 s | reference |
| v1 | Viterbi instead of the vote, same signal | kept |
| v2 | team evidence from metres to the nearest home and away player; ball gaps ≤ 0.5 s interpolated | kept |
| v3 | dead-ball evidence: ball over the line, players walking, ball standing still | kept |
| v4 | Smart Tagging as a prior on which team has the ball | **submitted** |
| v5 | no team evidence while the ball travels faster than 7 m/s | tried, dropped |
| v6 | a ball standing still on a line or the centre spot counts towards a stoppage | tried, dropped |
| v7 | v4 with the alive/dead evidence learned from the match itself by EM (`solution/adapt.py`) | tried, dropped |
| v8 | v4 + Smart Tagging restarts (set pieces, goal → kick-off) as dead-ball evidence | tried, dropped |

Parameters are football priors written in each module's `# Params` block, set by hand before any
score existed and checked only on external data (two public Metrica matches, below). None was
searched on the competition's public five minutes, and the submitted pipeline learns nothing from
the provided game. The submitted stage, v4, was the default before the first score was computed,
and its parameters have not changed since (see *How the submitted stage was chosen*).

### Results on the competition's public five minutes

17 possessions; 5–95% block-bootstrap interval, 1000 draws. This window checks that the pipeline
is correct — frames aligned, file well-formed, labels meaning what we think. It is not a tuning
set and does not choose between stages; the table is reported for completeness.

| stage | macroF1 | spellF1 [5–95%] | possessions (truth 17) | alive/dead F1 |
|---|---|---|---|---|
| v0 = published baseline | 0.6207 | 0.3256 [0.214, 0.447] | 26 | 0.899 |
| v1 | 0.6362 | 0.3304 [0.217, 0.444] | 29 | 0.893 |
| v2 | 0.6518 | 0.3333 [0.200, 0.467] | 25 | 0.893 |
| v3 | 0.6816 | 0.3707 [0.234, 0.498] | 24 | 0.913 |
| **v4** | **0.6821** | **0.4316** [0.284, 0.590] | 21 | **0.924** |
| v5 | 0.6754 | 0.4000 [0.244, 0.556] | 19 | 0.924 |
| v6 | 0.6754 | 0.4000 [0.244, 0.556] | 19 | 0.924 |
| v7 | 0.6593 | 0.3800 [0.240, 0.520] | 23 | 0.911 |
| v8 | 0.6868 | 0.3784 [0.227, 0.541] | 20 | 0.909 |

Over the full match the number of predicted possessions falls from 669 (v0) to 366 (v4), with
mean duration rising from 7.6 s to 10.5 s; dead ball covers 39% of graded frames, in line with
the 55–60 minutes of effective playing time typical of a top-flight match. v0 reproduces the
published baseline exactly, and v1 computed from the ATD equals v1 computed from the published
`baseline_raw.csv`, which confirms the parsing and the frame alignment.

### Validation on two public matches

To rank stages with more than 17 possessions, we also scored them on Metrica's public sample
matches (Sample Game 1 and 2), whose event logs give a possession label for every frame. The
labels are derived mechanically from the events (`validation/metrica_public.py` documents the
rule); that is not the competition's tracking-based definition, and the sample tracking is
cleaner, so these numbers compare stages with each other and do not predict the competition
score. Smart Tagging is not available there, so v4 and v6 cannot be run. spellF1, 5–95% interval:

| stage | Sample Game 1 (328 possessions) | Sample Game 2 (330 possessions) |
|---|---|---|
| v0 baseline | 0.399 [0.367, 0.433] | 0.397 [0.366, 0.429] |
| v1 Viterbi | 0.472 [0.437, 0.510] | 0.476 [0.441, 0.514] |
| v2 distances | 0.527 [0.489, 0.567] | 0.534 [0.494, 0.575] |
| v3 dead ball | 0.511 [0.473, 0.550] | 0.533 [0.492, 0.573] |
| v5 fast ball | 0.520 [0.468, 0.571] | 0.542 [0.492, 0.591] |
| v7 EM (= v3 + EM here) | 0.508 [0.471, 0.545] | 0.533 [0.494, 0.572] |

- The decoder and the distance evidence are a real gain: v2 beats the baseline on both matches
  with non-overlapping intervals.
- v3, part of the planned pipeline, keeps spellF1 and raises dead-ball recall on Game 1
  (0.75 → 0.80) and alive/dead F1.
- The priors are not fragile: an expected possession of 6, 12 or 24 s gives the same result
  within noise, while doubling the tempering to 0.6 is clearly worse on both matches and halving
  it to 0.15 halves the number of predicted possessions. The submitted values sit in the stable
  region and were not changed.

### How the submitted stage was chosen

Two rules were written into the project plan before any score existed (`docs/ROADMAP.md`,
commit `97760cc`): the full pipeline v0–v4 is the submission, and a change is adopted only if it
is shown to be better — when two versions cannot be told apart, the simpler one stays.
`DEFAULT_STAGE = "v4"` is in `make_submission.py` from its first commit (`75b971e`), made before
the first run on the data, and every v0–v4 parameter is still the one of that commit.

v4 itself cannot be tested on external data: Metrica's public matches have no Smart Tagging. It is
submitted because it is the planned design, with a deliberately modest tag prior (odds ×2, because
a phase is not a possession), not because it scored best anywhere.

v5–v8 were explored afterwards, one weakness at a time, and **none was adopted**, so the submitted
file is the one we would have produced had they never been tried. While working we also read
their scores on the public five minutes (table above). Under the rules that window chooses
nothing, so the reasons that stand are the ones that do not use it:

| stage | evidence without the public window | decision |
|---|---|---|
| v5 | on both Metrica matches it predicts far too few possessions (216 vs 328, 198 vs 330); spellF1 interval overlaps v2 and v3 | not shown better → not adopted |
| v6 | changes about 390 frames of the whole match: stoppages here are rarely a ball standing on a line | no measurable effect → not adopted |
| v7 | level with v3 on both Metrica matches (0.508 vs 0.511, 0.533 vs 0.533) | simpler hand-set evidence stays |
| v8 | no external test possible (no Smart Tagging in Metrica's matches); full-match dead-ball share rises from 39% to 45% | not shown better → not adopted, and not retuned |

### What the explorations showed

These observations explain the limitations in §5. The public-window numbers are diagnostics of
behaviour, not grounds for the decision above.

- **v5** removed spurious possessions (full match 366 → 316) but matched fewer changes of
  possession in time: an interception happens exactly when a fast ball is cut out, so ignoring
  fast balls removed the evidence at the moment that mattered.
- **v7** tested whether the dead-ball weakness was a tuning problem. The hand-set alive/dead
  evidence fits Metrica's cleaner tracking (dead-ball recall 0.80–0.90) far better than this
  match's (0.32 on the public window), so v7 learned it from the match itself, without labels,
  by Baum–Welch on a 32-symbol description of each frame (ball seen, over the line, player-speed
  bin, ball still), keeping the team evidence and the transition priors fixed. Dead-ball recall
  did not move (0.322 → 0.323). The missed stoppages look like live play in every tracking
  feature we have — an information limit, not a tuning one. v7 is the only stage that learns
  anything from the provided game, and it is not in the submission.
- **v8** therefore brought new information: every Smart Tagging set piece is a restart, so play
  is dead shortly before it, and a goal is followed by a dead stretch until the kick-off. It
  found more stoppages (dead-ball recall 0.32 → 0.46) but turned live play into dead ball too
  (precision 1.00 → 0.66): the tags locate restarts only to within a few seconds, too coarsely to
  place dead-ball boundaries frame by frame. Moving or weakening the window would have meant
  fitting four public stoppages, which the rules exclude, so v8 was left as built.

v5–v8 remain in the code as ablations (`--stage`).

## 2. Assets used and dropped

| asset | used? | how / why not |
|---|---|---|
| Tactical ATD (tracking) | yes | ball and player positions and speeds, every frame |
| Smart Tagging | yes (v4) | team of possession-implying phases as a prior; `N/A` tags ignored. Restart timing as dead-ball evidence tried (v8) and dropped: too coarse in time |
| Homography | no | only needed to go between pitch and video, and we do not use the video |
| Tactical video | no | the tracking already encodes it; ball detection from video left as future work |
| Broadcast video, ATD, homography | no | not synchronised to the tactical timeline; adds alignment risk |
| Metrica public sample matches | validation only | event-labelled matches to rank stages and check the priors |

### Labelled data

No labels on the provided game were used for training, tuning or validation, and nothing about it
was produced or corrected by hand. Every label the submission outputs comes from the algorithm.
The only labelled data is external, and nothing is trained on it:

| dataset | source | labelled by | amount | used for |
|---|---|---|---|---|
| Metrica Sports sample data, Sample Game 1 and 2 (anonymised; synchronised tracking and events) | [github.com/metrica-sports/sample-data](https://github.com/metrica-sports/sample-data) | event data by Metrica Sports; per-frame H/A/D derived from the events by a fixed rule in our code (`validation/metrica_public.py`), with no hand labels of ours | 2 matches, 328 + 330 possessions | ranking stages v0–v3, v5 and v7; checking the sensitivity of the priors |
| the organisers' public five minutes | `evaluation/gt/` | the organisers | 17 possessions | checking correctness (alignment, file format, label meaning) only |

We thank Metrica Sports for publishing the sample data.

## 3. Handling missing and noisy tracking

The tracking is automatic and uncorrected (DATA.md): the ball is missing on 41% of graded frames,
there are 46 track slots for 22 players, and slots appear, vanish, swap identity and occasionally
duplicate a player. The pipeline is built so that none of this has to be repaired first.

- **Short ball gaps are filled, long ones are not.** A gap of up to 0.5 s between two known ball
  positions is interpolated linearly (`solution/features.py`); a longer one is left unknown,
  because inventing a ball position for seconds would invent who had it.
- **An unknown ball is evidence of nothing, not of a change.** With no ball, or a ball more than
  3 m from every player, P(home | alive) is 0.5. The decoder then has no reason to pay the price
  of a change of possession and keeps the current team — the "loose ball stays with the last
  team" rule of CHALLENGE.md, applied to occlusions as well.
- **A missing ball is weak dead-ball evidence, never proof.** P(alive) drops from 0.78 (ball
  seen) to 0.27 (ball not seen), so a long stretch without the ball and with slow players
  becomes a stoppage, while a ball hidden for a moment in a crowded box does not.
- **No player identities are needed.** Every feature is team-level: the distance from the ball to
  the nearest home and the nearest away player, and the mean speed of all tracked players. An
  identity switch or a fragmented track changes nothing; a duplicated track repeats a distance
  that is already counted; an empty slot (NaN) is skipped.
- **Noise is averaged before it is believed.** Player speed is averaged over all tracked players
  and over ±2 s; ball speed is measured over 0.2 s; a ball counts as still only after a whole
  second below 0.5 m/s, and as over the line only 0.5 m beyond it.
- **Consecutive frames are not independent witnesses.** The same occlusion or the same player
  standing near the ball repeats a reading 25 times a second, so all evidence is tempered (×0.3):
  about a second of consistent evidence is needed to change state, which removes flicker without
  a fixed smoothing window.
- **Each half is decoded on its own**, so nothing carries across halftime, and only the tactical
  recording is used: the broadcast feed has its own unsynchronised timeline and a third of its
  frames have no usable homography.

## 4. Possession rules implemented

- **Loose and contested balls** stay with the team that last had possession: when the ball is
  more than 3 m from every player, or not tracked, the frame carries no team evidence and the
  decoder keeps the current state.
- **Control** means being nearest the ball within 3 m, weighted by how much closer the home
  player is than the away player (each metre multiplies the odds by e). A brief touch or a
  deflection gives evidence for well under a second and does not outweigh the price of a change
  of possession.
- **Dead ball** is evidenced by the ball beyond the lines, players walking (mean speed well under
  the ~2 m/s of live play) and a ball standing still; a ball merely lost by the tracker for a
  moment is not a stoppage.
- **Smart Tagging** phases that imply possession (Build Up, Progression, Ball in the Box, Set
  Pieces, …) favour the tagged team; Defending phases and Defensive Transitions favour the other
  team. Tags with team `N/A` are ignored.
- **Restarts** are not forced: after a stoppage the possessing team is whichever the evidence
  favours once play resumes.

## 5. Limitations

- **Stoppages with a visible ball.** The largest remaining error is dead ball labelled as play
  (v4, public window: 996 of 1,469 dead-ball frames predicted H or A; every frame predicted D was
  correct). A ball placed for a throw-in or a free kick looks like a ball at a player's feet. A
  restart cue for balls standing on a line (v6) did not fire often enough to help, and learning
  the dead-ball evidence from the match (v7) did not separate them either: the tracking alone
  does not carry the information. Smart Tagging restarts (v8) carry some of it, but too
  coarsely in time — they found more stoppages while cutting into live play. Detecting the ball
  and the restart from video is the remaining route.
- **Validation.** The competition's labelled data is five minutes with 17 possessions. The larger
  check on two public Metrica matches uses event-derived labels and cleaner tracking, so it
  supports the ranking of stages but not their absolute scores. It cannot test v4: Metrica's
  matches have no Smart Tagging, so the tag prior — modest by design and fixed before any score
  — is the one part of the submission with no external check.
- **Hand-set priors.** Durations, distances and odds come from football knowledge, not learning;
  a model trained on labelled matches could set them better.
- **No video.** The ball is missing on 41% of graded frames and we do not re-detect it; that is
  the obvious next step with more time.

## 6. Reproduction

```bash
uv venv --python 3.11 && uv pip sync requirements-lock.txt   # or: pip install -r requirements-lock.txt
export MTAH_DATA_DIR=/path/to/mtah2027                       # or unpack the bundle into ./data
python make_submission.py            # -> evaluation/results/Decul.csv (stage v4)
python evaluation/validate_submission.py evaluation/results/Decul.csv
```

The output is deterministic: no randomness, no network, pinned versions. `scripts/final_checks.sh`
rebuilds the submitted file three ways — a second run, a run that parses the raw tracking again
(`--no-cache`), and a run from a fresh clone of the repository with a fresh environment built
from `requirements-lock.txt` — and requires all three to be byte-identical; it passed on
23 October 2026 and is re-run on the final commit before submission. Any stage can be rebuilt
with `--stage v0 … v8`.

Everything CPU-only; no GPU and no network once the environment is installed. The first run
parses the raw tracking once and caches the arrays in `data/cache/` (gitignored, next to the
data); after that a stage takes a few seconds (v7, with its EM iterations, about fifteen).

| to reproduce | command | needs the match data |
|---|---|---|
| the submission | `python make_submission.py` | yes |
| the public-window tables in §1 (every stage, bootstrap) | `bash scripts/run_all.sh` | yes |
| the reproduction check above | `bash scripts/final_checks.sh` | yes |
| v1 from the organisers' published `baseline_raw.csv` | `python validation/v1_from_baseline_raw.py`, then `python evaluation/run_evaluation.py` | no |
| synthetic checks of the decoder, features, EM and restart tags | `python tests/test_pipeline.py` | no |
| the validation tables on Metrica's public matches | below | no |

Validation tables in §1 (public data only):

```bash
for g in 1 2; do
  d=~/mtah-public/metrica_sample/Sample_Game_$g; mkdir -p $d
  for f in RawEventsData RawTrackingData_Home_Team RawTrackingData_Away_Team; do
    curl -sSfL -o $d/Sample_Game_${g}_$f.csv \
      https://raw.githubusercontent.com/metrica-sports/sample-data/master/data/Sample_Game_$g/Sample_Game_${g}_$f.csv
  done
  python validation/metrica_public.py $d
done
```

## 7. Repository layout

The organisers' starter kit is kept unchanged (`games.py`, `starter/`, `evaluation/`, the
challenge documents; its README is `STARTER_KIT.md`). Team Decul's files:

| path | what it is |
|---|---|
| `make_submission.py` | the one command that writes `evaluation/results/Decul.csv`; `--stage v0 … v8` |
| `solution/decode.py` | three-state Viterbi, per half; transition priors |
| `solution/evidence.py` | per-frame log-likelihoods for H, A, D from the features |
| `solution/features.py` | ball gaps, nearest-player distances, ball out / still, player speed |
| `solution/atd.py` | parses the raw tracking into arrays, cached in `data/cache/` |
| `solution/tagging.py` | Smart Tagging: team prior (v4), restart timing (v8) |
| `solution/adapt.py` | EM-learned dead-ball evidence (v7) |
| `validation/` | stage and prior validation on public data (Metrica sample matches, `baseline_raw.csv`) |
| `tests/test_pipeline.py` | synthetic checks, no data needed |
| `scripts/run_all.sh`, `scripts/final_checks.sh` | the runs on the match data behind §1 and §6 |
| `requirements-lock.txt` | the pinned environment |
| `docs/Decul.md`, `docs/ROADMAP.md` | this document; the milestone log of how the work went |
| `.claude/`, `CLAUDE.md` | the AI-tool configuration and the data guard described in §8 |

## 8. Use of AI tools and data handling

Claude Code (Anthropic) helped write the code and this document. The match data was never shown
to it: a project-scope hook (`.claude/hooks/guard_data.py`) and permission rules
(`.claude/settings.json`) refuse any tool call that reads the data folder, reads output computed
from it, or runs code that reads it. Every run on the match data was done locally by the team,
and only the scorer's and validator's summary output was shared. No language model is used when
the submission is produced.
