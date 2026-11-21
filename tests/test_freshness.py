from datetime import datetime, timedelta

from retail_pipeline.contracts import CONTRACTS
from retail_pipeline.freshness import evaluate_freshness

NOW = datetime(2026, 5, 1, 12, 0)


def test_all_fresh():
    last = {t: NOW - timedelta(hours=3) for t in CONTRACTS}
    assert evaluate_freshness(last, NOW, 26) == []


def test_stale_and_missing_tables_are_reported():
    last = {t: NOW - timedelta(hours=3) for t in CONTRACTS}
    last["orders"] = NOW - timedelta(hours=40)
    del last["payments"]
    problems = {p["table"]: p["problem"] for p in evaluate_freshness(last, NOW, 26)}
    assert set(problems) == {"orders", "payments"}
    assert "never" in problems["payments"] and "40.0h" in problems["orders"]
