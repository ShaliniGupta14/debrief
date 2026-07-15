"""Judge calibration: run the judge N times on the same small set of calls
and report how much it disagrees with itself. Pure computation here, no
API/DB -- the endpoint that actually calls the judge lives in routers/evals.py.
"""

import statistics
from typing import Any

LIMITATIONS_NOTE = (
    "Judge consistency is estimated from a small calibration set -- variance on "
    "this sample may not generalize to the full traffic distribution. A high "
    "mean_stddev means the judge disagrees with itself on identical input; treat "
    "individual eval scores as noisier the higher this is. Re-run calibration "
    "periodically, especially after changing the rubric or judge model."
)


def compute_calibration_report(per_call_scores: dict[str, list[float]]) -> dict[str, Any]:
    calls = []
    stddevs = []
    runs_per_call = 0

    for call_id, scores in per_call_scores.items():
        runs_per_call = max(runs_per_call, len(scores))
        # Population stdev, not sample (n-1): the question is "how much did
        # the judge disagree with itself on these specific runs", not an
        # inference about a broader population from a sample.
        stddev = round(statistics.pstdev(scores), 4) if len(scores) > 1 else 0.0
        calls.append({"call_id": call_id, "scores": scores, "stddev": stddev})
        stddevs.append(stddev)

    return {
        "calls": calls,
        "n_calls": len(per_call_scores),
        "n_runs_per_call": runs_per_call,
        "mean_stddev": round(statistics.fmean(stddevs), 4) if stddevs else 0.0,
        "note": LIMITATIONS_NOTE,
    }
