"""Rule-based evals: pure functions, no DB/IO, so they're cheap to run for
every call and trivial to unit test. All return (score, passed) where score
is always 1.0/0.0 -- rule evals are inherently binary, unlike judge scores.
"""

import json
import re
from typing import Any

import jsonschema


def _get_field(config: dict[str, Any], prompt: str, response: str) -> str:
    return prompt if config.get("field") == "prompt" else response


def eval_regex(config: dict[str, Any], prompt: str, response: str) -> tuple[float, bool]:
    text = _get_field(config, prompt, response)
    flags = re.IGNORECASE if config.get("case_insensitive") else 0
    passed = re.search(config["pattern"], text, flags) is not None
    return (1.0 if passed else 0.0), passed


def eval_json_schema(config: dict[str, Any], prompt: str, response: str) -> tuple[float, bool]:
    text = _get_field(config, prompt, response)
    try:
        parsed = json.loads(text)
        jsonschema.validate(instance=parsed, schema=config["schema"])
        passed = True
    except (json.JSONDecodeError, jsonschema.ValidationError):
        passed = False
    return (1.0 if passed else 0.0), passed


def eval_length(config: dict[str, Any], prompt: str, response: str) -> tuple[float, bool]:
    text = _get_field(config, prompt, response)
    length = len(text.split()) if config.get("unit") == "words" else len(text)
    min_len = config.get("min")
    max_len = config.get("max")
    passed = (min_len is None or length >= min_len) and (max_len is None or length <= max_len)
    return (1.0 if passed else 0.0), passed


def eval_contains(config: dict[str, Any], prompt: str, response: str) -> tuple[float, bool]:
    text = _get_field(config, prompt, response)
    needle = config["text"]
    if not config.get("case_sensitive", False):
        text, needle = text.lower(), needle.lower()
    found = needle in text
    passed = found if config.get("mode", "contains") == "contains" else not found
    return (1.0 if passed else 0.0), passed


RULE_EVALUATORS = {
    "regex": eval_regex,
    "json_schema": eval_json_schema,
    "length": eval_length,
    "contains": eval_contains,
}


def run_rule_eval(
    eval_type: str, config: dict[str, Any], prompt: str, response: str
) -> tuple[float, bool]:
    return RULE_EVALUATORS[eval_type](config, prompt, response)
