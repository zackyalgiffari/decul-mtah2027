# Team Decul — Technical document

More than a Hack 2027, Phase 1: frame-level ball possession.
Submission file: `Decul.csv`. Repository: https://github.com/zackyalgiffari/decul-mtah2027

---

## 1. Approach

_Draft — results to be filled in from the stage comparison._

The ranking metric scores whole possessions, so the main failure to avoid is flicker: a
per-frame rule that switches team for a few frames invents possessions and scores near zero even
when most frames are right. We therefore separate **evidence** (what each frame says) from
**decoding** (which sequence of possessions best explains all frames), and decode with a
three-state hidden Markov model (H, A, D), solved exactly by Viterbi, one half at a time.

- **Decoding** (`solution/decode.py`). Every change of state has a price set by football priors —
  a possession lasts around 12 s, a stoppage around 15 s, and three in four possessions end in an
  open-play turnover rather than a stoppage. A change happens only when the evidence outweighs
  the price, so strong sustained evidence switches within a second while missing evidence leaves
  the state alone. Unlike a fixed smoothing window, this keeps short real possessions and removes
  short false ones.
- **Evidence** (`solution/evidence.py`, `solution/features.py`). Per frame, P(ball alive) and
  P(home | alive), combined into log-likelihoods and tempered, because consecutive frames are not
  independent witnesses.

The pipeline is built in stages so each layer's contribution is measured on its own
(`make_submission.py --stage`):

| stage | adds |
|---|---|
| v0 | published baseline: nearest player, majority vote ±2 s |
| v1 | Viterbi instead of the vote, same signal |
| v2 | team evidence from metres to the nearest home and away player; ball gaps ≤ 0.5 s interpolated |
| v3 | dead-ball evidence: ball over the line, players walking, ball standing still |
| v4 | Smart Tagging as a prior on which team has the ball |
| v5 | no team evidence while the ball travels faster than 7 m/s (a pass or shot passing a player) |
| v6 | a ball standing still on a line or the centre spot counts towards a stoppage (restart waiting) |

Parameters are football priors written in each module's `# Params` block, not values searched on
the public five minutes, which hold too few possessions to choose between versions.

**Results on the public five minutes** (17 possessions; 5–95% block-bootstrap interval, 1000
draws). This window checks correctness; it cannot rank stages whose intervals overlap.

| stage | macroF1 | spellF1 [5–95%] | possessions (truth 17) | alive/dead F1 |
|---|---|---|---|---|
| v0 = published baseline | 0.6207 | 0.3256 [0.214, 0.447] | 26 | 0.899 |
| v1 | 0.6362 | 0.3304 [0.217, 0.444] | 29 | 0.893 |
| v2 | 0.6518 | 0.3333 [0.200, 0.467] | 25 | 0.893 |
| v3 | 0.6816 | 0.3707 [0.234, 0.498] | 24 | 0.913 |
| v4 | 0.6821 | 0.4316 [0.284, 0.590] | 21 | 0.924 |

Over the full match the number of predicted possessions falls from 669 (v0) to 366 (v4), with
mean duration rising from 7.6 s to 10.5 s; dead ball covers 39% of graded frames, in line with
the 55–60 minutes of effective playing time typical of a top-flight match. v0 reproduces the
published baseline exactly, and v1 computed from the ATD equals v1 computed from the published
`baseline_raw.csv`, which confirms the parsing and frame alignment.

## 2. Assets used and dropped

| asset | used? | how / why not |
|---|---|---|
| Tactical ATD (tracking) | yes | ball and player positions and speeds, every frame |
| Smart Tagging | yes (v4) | team of possession-implying phases as a prior; `N/A` tags ignored |
| Homography | no | only needed to go between pitch and video, and we do not use the video |
| Tactical video | no | the tracking already encodes it; ball detection from video left as future work |
| Broadcast video, ATD, homography | no | not synchronised to the tactical timeline; adds alignment risk |

## 3. Possession rules implemented

_Draft._

- **Loose and contested balls** stay with the team that last had possession: when the ball is
  more than 3 m from every player, or not tracked, the frame carries no team evidence and the
  decoder keeps the current state.
- **Control** means being nearest the ball within 3 m, weighted by how much closer the home
  player is than the away player. A brief touch or a deflection gives evidence for well under a
  second and does not outweigh the price of a change of possession.
- **Dead ball** is evidenced by the ball beyond the lines, players walking (mean speed well
  under the ~2 m/s of live play) and a ball standing still; a ball merely lost by the tracker for
  a moment is not a stoppage.
- **Restarts** are not forced: after a stoppage the possessing team is whichever the evidence
  favours once play resumes.

## 4. Limitations

_Draft._

- **Stoppages with a visible ball.** The largest remaining error is dead ball labelled as play
  (v4, public window: 996 of 1,469 dead-ball frames predicted H or A; every frame predicted D was
  correct). A ball placed for a throw-in or corner looks like a ball at a player's feet. Stage
  v6 adds a restart cue for exactly this case.
- **Validation.** The only labelled data is five minutes with 17 possessions, so stage choices
  rest on consistent movement across all diagnostics plus football priors, not on one score.
- **Hand-set priors.** Durations, distances and odds are set from football knowledge, not
  learned; a model trained on labelled matches could set them better.
- **No video.** The ball is missing on 41% of graded frames and we do not re-detect it; that is
  the obvious next step with more time.

## 5. Reproduction

```bash
uv venv --python 3.11 && uv pip sync requirements-lock.txt   # or: pip install -r requirements-lock.txt
export MTAH_DATA_DIR=/path/to/mtah2027
python make_submission.py            # -> evaluation/results/Decul.csv
python evaluation/validate_submission.py evaluation/results/Decul.csv
```
