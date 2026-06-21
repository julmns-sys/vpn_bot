from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Subscription, User


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

    async def get_by_id(self, subscription_id: int) -> Subscription | None:
        result = await self._session.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .where(Subscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_by_user_id(self, user_id: int) -> Subscription | None:
        result = await self._session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(["pending", "submitted"]),
            )
            .order_by(Subscription.created_at.desc())
        )
        return result.scalars().first()

    async def update_status(
        self,
        subscription: Subscription,
        *,
        status: str,
        starts_at: datetime | None = None,
        expires_at: datetime | None = None,
        external_payment_id: str | None = None,
        meta: str | None = None,
    ) -> Subscription:
        subscription.status = status
        if starts_at is not None:
            subscription.starts_at = starts_at
        if expires_at is not None:
            subscription.expires_at = expires_at
        if external_payment_id is not None:
            subscription.external_payment_id = external_payment_id
        if meta is not None:
            subscription.meta = meta
        await self._session.flush()
        return subscription
