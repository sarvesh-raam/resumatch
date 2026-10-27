"""Rank every eval resume against every eval JD and compare methods.

    python eval/run_eval.py            # all methods
    python eval/run_eval.py --fast     # skip the MiniLM ones

The data is small and synthetic (see eval/README.md), so treat the numbers as
a regression check and a sanity comparison, not as a real accuracy claim.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))

from resumatch.embedding import get_embedder  # noqa: E402
from resumatch.matcher import JobMatcher  # noqa: E402
from resumatch.skills import default_index  # noqa: E402

DATA = ROOT / "data"


def load():
    jds = {p.stem: p.read_text(encoding="utf-8") for p in sorted((DATA / "jds").glob("*.txt"))}
    resumes = {p.stem: p.read_text(encoding="utf-8") for p in sorted((DATA / "resumes").glob("*.txt"))}
    labels: dict[str, dict[str, int]] = defaultdict(dict)
    with open(DATA / "labels.csv", newline="") as f:
        for row in csv.DictReader(f):
            labels[row["jd"]][row["resume"]] = int(row["label"])
    for jd in jds:
        missing = set(resumes) - set(labels[jd])
        assert not missing, f"no labels for {jd} x {sorted(missing)}"
    return jds, resumes, labels


# --- methods: each returns {jd: {resume: score}} -----------------------------

def resumatch(kind):
    def run(jds, resumes):
        emb, skills = get_embedder(kind), default_index()
        out = {}
        for name, text in jds.items():
            m = JobMatcher(text, emb, skills)
            out[name] = {r: m.score_text(t).score for r, t in resumes.items()}
        return out

    return run


def doc_cosine_minilm(jds, resumes):
    emb = get_embedder("minilm")
    rv = emb.encode(list(resumes.values()))
    jv = emb.encode(list(jds.values()))
    sims = jv @ rv.T
    return {j: dict(zip(resumes, sims[i])) for i, j in enumerate(jds)}


def tfidf(jds, resumes):
    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit([*jds.values(), *resumes.values()])
    rv = vec.transform(resumes.values())
    jv = vec.transform(jds.values())
    sims = (jv @ rv.T).toarray()
    return {j: dict(zip(resumes, sims[i])) for i, j in enumerate(jds)}


def skill_overlap(jds, resumes):
    """What a keyword ATS does: share of JD skills that appear anywhere in the resume."""
    idx = default_index()
    out = {}
    for j, jt in jds.items():
        want = idx.find(jt)
        out[j] = {r: len(want & idx.find(rt)) / max(len(want), 1) for r, rt in resumes.items()}
    return out


METHODS = {
    "resumatch (MiniLM)": resumatch("minilm"),
    "resumatch (hashing)": resumatch("hashing"),
    "whole-doc MiniLM cosine": doc_cosine_minilm,
    "whole-doc TF-IDF cosine": tfidf,
    "skill keyword overlap": skill_overlap,
}
SLOW = {"resumatch (MiniLM)", "whole-doc MiniLM cosine"}


# --- metrics ------------------------------------------------------------------

def ndcg_at(k, ranked, rel):
    dcg = sum((2 ** rel[r] - 1) / math.log2(i + 2) for i, r in enumerate(ranked[:k]))
    ideal = sorted(rel.values(), reverse=True)
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal[:k]))
    return dcg / idcg if idcg else 0.0


def pairwise_acc(scores, rel):
    good = total = 0
    names = list(rel)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if rel[a] == rel[b]:
                continue
            total += 1
            hi, lo = (a, b) if rel[a] > rel[b] else (b, a)
            if scores[hi] > scores[lo]:
                good += 1
            elif scores[hi] == scores[lo]:
                good += 0.5
    return good / total


def evaluate(scores, labels):
    ndcg, pairs, top1, stuffer = [], [], [], []
    for jd, rel in labels.items():
        s = scores[jd]
        # stable tie-break by name so results don't depend on dict order
        ranked = sorted(rel, key=lambda r: (-s[r], r))
        ndcg.append(ndcg_at(3, ranked, rel))
        pairs.append(pairwise_acc(s, rel))
        top1.append(rel[ranked[0]] == 2)
        if "keyword_stuffer" in rel:
            stuffer.append(ranked.index("keyword_stuffer") + 1)
    return {
        "nDCG@3": np.mean(ndcg),
        "pairwise acc": np.mean(pairs),
        "top-1 correct": f"{sum(top1)}/{len(top1)}",
        "stuffer avg rank": np.mean(stuffer),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="skip methods that need MiniLM")
    ap.add_argument("--show", metavar="JD", help="print the full ranking for one JD")
    args = ap.parse_args()

    jds, resumes, labels = load()
    print(f"{len(jds)} JDs x {len(resumes)} resumes, {sum(len(v) for v in labels.values())} labelled pairs\n")

    rows = []
    for name, fn in METHODS.items():
        if args.fast and name in SLOW:
            continue
        scores = fn(jds, resumes)
        rows.append((name, evaluate(scores, labels)))
        if args.show and args.show in scores:
            s = scores[args.show]
            print(f"{name} on {args.show}:")
            for r in sorted(s, key=lambda r: -s[r]):
                print(f"  {float(s[r]):7.3f}  {r}  (label {labels[args.show][r]})")
            print()

    cols = list(rows[0][1])
    print(f"{'method':<26}" + "".join(f"{c:>18}" for c in cols))
    for name, m in rows:
        cells = "".join(f"{v:>18.3f}" if isinstance(v, float) else f"{v:>18}" for v in m.values())
        print(f"{name:<26}" + cells)
    print(f"\n(stuffer avg rank: where the keyword-stuffed resume lands, out of {len(resumes)}; higher is better)")


if __name__ == "__main__":
    main()
