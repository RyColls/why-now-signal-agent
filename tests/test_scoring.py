"""Unit tests for scoring. All accounts and URLs here are invented fixtures."""

from datetime import date

import pandas as pd

from whynow import scoring as s

CONFIG = {
    "weights": {"hiring_maintenance": 30, "expansion": 25, "new_ops_leader": 20,
                "pain_in_job_post": 15, "funding_or_pe": 10},
    "decay": {"half_after_days": 180, "zero_after_days": 365},
    "rules": {"require_verified": True},
}
AS_OF = date(2026, 11, 11)


def sig(kind, published, **over):
    base = {"account_id": "A001", "type": kind, "source_url": "https://example.test/x",
            "published": published, "found": "2026-11-11", "sentence": "s", "verified": True}
    return {**base, **over}


def test_decay_boundaries():
    d = CONFIG["decay"]
    assert s.decay_factor(date(2026, 5, 15), AS_OF, d) == 1.0   # exactly 180 days
    assert s.decay_factor(date(2026, 5, 14), AS_OF, d) == 0.5   # 181 days
    assert s.decay_factor(date(2025, 11, 11), AS_OF, d) == 0.5  # exactly 365 days
    assert s.decay_factor(date(2025, 11, 10), AS_OF, d) == 0.0  # 366 days
    assert s.decay_factor(date(2026, 12, 1), AS_OF, d) == 0.0   # future date


def test_types_add_and_each_counts_once():
    out = s.score_account([
        sig("hiring_maintenance", "2026-10-01"),
        sig("expansion", "2026-03-01"),            # half: 12.5
        sig("expansion", "2026-09-01"),            # full: 25, replaces the older one
        sig("expansion", "2026-09-02", source_url="https://example.test/y"),
    ], AS_OF, CONFIG)
    assert out["score"] == 55
    assert out["status"] == "call"
    assert [x["type"] for x in out["signals"]] == ["hiring_maintenance", "expansion"]


def test_signals_without_evidence_or_verification_do_not_count():
    out = s.score_account([
        sig("hiring_maintenance", "2026-10-01", source_url=""),
        sig("expansion", "2026-10-01", sentence=" "),
        sig("new_ops_leader", "not-a-date"),
        sig("funding_or_pe", "2026-10-01", verified=False),
        sig("made_up_type", "2026-10-01"),
    ], AS_OF, CONFIG)
    assert out["score"] == 0
    assert out["status"] == s.NO_SIGNAL


def test_rank_orders_by_score_then_freshness():
    universe = pd.DataFrame({
        "account_id": ["A001", "A002", "A003"],
        "company_name": ["Alpha", "Bravo", "Charlie"],
        "industry": ["plastics"] * 3,
    })
    ranked = s.rank(universe, [
        sig("expansion", "2026-08-01", account_id="A001"),
        sig("expansion", "2026-10-01", account_id="A003"),
    ], AS_OF, CONFIG)
    assert [r["company_name"] for r in ranked] == ["Charlie", "Alpha", "Bravo"]
    assert ranked[2]["status"] == s.NO_SIGNAL and ranked[2]["rank"] == 3
