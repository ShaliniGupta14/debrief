"""Statistics for comparing prompt-version score distributions. Pure
functions -- no DB -- so the math is unit-testable against fixed-seed
synthetic distributions, independent of the query layer that feeds them.
"""

import random
import statistics
from dataclasses import dataclass

DEFAULT_RESAMPLES = 2000
DEFAULT_CONFIDENCE = 0.95


@dataclass
class BootstrapComparison:
    mean_a: float
    mean_b: float
    delta: float  # mean_b - mean_a
    ci_low: float
    ci_high: float
    n_a: int
    n_b: int
    # True only when the *entire* CI of the delta sits below zero -- i.e. we're
    # statistically confident B is worse, not just numerically lower on this sample.
    regressed: bool


def bootstrap_compare(
    scores_a: list[float],
    scores_b: list[float],
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    confidence: float = DEFAULT_CONFIDENCE,
    rng: random.Random | None = None,
) -> BootstrapComparison | None:
    if not scores_a or not scores_b:
        return None

    rng = rng or random.Random()
    mean_a = statistics.fmean(scores_a)
    mean_b = statistics.fmean(scores_b)

    deltas = []
    for _ in range(n_resamples):
        resample_a = rng.choices(scores_a, k=len(scores_a))
        resample_b = rng.choices(scores_b, k=len(scores_b))
        deltas.append(statistics.fmean(resample_b) - statistics.fmean(resample_a))
    deltas.sort()

    alpha = (1 - confidence) / 2
    lo_idx = int(alpha * n_resamples)
    hi_idx = min(int((1 - alpha) * n_resamples), n_resamples - 1)

    ci_low, ci_high = deltas[lo_idx], deltas[hi_idx]
    return BootstrapComparison(
        mean_a=mean_a,
        mean_b=mean_b,
        delta=mean_b - mean_a,
        ci_low=ci_low,
        ci_high=ci_high,
        n_a=len(scores_a),
        n_b=len(scores_b),
        regressed=ci_high < 0,
    )


@dataclass
class PromptRegression:
    prompt: str
    mean_score_a: float
    mean_score_b: float
    delta: float
    n_calls_a: int
    n_calls_b: int


def worst_regressions(
    scores_by_prompt_a: dict[str, list[float]],
    scores_by_prompt_b: dict[str, list[float]],
    *,
    n: int = 10,
) -> list[PromptRegression]:
    shared_prompts = set(scores_by_prompt_a) & set(scores_by_prompt_b)
    rows = []
    for prompt in shared_prompts:
        scores_a = scores_by_prompt_a[prompt]
        scores_b = scores_by_prompt_b[prompt]
        mean_a = statistics.fmean(scores_a)
        mean_b = statistics.fmean(scores_b)
        rows.append(
            PromptRegression(
                prompt=prompt,
                mean_score_a=mean_a,
                mean_score_b=mean_b,
                delta=mean_b - mean_a,
                n_calls_a=len(scores_a),
                n_calls_b=len(scores_b),
            )
        )
    rows.sort(key=lambda r: r.delta)
    return rows[:n]
