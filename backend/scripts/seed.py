"""Seed ~2000 realistic fake calls across 3 apps and 2 prompt versions.

Assumes the schema is already migrated (`alembic upgrade head`) — this script
owns data, not schema. Safe to re-run: refuses to add more data if any already
exists, unless --reset is passed (which truncates everything first).

Usage:
    uv run python scripts/seed.py [--reset] [--calls 2000]
"""

import argparse
import asyncio
import json
import random
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.models import EvalDefinition, EvalResult, LLMCall, ModelPrice, Project  # noqa: E402
from app.security import generate_api_key, hash_api_key  # noqa: E402

random.seed(42)  # reproducible across runs

MODELS = [
    # (model, input_price_per_mtok, output_price_per_mtok, sampling weight)
    ("claude-sonnet-5", Decimal("3"), Decimal("15"), 0.4),
    ("claude-haiku-4-5", Decimal("1"), Decimal("5"), 0.3),
    ("gpt-4o", Decimal("2.5"), Decimal("10"), 0.2),
    ("gpt-4o-mini", Decimal("0.15"), Decimal("0.6"), 0.1),
]

PROMPT_VERSIONS = ["v1", "v2"]

ERROR_MESSAGES = ["rate_limit_exceeded", "context_length_exceeded", "upstream_timeout"]

APPS = [
    {
        "name": "support-bot",
        "pairs": [
            (
                "What's your return policy?",
                "You can return any item within 30 days of purchase for a full refund.",
            ),
            (
                "How do I reset my password?",
                "Click 'Forgot password' on the login page and follow the emailed link.",
            ),
            (
                "My order hasn't arrived yet, what should I do?",
                "I'm sorry to hear that. Let me look up your order and provide an update.",
            ),
            (
                "Can I get a refund for my last purchase?",
                "Refunds are processed within 5-7 business days after we receive the item.",
            ),
            (
                "How do I cancel my subscription?",
                "You can cancel anytime from Account Settings > Subscription > Cancel.",
            ),
        ],
    },
    {
        "name": "content-generator",
        "pairs": [
            (
                "Write a blog post intro about sustainable fashion.",
                "Sustainable fashion isn't just a trend, it's a movement reshaping how we "
                "think about clothing.",
            ),
            (
                "Draft a tweet announcing our new product launch.",
                "Big news! Our newest product just dropped. Check it out and be the first "
                "to try it.",
            ),
            (
                "Write a product description for a wireless charger.",
                "Charge effortlessly with our sleek wireless charger, compatible with all "
                "Qi-enabled devices.",
            ),
            (
                "Generate 3 headline options for a fitness app landing page.",
                "1. Get Fit, Stay Fit  2. Your Fitness Journey Starts Here  3. Move More, "
                "Worry Less",
            ),
            (
                "Write a short email newsletter about our summer sale.",
                "Summer's here and so are our biggest savings of the year. Shop the sale "
                "before it ends!",
            ),
        ],
    },
    {
        "name": "code-reviewer",
        "pairs": [
            (
                "Review this function for potential bugs: def add(a, b): return a - b",
                "Bug found: the function is named `add` but performs subtraction "
                "(`a - b` instead of `a + b`).",
            ),
            (
                "Write a function that reverses a linked list in Python.",
                "def reverse_list(head):\n    prev = None\n    while head:\n        "
                "head.next, prev, head = prev, head, head.next\n    return prev",
            ),
            (
                'Is this SQL query vulnerable to injection? query = f"SELECT * FROM '
                'users WHERE id={id}"',
                "Yes, this is vulnerable to SQL injection since `id` is interpolated "
                "directly. Use parameterized queries instead.",
            ),
            (
                "Suggest improvements for this recursive fibonacci implementation.",
                "Consider memoization or an iterative approach to avoid exponential "
                "time complexity.",
            ),
            (
                "Explain why this async function might deadlock.",
                "It likely deadlocks because it awaits a lock it already holds without "
                "releasing it first.",
            ),
        ],
    },
]


