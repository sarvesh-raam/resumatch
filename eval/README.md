# Eval

A small ranking check: 5 job descriptions × 9 resumes = 45 labelled pairs.

```
python eval/run_eval.py              # all methods (needs MiniLM, ~90 MB download on first run)
python eval/run_eval.py --fast       # hashing embedder + baselines only, what CI runs
python eval/run_eval.py --show backend_engineer   # print each method's ranking for one JD
```

## Data

Everything in `data/` is made up. The resumes are written to look like common
Indian fresher/junior profiles (Python backend, Java backend, ML, data analyst,
frontend, MERN, GenAI, a mechanical engineer) plus one deliberately bad case:
`keyword_stuffer.txt`, which lists ~30 skills and has two tutorial-level
projects. A tool that just counts keywords should rank it high; a useful one
shouldn't.

`labels.csv` grades each pair 0 (not a fit), 1 (partial) or 2 (strong fit).
Labels were assigned by reading each pair, before any tuning. They haven't
been checked by a recruiter, so they measure "does this agree with a
reasonable reading", not hiring outcomes.

## Metrics

- **nDCG@3** – are the best-fit resumes near the top of each JD's ranking
- **pairwise acc** – of all resume pairs with different labels, how often the better one scores higher
- **top-1 correct** – is the #1 resume the label-2 one
- **stuffer avg rank** – where `keyword_stuffer` lands, out of 9 (higher is better)

## Caveats

- 45 pairs is tiny. One flipped pair moves pairwise accuracy by ~2 points.
- The MiniLM similarity thresholds in `embedding.py` and the "listed only"
  credit in `matcher.py` were set by looking at this same data, so the
  ResuMatch numbers are not held-out. The baselines have no tuning at all.
- All resumes are plain text, so PDF extraction isn't tested here (it's
  covered in `backend/tests/test_parsing.py`).
