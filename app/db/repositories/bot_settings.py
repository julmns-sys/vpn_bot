from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BotSetting


class BotSettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> BotSetting | None:
        result = await self._session.execute(
            select(BotSetting).where(BotSetting.key == key)
        )
        return result.scalar_one_or_none()

    async def get_many(self, keys: list[str]) -> dict[str, str]:
        result = await self._session.execute(
            select(BotSetting).where(BotSetting.key.in_(keys))
        )
        return {item.key: item.value for item in result.scalars().all()}

    async def set(self, key: str, value: str) -> BotSetting:
        setting = await self.get(key)
        if setting:
            setting.value = value
        else:
            setting = BotSetting(key=key, value=value)
            self._session.add(setting)
        await self._session.flush()
        return setting
