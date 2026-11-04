import numpy as np

from airbnb import evaluate as ev


def test_retrieval_metrics():
    ranked = ["a", "b", "c", "d"]
    rel = {"b": 1, "d": 1, "z": 1}
    assert ev.precision_at_k(ranked, rel, 2) == 0.5
    assert abs(ev.recall_at_k(ranked, rel, 4) - 2 / 3) < 1e-9
    assert ev.reciprocal_rank(ranked, rel) == 0.5
    assert 0 < ev.ndcg_at_k(ranked, rel, 4) < 1


def test_perfect_ranking_scores_one():
    rel = {"a": 1, "b": 1}
    assert ev.ndcg_at_k(["a", "b", "c"], rel, 10) == 1.0
    assert ev.recall_at_k(["a", "b"], rel, 10) == 1.0


def test_evaluate_run_and_ci():
    run = {"q1": ["a", "b"], "q2": ["c", "d"]}
    qrels = {"q1": {"a": 1}, "q2": {"d": 1}}
    res = ev.evaluate_run(run, qrels)
    assert res["mrr"]["mean"] == 0.75
    assert res["mrr"]["ci_low"] <= 0.75 <= res["mrr"]["ci_high"]


def test_regression_metrics():
    y = np.array([100, 200])
    assert ev.mae(y, [110, 190]) == 10
    assert ev.interval_coverage(y, [90, 210], [120, 220]) == 0.5
