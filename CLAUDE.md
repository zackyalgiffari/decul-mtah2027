# Team Decul — More than a Hack 2027, Phase 1

Label every one of the 199,319 frames of one match `H` / `A` / `D` (or `X`), ranked on `spellF1`.
Deadline **2026-11-17**. The plan, milestone by milestone, is [docs/ROADMAP.md](docs/ROADMAP.md).

## Hard rules

- **Never read, open, print or summarise anything under `data/` or `$MTAH_DATA_DIR`**
  (`~/mtah-data`). The terms forbid giving the match data, or any extract of it, to a hosted LLM
  (OVERVIEW.md, "Use of Large Language Models"). `.claude/settings.json` denies `Read` there; do
  not work around it with shell commands. The user runs anything that touches the data and shares
  only the output of `evaluation/run_evaluation.py` and `evaluation/validate_submission.py`.
- **Never commit the data or anything derived from it frame by frame** (feature tables, tracking
  exports, plots of it). The repository becomes public, history included.
- **Deterministic code only.** `make_submission.py` must regenerate `Decul.csv` byte-identically:
  no unseeded randomness, no network, no hosted model at inference time.
- **Do not tune on the public 5 minutes.** 17 possessions cannot rank two versions (EVALUATION.md).
  Use it to check correctness; use `--bootstrap 1000` before claiming one version beats another.

## File map

**1. Presented to the organisers — the submission.** Keep these clean; they are what gets judged.

| path | role |
|---|---|
| `make_submission.py` | the one command that writes `evaluation/results/Decul.csv` |
| `solution/` | the Decul pipeline: everything `make_submission.py` calls |
| `requirements-lock.txt` | pinned versions the submission is produced with |
| `docs/Decul.md` | the technical document (submitted as `Decul.md`) |
| `README.md` (top section only) | install and run instructions |
| `CLAUDE.md`, `docs/ROADMAP.md`, `.claude/settings.json` | how the work was organised |

**2. Organiser infrastructure we depend on — read-only.** Do not modify: it keeps
`git pull upstream main` conflict-free and the scorer identical to the official one.

`games.py` (paths, frame alignment, halves) · `starter/baseline.py` (ATD parser, `smooth`,
`write_submission`) · `starter/load_atd.py` · `starter/load_smart_tagging.py` ·
`starter/load_homography.py` · `evaluation/possession_metrics.py` · `evaluation/run_evaluation.py` ·
`evaluation/validate_submission.py` · `evaluation/gt/` (public 5-minute ground truth) ·
`evaluation/results/baseline_raw.csv` (unsmoothed nearest-player labels, the input to v1) · `LICENSE`

**3. Reference docs — read, never edit.** `CHALLENGE.md`, `EVALUATION.md`, `DATA.md`,
`SUBMISSION.md`, `RULES.md`, `FAQ.md`, `OVERVIEW.md`. If a doc and `possession_metrics.py`
disagree, the code is right.

**4. Not relevant to the submission — ignore unless asked.** `starter/*.ipynb`, `starter/utils.py`,
`starter/make_dummy_submission.py`, `evaluation/results/baseline_smooth*.csv`, the organisers'
`requirements.txt` and `requirements-starter.txt`.

**5. Scratch — `experiments/`.** Gitignored except its README. Never presented, never committed.

## Where new code goes

Ask one question: **does `make_submission.py` run it, or does `docs/Decul.md` cite it?**

- Yes → `solution/`, written to the standard of the starter code (docstrings that say why,
  `# Params` blocks, numpy where it is enough).
- No → `experiments/`. Sweeps, notebooks, one-off checks, plots, Metrica sample-data trials.

Promoting something from `experiments/` to `solution/`: move only the functions the pipeline
needs, drop hard-coded paths in favour of `games.asset_paths()`, make it deterministic, wire it
into `make_submission.py`, and record the finding (with its bootstrap interval) in `docs/Decul.md`.

## Commands

```bash
source ~/venvs/mtah/bin/activate                 # Python 3.11, from requirements-lock.txt
python evaluation/run_evaluation.py              # score every CSV in evaluation/results/
python evaluation/run_evaluation.py --bootstrap 1000
python make_submission.py                        # needs the data -- the user runs this
python evaluation/validate_submission.py evaluation/results/Decul.csv
```

Remotes: `origin` is the Decul repo (private until submission), `upstream` is the organisers'.
