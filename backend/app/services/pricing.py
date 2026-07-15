from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelPrice


async def compute_cost(
    db: AsyncSession, model: str, input_tokens: int, output_tokens: int, as_of: datetime
) -> Decimal | None:
    """Price at the rate in effect when the call happened, not today's rate."""
    result = await db.execute(
        select(ModelPrice)
        .where(ModelPrice.model == model, ModelPrice.effective_date <= as_of.date())
        .order_by(ModelPrice.effective_date.desc())
        .limit(1)
    )
    price = result.scalar_one_or_none()
    if price is None:
        return None
    return (
        Decimal(input_tokens) * price.input_price_per_mtok
        + Decimal(output_tokens) * price.output_price_per_mtok
    ) / Decimal(1_000_000)
