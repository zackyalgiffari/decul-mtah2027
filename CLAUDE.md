# Team Decul — More than a Hack 2027, Phase 1

Label every one of the 199,319 frames of one match `H` / `A` / `D` (or `X`), ranked on `spellF1`.
Deadline **2026-11-17**. The plan, milestone by milestone, is [docs/ROADMAP.md](docs/ROADMAP.md).

## Hard rules

- **Never read, open, print or summarise anything under `data/` or `$MTAH_DATA_DIR`**
  (`~/mtah-data`), nor output computed from it. The terms accepted at enrolment forbid giving the
  match data, any extract of it, or any confidential information from the organisers to a hosted
  LLM without their written authorisation (also OVERVIEW.md, "Use of Large Language Models").
  The user runs anything that touches the data and shares only the output of
  `evaluation/run_evaluation.py` and `evaluation/validate_submission.py`.
- **When a call is blocked by the data guard, stop and ask the user.** Never rephrase, split or
  wrap a command to get past it, and never edit `.claude/` unless the user asks for that change.
- **Never commit the data or anything derived from it frame by frame** (feature tables, tracking
  exports, plots of it). The repository becomes public, history included.
- **Write outputs computed from the data under `data/`** (e.g. `data/cache/`), never elsewhere,
  so they stay gitignored and guarded. All of it is deleted when the competition ends.
- **Deterministic code only.** `make_submission.py` must regenerate `Decul.csv` byte-identically:
  no unseeded randomness, no network, no hosted model at inference time.
- **Do not tune on the public 5 minutes.** 17 possessions cannot rank two versions (EVALUATION.md).
  Use it to check correctness; use `--bootstrap 1000` before claiming one version beats another.

## Enforcement

The rules above are enforced in this project's `.claude/settings.json` only (project scope; no
user-level setting is involved):

| layer | blocks |
|---|---|
| `permissions.deny` | Read and Edit of `data/**` and `~/mtah-data/**` |
| `permissions.ask` | any edit under `.claude/` needs the user's approval |
| `.claude/hooks/guard_data.py` (PreToolUse, fail-closed) | file tools on the data or on outputs computed from it (`evaluation/results/[Dd]ecul*.csv`, data-like files in `experiments/`); shell commands that name the data, list it, run code that reads it (`make_submission.py`, `starter/baseline.py`, the loaders, notebooks), or search recursively into it |

The hook reads command text only: a new script that opens the data without naming it is not
caught. That gap is closed only by the Bash sandbox (`sandbox.enabled`, needs `socat`), which is
not enabled yet. Hook tests: `python3 .claude/hooks/test_guard_data.py`.

"Respect .gitignore" in `/config` is not a protection: it only filters the `@` file picker.

## File map

**1. Presented to the organisers — the submission.** Keep these clean; they are what gets judged.

| path | role |
|---|---|
| `make_submission.py` | the one command that writes `evaluation/results/Decul.csv` |
| `solution/` | the Decul pipeline: everything `make_submission.py` calls |
| `requirements-lock.txt` | pinned versions the submission is produced with |
| `docs/Decul.md` | the technical document (submitted as `Decul.md`) |
| `README.md` (top section only) | install and run instructions |
| `CLAUDE.md`, `docs/ROADMAP.md`, `.claude/` | how the work was organised, and the data guard |

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
