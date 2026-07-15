import random

from app.evals.compare_stats import bootstrap_compare, worst_regressions

SEED = 42


def test_identical_distributions_show_no_regression():
    scores = [0.8, 0.85, 0.75, 0.9, 0.8, 0.82, 0.78, 0.88] * 5
    result = bootstrap_compare(scores, scores, rng=random.Random(SEED))
    assert result is not None
    assert result.delta == 0.0
    assert result.ci_low <= 0 <= result.ci_high
    assert result.regressed is False


def test_clear_large_regression_is_detected():
    rng_data = random.Random(SEED)
    scores_a = [min(1.0, max(0.0, rng_data.gauss(0.9, 0.03))) for _ in range(40)]
    scores_b = [min(1.0, max(0.0, rng_data.gauss(0.3, 0.03))) for _ in range(40)]

    result = bootstrap_compare(scores_a, scores_b, rng=random.Random(SEED))
    assert result is not None
    assert result.delta < -0.5
    assert result.ci_high < 0  # entire CI below zero -> confidently worse
    assert result.regressed is True


def test_clear_improvement_is_not_flagged_as_regression():
    rng_data = random.Random(SEED)
    scores_a = [min(1.0, max(0.0, rng_data.gauss(0.4, 0.05))) for _ in range(40)]
    scores_b = [min(1.0, max(0.0, rng_data.gauss(0.9, 0.05))) for _ in range(40)]

    result = bootstrap_compare(scores_a, scores_b, rng=random.Random(SEED))
    assert result is not None
    assert result.delta > 0.3
    assert result.regressed is False


def test_small_noisy_difference_is_not_confidently_regressed():
    # A tiny true difference (0.75 vs 0.72) on a small, noisy sample: the CI
    # should straddle zero -- the statistical test should NOT claim confidence
    # it doesn't have. This is the case a naive "mean_b < mean_a" check would
    # wrongly flag; the whole point of the CI is to not be fooled by it.
    rng_data = random.Random(SEED)
    scores_a = [min(1.0, max(0.0, rng_data.gauss(0.75, 0.2))) for _ in range(12)]
    scores_b = [min(1.0, max(0.0, rng_data.gauss(0.72, 0.2))) for _ in range(12)]

    result = bootstrap_compare(scores_a, scores_b, rng=random.Random(SEED))
    assert result is not None
    assert result.ci_low <= 0 <= result.ci_high
    assert result.regressed is False


def test_bootstrap_compare_returns_none_for_empty_input():
    assert bootstrap_compare([], [0.5, 0.6]) is None
    assert bootstrap_compare([0.5, 0.6], []) is None


def test_bootstrap_compare_is_deterministic_given_a_seeded_rng():
    scores_a = [0.5, 0.6, 0.7, 0.4]
    scores_b = [0.3, 0.5, 0.4, 0.6]
    result1 = bootstrap_compare(scores_a, scores_b, rng=random.Random(SEED))
    result2 = bootstrap_compare(scores_a, scores_b, rng=random.Random(SEED))
    assert result1 == result2


def test_worst_regressions_sorts_by_most_negative_delta_first():
    scores_a = {"prompt-1": [0.9], "prompt-2": [0.8], "prompt-3": [0.5]}
    scores_b = {"prompt-1": [0.85], "prompt-2": [0.3], "prompt-3": [0.9]}
    # prompt-1 delta -0.05, prompt-2 delta -0.5, prompt-3 delta +0.4
    results = worst_regressions(scores_a, scores_b, n=10)
    assert [r.prompt for r in results] == ["prompt-2", "prompt-1", "prompt-3"]


def test_worst_regressions_respects_n():
    scores_a = {f"p{i}": [0.9] for i in range(5)}
    scores_b = {f"p{i}": [0.9 - i * 0.1] for i in range(5)}
    results = worst_regressions(scores_a, scores_b, n=2)
    assert len(results) == 2


def test_worst_regressions_excludes_prompts_not_shared_by_both_versions():
    scores_a = {"only-in-a": [0.9]}
    scores_b = {"only-in-b": [0.1]}
    assert worst_regressions(scores_a, scores_b) == []


def test_worst_regressions_averages_multiple_calls_per_prompt():
    scores_a = {"prompt-1": [0.8, 1.0]}  # mean 0.9
    scores_b = {"prompt-1": [0.4, 0.6]}  # mean 0.5
    result = worst_regressions(scores_a, scores_b)[0]
    assert result.mean_score_a == 0.9
    assert result.mean_score_b == 0.5
    assert result.delta == -0.4
    assert result.n_calls_a == 2
    assert result.n_calls_b == 2
