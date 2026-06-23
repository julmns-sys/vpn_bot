from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        normalized = username.strip().lstrip("@")
        result = await self._session.execute(
            select(User).where(User.username == normalized)
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_ids(self, telegram_ids: list[int]) -> list[User]:
        if not telegram_ids:
            return []
        result = await self._session.execute(
            select(User).where(User.telegram_id.in_(telegram_ids))
        )
        return list(result.scalars().all())

    async def create(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def count(self) -> int:
        result = await self._session.execute(select(func.count(User.id)))
        return int(result.scalar_one())
