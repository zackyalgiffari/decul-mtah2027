# Team Decul — Technical document

More than a Hack 2027, Phase 1: frame-level ball possession.
Submission file: `Decul.csv`. Repository: https://github.com/zackyalgiffari/decul-mtah2027

---

## 1. Approach

_What we built, and why that rather than something else._

## 2. Assets used and dropped

| asset | used? | how / why not |
|---|---|---|
| Tactical ATD (tracking) | | |
| Smart Tagging | | |
| Homography | | |
| Tactical video | | |
| Broadcast video, ATD, homography | | |

## 3. Possession rules implemented

_Where we drew the line on loose balls, challenges, deflections and restarts._

## 4. Limitations

_Where it fails, and what we would fix with more time._

## 5. Reproduction

```bash
uv venv --python 3.11 && uv pip sync requirements-lock.txt   # or: pip install -r requirements-lock.txt
export MTAH_DATA_DIR=/path/to/mtah2027
python make_submission.py            # -> evaluation/results/Decul.csv
python evaluation/validate_submission.py evaluation/results/Decul.csv
```
