"""Eval gate: the synthetic benchmark must keep scoring at least this well (offline, no Claude)."""

from evals.run import run


def test_eval_gate():
    r = run(with_claude=False)
    assert r["page_types"]["ari"] >= 0.8, r["page_types"]
    assert r["page_types"]["ari"] >= r["page_types"]["ari_url_only"]  # page structure must help, never hurt
    assert r["page_types"]["count_error"] <= 0.05
    assert r["checks"]["precision"] >= 0.95 and r["checks"]["recall"] >= 0.9, {k: v for k, v in r["checks"].items() if k != "per_check"}
