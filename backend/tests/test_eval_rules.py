from app.evals.rules import run_rule_eval


def test_regex_matches():
    score, passed = run_rule_eval("regex", {"pattern": r"\d{3}-\d{4}"}, "prompt", "call 555-1234")
    assert passed is True
    assert score == 1.0


def test_regex_does_not_match():
    score, passed = run_rule_eval("regex", {"pattern": r"\d{3}-\d{4}"}, "prompt", "no phone here")
    assert passed is False
    assert score == 0.0


def test_regex_case_insensitive_flag():
    assert run_rule_eval("regex", {"pattern": "hello"}, "prompt", "HELLO world")[1] is False
    assert (
        run_rule_eval(
            "regex", {"pattern": "hello", "case_insensitive": True}, "prompt", "HELLO world"
        )[1]
        is True
    )


def test_regex_can_target_prompt_field():
    score, passed = run_rule_eval(
        "regex", {"pattern": "urgent", "field": "prompt"}, "this is urgent", "a calm reply"
    )
    assert passed is True


def test_json_schema_valid():
    schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
    score, passed = run_rule_eval("json_schema", {"schema": schema}, "prompt", '{"name": "Ada"}')
    assert passed is True


def test_json_schema_invalid_json():
    schema = {"type": "object"}
    score, passed = run_rule_eval("json_schema", {"schema": schema}, "prompt", "not json at all")
    assert passed is False


def test_json_schema_valid_json_wrong_shape():
    schema = {"type": "object", "required": ["name"]}
    score, passed = run_rule_eval("json_schema", {"schema": schema}, "prompt", '{"other": 1}')
    assert passed is False


def test_length_within_bounds():
    score, passed = run_rule_eval("length", {"min": 5, "max": 20}, "prompt", "hello world")
    assert passed is True


def test_length_below_min():
    score, passed = run_rule_eval("length", {"min": 50}, "prompt", "too short")
    assert passed is False


def test_length_above_max():
    score, passed = run_rule_eval("length", {"max": 5}, "prompt", "this is way too long")
    assert passed is False


def test_length_word_unit():
    score, passed = run_rule_eval(
        "length", {"min": 3, "max": 5, "unit": "words"}, "prompt", "one two three"
    )
    assert passed is True


def test_contains_found():
    score, passed = run_rule_eval("contains", {"text": "refund"}, "prompt", "here is your refund")
    assert passed is True


def test_contains_not_found():
    score, passed = run_rule_eval("contains", {"text": "refund"}, "prompt", "here is your receipt")
    assert passed is False


def test_contains_not_contains_mode_passes_when_absent():
    score, passed = run_rule_eval(
        "contains", {"text": "sorry", "mode": "not_contains"}, "prompt", "great news!"
    )
    assert passed is True


def test_contains_not_contains_mode_fails_when_present():
    score, passed = run_rule_eval(
        "contains", {"text": "sorry", "mode": "not_contains"}, "prompt", "sorry about that"
    )
    assert passed is False


def test_contains_case_sensitivity():
    # Default (case_sensitive=False) ignores case, so this matches.
    assert run_rule_eval("contains", {"text": "REFUND"}, "prompt", "your refund")[1] is True
    # With case_sensitive=True, a case mismatch no longer matches.
    assert (
        run_rule_eval(
            "contains", {"text": "REFUND", "case_sensitive": True}, "prompt", "your refund"
        )[1]
        is False
    )
