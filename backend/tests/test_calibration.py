from app.evals.calibration import compute_calibration_report


def test_identical_scores_have_zero_stddev():
    report = compute_calibration_report({"call-1": [0.8, 0.8, 0.8]})
    assert report["calls"][0]["stddev"] == 0.0
    assert report["mean_stddev"] == 0.0


def test_varying_scores_report_nonzero_stddev():
    # Population stdev of [0.6, 0.8, 1.0], mean 0.8: sqrt(((.2)^2+0^2+(.2)^2)/3) = 0.1633
    report = compute_calibration_report({"call-1": [0.6, 0.8, 1.0]})
    assert report["calls"][0]["stddev"] == 0.1633


def test_mean_stddev_averages_across_calls():
    report = compute_calibration_report(
        {
            "call-1": [0.8, 0.8, 0.8],  # stddev 0.0
            "call-2": [0.6, 0.8, 1.0],  # stddev 0.1633
        }
    )
    assert report["n_calls"] == 2
    assert report["mean_stddev"] == round((0.0 + 0.1633) / 2, 4)


def test_n_runs_per_call_reflects_actual_run_count():
    report = compute_calibration_report({"call-1": [0.5, 0.5, 0.5]})
    assert report["n_runs_per_call"] == 3


def test_single_run_has_zero_stddev_not_an_error():
    report = compute_calibration_report({"call-1": [0.7]})
    assert report["calls"][0]["stddev"] == 0.0


def test_empty_report_does_not_crash():
    report = compute_calibration_report({})
    assert report["n_calls"] == 0
    assert report["mean_stddev"] == 0.0
    assert report["calls"] == []


def test_report_includes_limitations_note():
    report = compute_calibration_report({"call-1": [0.5, 0.6]})
    assert "small calibration set" in report["note"]