def _fake_call(app: dict, project_id, now: datetime) -> LLMCall:
    model, input_price, output_price, _ = random.choices(MODELS, weights=[m[3] for m in MODELS])[0]
    prompt_version = random.choice(PROMPT_VERSIONS)
    prompt, response = random.choice(app["pairs"])

    input_tokens = max(20, int(random.gauss(len(prompt.split()) * 1.3 + 150, 40)))
    output_tokens = max(10, int(random.gauss(len(response.split()) * 1.3 + 20, 20)))
    # v2 tends to run a bit longer -- gives Day 2's compare view something real to show.
    if prompt_version == "v2":
        output_tokens = int(output_tokens * 1.15)

    latency_ms = max(50, int(random.lognormvariate(6.0, 0.5)))

    is_error = random.random() < 0.03
    status = "error" if is_error else "ok"
    error_message = random.choice(ERROR_MESSAGES) if is_error else None
    cost_usd = (
        None
        if is_error
        else (Decimal(input_tokens) * input_price + Decimal(output_tokens) * output_price)
        / Decimal(1_000_000)
    )

    created_at = now - timedelta(days=random.uniform(0, 14), seconds=random.uniform(0, 86400))

    return LLMCall(
        project_id=project_id,
        model=model,
        prompt=prompt,
        response="" if is_error else response,
        prompt_version=prompt_version,
        input_tokens=input_tokens,
        output_tokens=0 if is_error else output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        status=status,
        error_message=error_message,
        metadata_={
            "env": random.choices(["prod", "staging"], weights=[0.85, 0.15])[0],
            "region": random.choice(["us-east-1", "us-west-2", "eu-west-1"]),
        },
        created_at=created_at,
    )


async def reset(db) -> None:
    print(
        "Resetting: truncating eval_results, eval_definitions, llm_calls, model_prices, projects..."
    )
    for model in (EvalResult, EvalDefinition, LLMCall, ModelPrice, Project):
        await db.execute(model.__table__.delete())
    await db.commit()


async def main(total_calls: int, do_reset: bool) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        if do_reset:
            await reset(db)
        else:
            existing = await db.execute(select(func.count()).select_from(LLMCall))
            if existing.scalar_one() > 0:
                print("llm_calls already has data. Re-run with --reset to wipe and reseed.")
                await engine.dispose()
                return

        print("Seeding model prices...")
        for model, input_price, output_price, _ in MODELS:
            db.add(
                ModelPrice(
                    model=model,
                    input_price_per_mtok=input_price,
                    output_price_per_mtok=output_price,
                    effective_date=datetime(2026, 1, 1).date(),
                )
            )
        await db.commit()

        print("Seeding projects...")
        seeded_keys: dict[str, str] = {}
        projects = []
        for app in APPS:
            raw_key = generate_api_key()
            project = Project(
                name=app["name"], api_key_hash=hash_api_key(raw_key), api_key_prefix=raw_key[:12]
            )
            db.add(project)
            await db.flush()
            projects.append((project, app))
            seeded_keys[app["name"]] = raw_key
        await db.commit()

        print(f"Seeding ~{total_calls} calls...")
        now = datetime.now(UTC)
        calls_per_app = total_calls // len(projects)
        for project, app in projects:
            for _ in range(calls_per_app):
                db.add(_fake_call(app, project.id, now))
            await db.commit()
            print(f"  {app['name']}: {calls_per_app} calls")

        keys_path = Path(__file__).resolve().parent / ".seeded_keys.json"
        keys_path.write_text(json.dumps(seeded_keys, indent=2))
        print(f"\nDone. API keys written to {keys_path} (gitignored, hashed at rest server-side):")
        for name, key in seeded_keys.items():
            print(f"  {name}: {key}")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="truncate existing data first")
    parser.add_argument("--calls", type=int, default=2000, help="total calls to generate")
    args = parser.parse_args()
    asyncio.run(main(args.calls, args.reset))
