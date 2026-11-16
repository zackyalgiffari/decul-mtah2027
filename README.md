# Team Decul — More than a Hack 2027, Phase 1: Ball Possession

For every frame of FC Barcelona vs Athletic Club, say who has the ball: `H`, `A`, or `D` for a
dead ball. This repository regenerates Team Decul's submission, `Decul.csv`, from the provided
data with one command.

**Technical document: [docs/Decul.md](docs/Decul.md).**

## Method in brief

Per-frame evidence from the automatic tracking — metres from the ball to the nearest home and
away player, whether the ball is seen, over the line or still, how fast the players move — plus a
Smart Tagging prior on which team has the ball, decoded into whole possessions by a three-state
(H, A, D) hidden Markov model solved exactly by Viterbi, one half at a time. Every change of
possession has a price, so short flickers are removed while real, well-evidenced changes are
kept. Built and measured in stages (`--stage v0 … v8`); the submitted stage is **v4**.

| | spellF1 | |
|---|---|---|
| Competition, public five minutes (17 possessions) | **0.4316** vs baseline 0.3256 | intervals overlap — a correctness check, not a ranking |
| Metrica public match 1 (328 possessions) | **0.527** vs 0.399 | non-overlapping bootstrap intervals |
| Metrica public match 2 (330 possessions) | **0.534** vs 0.397 | non-overlapping bootstrap intervals |

## Reproduce the submission

```bash
uv venv --python 3.11 && uv pip sync requirements-lock.txt   # or: pip install -r requirements-lock.txt
export MTAH_DATA_DIR=/path/to/mtah2027      # or unpack the data bundle into ./data
python make_submission.py                   # -> evaluation/results/Decul.csv (stage v4)
python evaluation/validate_submission.py evaluation/results/Decul.csv
sha256sum evaluation/results/Decul.csv
```

A correct run gives a file whose sha256 begins `c499eee84cf9ec00`, and the validator reports
366 possessions of mean 10.5 s.

Deterministic, CPU-only, no network: a second run, a run that re-parses the raw tracking
(`--no-cache`) and a run from a fresh clone with a fresh environment produce the same file
byte for byte (`scripts/final_checks.sh`). The match data is not in this repository and is never
committed (`data/` is gitignored).

## What is where

| path | |
|---|---|
| `make_submission.py` | the one command; `--stage v0 … v8` rebuilds any stage |
| `solution/` | the pipeline: decoder, evidence, features, tracking parser, Smart Tagging |
| `validation/` | stage and prior validation on public data only |
| `tests/test_pipeline.py` | synthetic checks, no data needed — `python tests/test_pipeline.py` |
| `scripts/` | `run_all.sh` (every stage, scored) and `final_checks.sh` (reproduction check); both need the data |
| `docs/Decul.md` | the technical document; `docs/ROADMAP.md` is the milestone log |
| `requirements-lock.txt` | the pinned environment (Python 3.11) |
| `.claude/`, `CLAUDE.md` | AI-tool configuration and the guard that kept the match data away from it |
| everything else | the organisers' starter kit, unchanged — see below |

## The organisers' starter kit

`games.py`, `starter/`, `evaluation/` (including the official scorer), `data/README.md` and the
challenge documents are the organisers' and are kept unchanged:
[CHALLENGE.md](CHALLENGE.md) · [DATA.md](DATA.md) · [EVALUATION.md](EVALUATION.md) ·
[SUBMISSION.md](SUBMISSION.md) · [RULES.md](RULES.md) · [FAQ.md](FAQ.md) ·
[OVERVIEW.md](OVERVIEW.md). Their original README is [STARTER_KIT.md](STARTER_KIT.md).

## Data, AI tools and licence

The match data is licensed to participants for this competition only and is not in this
repository. Claude Code (Anthropic) helped write the code and documents; a project-scope hook
blocked it from reading the data or running anything that reads it, and every run on the data
was done locally by the team (details in [docs/Decul.md](docs/Decul.md), §8).

Code and documentation are released under the MIT Licence ([LICENSE](LICENSE)), which does not
cover the match data.
