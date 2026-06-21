from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Subscription


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_placeholder(
        self,
        user_id: int,
        period_days: int,
        amount: int | None = None,
        status: str = "pending",
        starts_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> Subscription:
        subscription = Subscription(
            user_id=user_id,
            period_days=period_days,
            amount=amount,
            status=status,
            starts_at=starts_at,
            expires_at=expires_at,
        )
        self._session.add(subscription)
        await self._session.flush()
        return subscription
