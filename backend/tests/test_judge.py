from dataclasses import dataclass, field
from typing import Any

import pytest

from app.evals.judge import run_judge_eval

CONFIG = {"rubric": "Response must be polite and answer the question."}


@dataclass
class FakeToolUseBlock:
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class FakeMessage:
    content: list[Any]


@dataclass
class FakeMessagesClient:
    """Returns a scripted sequence of responses, one per call to .create().
    A response can be a message, or an Exception instance to raise."""

    responses: list[Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response


def _scored_message(score: float, rationale: str = "Fine.") -> FakeMessage:
    return FakeMessage(content=[FakeToolUseBlock(input={"score": score, "rationale": rationale})])


async def test_judge_returns_score_and_rationale_on_success():
    client = FakeMessagesClient(responses=[_scored_message(0.9, "Polite and correct.")])
    result = await run_judge_eval(client, "claude-sonnet-5", CONFIG, "prompt", "response")
    assert result is not None
    assert result.score == 0.9
    assert result.rationale == "Polite and correct."
    assert len(client.calls) == 1


async def test_judge_uses_temperature_zero_and_tool_choice():
    client = FakeMessagesClient(responses=[_scored_message(0.5)])
    await run_judge_eval(client, "claude-sonnet-5", CONFIG, "prompt", "response")
    call_kwargs = client.calls[0]
    assert call_kwargs["temperature"] == 0
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "submit_score"}


async def test_judge_passed_uses_default_threshold():
    client = FakeMessagesClient(responses=[_scored_message(0.75)])
    result = await run_judge_eval(client, "claude-sonnet-5", CONFIG, "prompt", "response")
    assert result is not None
    assert result.passed is True  # 0.75 >= default 0.7

    client2 = FakeMessagesClient(responses=[_scored_message(0.5)])
    result2 = await run_judge_eval(client2, "claude-sonnet-5", CONFIG, "prompt", "response")
    assert result2 is not None
    assert result2.passed is False


async def test_judge_respects_custom_pass_threshold():
    config = {**CONFIG, "pass_threshold": 0.9}
    client = FakeMessagesClient(responses=[_scored_message(0.8)])
    result = await run_judge_eval(client, "claude-sonnet-5", config, "prompt", "response")
    assert result is not None
    assert result.passed is False


async def test_judge_clamps_out_of_range_score():
    client = FakeMessagesClient(responses=[_scored_message(1.5)])
    result = await run_judge_eval(client, "claude-sonnet-5", CONFIG, "prompt", "response")
    assert result is not None
    assert result.score == 1.0


async def test_judge_retries_on_malformed_response_then_succeeds():
    malformed = FakeMessage(content=[FakeToolUseBlock(input={"rationale": "no score field"})])
    client = FakeMessagesClient(responses=[malformed, _scored_message(0.8, "Recovered.")])
    result = await run_judge_eval(client, "claude-sonnet-5", CONFIG, "prompt", "response")
    assert result is not None
    assert result.score == 0.8
    assert len(client.calls) == 2


async def test_judge_retries_on_api_error_then_succeeds():
    client = FakeMessagesClient(responses=[RuntimeError("rate limited"), _scored_message(0.6)])
    result = await run_judge_eval(client, "claude-sonnet-5", CONFIG, "prompt", "response")
    assert result is not None
    assert result.score == 0.6


async def test_judge_gives_up_after_max_attempts():
    client = FakeMessagesClient(responses=[RuntimeError("down")] * 5)
    result = await run_judge_eval(client, "claude-sonnet-5", CONFIG, "prompt", "response")
    assert result is None
    assert len(client.calls) == 3  # MAX_ATTEMPTS, not more


@pytest.mark.parametrize("bad_score", ["not-a-number", None])
async def test_judge_retries_then_gives_up_on_non_numeric_score(bad_score):
    bad = FakeMessage(content=[FakeToolUseBlock(input={"score": bad_score, "rationale": "x"})])
    client = FakeMessagesClient(responses=[bad, bad, bad])
    result = await run_judge_eval(client, "claude-sonnet-5", CONFIG, "prompt", "response")
    assert result is None
