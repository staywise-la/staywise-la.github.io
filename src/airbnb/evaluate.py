"""Shared evaluation code. Every module reports numbers through these
functions, so results are comparable and reproducible.

Retrieval format
----------------
run   : {query_id: [doc_id, doc_id, ...]}   ranked list, best first
qrels : {query_id: {doc_id: relevance}}     relevance 1 (or graded 1, 2, 3)
"""
from __future__ import annotations

from typing import Callable, Hashable, Mapping, Sequence

import numpy as np

Run = Mapping[Hashable, Sequence[Hashable]]
Qrels = Mapping[Hashable, Mapping[Hashable, float]]


# ---------------------------------------------------------------------------
# Per-query retrieval metrics
# ---------------------------------------------------------------------------
def precision_at_k(ranked: Sequence, rel: Mapping, k: int) -> float:
    top = ranked[:k]
    return sum(1 for d in top if rel.get(d, 0) > 0) / k if k else 0.0


def recall_at_k(ranked: Sequence, rel: Mapping, k: int) -> float:
    n_rel = sum(1 for v in rel.values() if v > 0)
    if n_rel == 0:
        return 0.0
    return sum(1 for d in ranked[:k] if rel.get(d, 0) > 0) / n_rel


def f1_at_k(ranked: Sequence, rel: Mapping, k: int) -> float:
    p, r = precision_at_k(ranked, rel, k), recall_at_k(ranked, rel, k)
    return 2 * p * r / (p + r) if (p + r) else 0.0


def ndcg_at_k(ranked: Sequence, rel: Mapping, k: int) -> float:
    gains = [rel.get(d, 0) for d in ranked[:k]]
    dcg = sum((2 ** g - 1) / np.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted((v for v in rel.values() if v > 0), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / np.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def reciprocal_rank(ranked: Sequence, rel: Mapping, k: int | None = None) -> float:
    for i, d in enumerate(ranked[:k] if k else ranked):
        if rel.get(d, 0) > 0:
            return 1.0 / (i + 1)
    return 0.0


METRICS: dict[str, Callable] = {
    "recall@10": lambda r, q: recall_at_k(r, q, 10),
    "ndcg@10": lambda r, q: ndcg_at_k(r, q, 10),
    "mrr": lambda r, q: reciprocal_rank(r, q),
    "precision@10": lambda r, q: precision_at_k(r, q, 10),
    "f1@10": lambda r, q: f1_at_k(r, q, 10),
}


# ---------------------------------------------------------------------------
# Whole-run evaluation with bootstrap confidence intervals
# ---------------------------------------------------------------------------
def per_query_scores(run: Run, qrels: Qrels, metrics: dict[str, Callable] | None = None) -> dict[str, np.ndarray]:
    metrics = metrics or METRICS
    qids = [q for q in qrels if q in run]
    return {name: np.array([fn(list(run[q]), qrels[q]) for q in qids]) for name, fn in metrics.items()}


def bootstrap_ci(values: np.ndarray, n_boot: int = 2000, alpha: float = 0.05, seed: int = 6740) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n_boot, len(values)), replace=True).mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def evaluate_run(run: Run, qrels: Qrels, metrics: dict[str, Callable] | None = None) -> dict[str, dict[str, float]]:
    """Mean and 95% bootstrap CI for each metric."""
    out = {}
    for name, vals in per_query_scores(run, qrels, metrics).items():
        lo, hi = bootstrap_ci(vals) if len(vals) else (np.nan, np.nan)
        out[name] = {"mean": float(vals.mean()) if len(vals) else np.nan, "ci_low": lo, "ci_high": hi, "n": int(len(vals))}
    return out


def paired_bootstrap_pvalue(a: np.ndarray, b: np.ndarray, n_boot: int = 5000, seed: int = 6740) -> float:
    """Two-sided p-value that systems A and B differ (same queries, same order)."""
    rng = np.random.default_rng(seed)
    diff = a - b
    observed = diff.mean()
    centered = diff - observed
    boots = rng.choice(centered, size=(n_boot, len(diff)), replace=True).mean(axis=1)
    return float((np.abs(boots) >= abs(observed)).mean())


# ---------------------------------------------------------------------------
# Regression metrics (price module)
# ---------------------------------------------------------------------------
def mae(y_true, y_pred) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def mape(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)


def interval_coverage(y_true, lower, upper) -> float:
    """Share of true values inside [lower, upper]. An 80% interval should give ~0.80."""
    y_true = np.asarray(y_true)
    return float(np.mean((y_true >= np.asarray(lower)) & (y_true <= np.asarray(upper))))
