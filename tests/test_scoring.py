"""Unit tests for pure scoring math (no database)."""

from datetime import datetime, timedelta, timezone

from app.services.scoring import (
    bayesian_average,
    compute_recursive_score,
    compute_user_reputation,
    rapid_posting_penalty,
    scale_score,
    trust_score,
    wilson_lower_bound,
)


def test_bayesian_average_no_votes_returns_prior():
    """With no votes, Bayesian average equals the prior mean."""
    assert bayesian_average(0, 0, prior_mean=0.0, prior_weight=10.0) == 0.0
    assert bayesian_average(0, 0, prior_mean=0.5, prior_weight=10.0) == 0.5


def test_bayesian_average_pulls_toward_prior_with_few_votes():
    """A single upvote is pulled toward the prior."""
    score = bayesian_average(1, 0, prior_mean=0.0, prior_weight=10.0)
    # (1*1 + 10*0) / 11 ≈ 0.0909
    assert abs(score - (1.0 / 11.0)) < 1e-9


def test_bayesian_average_all_downvotes():
    """All downvotes produce a negative mean, softened by the prior."""
    score = bayesian_average(0, 5, prior_mean=0.0, prior_weight=10.0)
    assert score == (-5.0) / 15.0


def test_wilson_lower_bound_no_votes():
    """Wilson lower bound is 0 with no votes."""
    assert wilson_lower_bound(0, 0) == 0.0


def test_wilson_lower_bound_increases_with_confidence():
    """More unanimous ups raise the Wilson lower bound."""
    low = wilson_lower_bound(1, 0)
    high = wilson_lower_bound(50, 0)
    assert 0.0 < low < high < 1.0


def test_wilson_lower_bound_mixed_votes():
    """Mixed votes yield a lower bound below the raw proportion."""
    bound = wilson_lower_bound(8, 2)
    assert 0.0 < bound < 0.8


def test_trust_score_zero_reputation():
    """New users have zero trust weight."""
    assert trust_score(0, trust_constant=100) == 0.0


def test_trust_score_approaches_one():
    """High reputation approaches but does not reach 1."""
    assert abs(trust_score(100, trust_constant=100) - 0.5) < 1e-9
    assert 0.9 < trust_score(1000, trust_constant=100) < 1.0


def test_trust_score_clamps_negative_reputation():
    """Negative reputation is treated as zero trust."""
    assert trust_score(-50, trust_constant=100) == 0.0


def test_rapid_posting_penalty_no_penalty_when_spaced():
    """Posts spaced at or above the threshold get full credit."""
    assert rapid_posting_penalty(1.0, min_hours=1.0) == 1.0
    assert rapid_posting_penalty(2.0, min_hours=1.0) == 1.0


def test_rapid_posting_penalty_decays_when_close():
    """Closer posts receive a stricter exponential penalty."""
    mild = rapid_posting_penalty(0.5, min_hours=1.0)
    harsh = rapid_posting_penalty(0.1, min_hours=1.0)
    assert 0.0 < harsh < mild < 1.0


def test_scale_score_rounds():
    """Float scores scale to integers."""
    assert scale_score(0.5, scale=100) == 50
    assert scale_score(-0.25, scale=100) == -25


def test_compute_recursive_score_leaf():
    """Leaf recursive score is just the scaled Bayesian value."""
    assert compute_recursive_score(0.5, [], scale=100) == 50


def test_compute_recursive_score_with_trusted_children():
    """Children contribute trust-weighted recursive scores."""
    # own 0.5 → 50; child 100 * 0.5 trust → 50; total 100
    assert compute_recursive_score(0.5, [(100, 0.5)], scale=100) == 100


def test_compute_user_reputation_no_votes():
    """No votes yields zero reputation."""
    now = datetime.now(timezone.utc)
    assert compute_user_reputation(0, 0, [now]) == 0


def test_compute_user_reputation_applies_rapid_penalty():
    """Rapid consecutive posts reduce reputation versus spaced posts."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    spaced = [t0, t0 + timedelta(hours=2)]
    rapid = [t0, t0 + timedelta(minutes=10)]
    spaced_rep = compute_user_reputation(20, 0, spaced, reputation_scale=1000)
    rapid_rep = compute_user_reputation(20, 0, rapid, reputation_scale=1000)
    assert spaced_rep > rapid_rep >= 0
