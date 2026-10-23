# experiments/

Team Decul's scratch space: notebooks, parameter sweeps, one-off checks, plots, trials on the
public Metrica sample data. Everything here except this README is **gitignored**, so none of it
enters the repository's history — which becomes public at submission.

Nothing in here is presented to the organisers, and `make_submission.py` must never import from it.

When something here proves useful, promote it: pipeline code to `solution/`, checks without data
to `tests/`, checks on public data to `validation/`, runs on the match data to `scripts/` (see
"Where new code goes" in [CLAUDE.md](../CLAUDE.md)), and write the finding into
[docs/Decul.md](../docs/Decul.md).

Outputs computed from the match data do not belong here either: write them under `data/cache/`,
which is gitignored and guarded, and never paste them into a hosted LLM.
