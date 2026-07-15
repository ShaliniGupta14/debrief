"""LLM-as-judge: rubric-driven, temperature 0, structured JSON via tool-use.

Tool-use forces Claude to respond in a fixed schema rather than prompting for
JSON in prose and parsing it -- far fewer malformed responses in practice.
The retry loop is defense-in-depth on top of that (per spec: "retry-on-
malformed-JSON"), not the primary reliability mechanism.

Any failure -- malformed tool output OR an API-level error (rate limit,
timeout) -- ends in None after retries are exhausted, deliberately broad:
one judge hiccup should skip that eval_result, not crash the whole worker
job and lose the rule-eval results already computed for the same call.
"""

from dataclasses import dataclass
from typing import Any, Protocol

MAX_ATTEMPTS = 3

SCORE_TOOL: dict[str, Any] = {
    "name": "submit_score",
    "description": "Submit the evaluation score and rationale for the model response.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Quality score: 0 fails the rubric entirely, 1 fully satisfies it.",
            },
            "rationale": {
                "type": "string",
                "description": "One sentence explaining the score.",
            },
        },
        "required": ["score", "rationale"],
    },
}


@dataclass
class JudgeResult:
    score: float
    passed: bool
    rationale: str


class AnthropicMessagesClient(Protocol):
    """The one method judge.py needs -- lets tests pass a fake client
    without depending on the real anthropic SDK's client shape."""

    async def create(self, **kwargs: Any) -> Any: ...


def _build_prompt(rubric: str, prompt: str, response: str) -> str:
    return (
        f"Rubric:\n{rubric}\n\n"
        f"Prompt given to the model:\n{prompt}\n\n"
        f"Model's response:\n{response}\n\n"
        "Score how well the response satisfies the rubric."
    )


async def run_judge_eval(
    messages_client: AnthropicMessagesClient,
    model: str,
    config: dict[str, Any],
    prompt: str,
    response: str,
) -> JudgeResult | None:
    rubric = config["rubric"]
    pass_threshold = config.get("pass_threshold", 0.7)
    user_prompt = _build_prompt(rubric, prompt, response)

    for _attempt in range(MAX_ATTEMPTS):
        try:
            message = await messages_client.create(
                model=model,
                max_tokens=300,
                temperature=0,
                tools=[SCORE_TOOL],
                tool_choice={"type": "tool", "name": "submit_score"},
                messages=[{"role": "user", "content": user_prompt}],
            )
            tool_use = next(block for block in message.content if block.type == "tool_use")
            score = max(0.0, min(1.0, float(tool_use.input["score"])))
            rationale = str(tool_use.input["rationale"])
            return JudgeResult(score=score, passed=score >= pass_threshold, rationale=rationale)
        except Exception:  # noqa: BLE001 -- see module docstring: any failure retries, then gives up
            continue
    return None
