from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import User, VpnAccount


class VpnAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: int) -> VpnAccount | None:
        result = await self._session.execute(
            select(VpnAccount).where(VpnAccount.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> VpnAccount | None:
        result = await self._session.execute(
            select(VpnAccount).where(VpnAccount.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_id: int) -> VpnAccount | None:
        result = await self._session.execute(
            select(VpnAccount)
            .join(User)
            .options(selectinload(VpnAccount.user))
            .where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        xui_client_id: str,
        email: str,
        uuid: str,
        inbound_id: int,
        config_url: str,
        expires_at: datetime,
        is_active: bool = True,
    ) -> VpnAccount:
        account = VpnAccount(
            user_id=user_id,
            xui_client_id=xui_client_id,
            email=email,
            uuid=uuid,
            inbound_id=inbound_id,
            config_url=config_url,
            expires_at=expires_at,
            is_active=is_active,
        )
        self._session.add(account)
        await self._session.flush()
        return account

    async def update_config(
        self,
        account: VpnAccount,
        *,
        config_url: str,
        expires_at: datetime,
        is_active: bool,
    ) -> VpnAccount:
        account.config_url = config_url
        account.expires_at = expires_at
        account.is_active = is_active
        await self._session.flush()
        return account

    async def list_accounts_for_alert(
        self,
        *,
        expires_before: datetime,
        alert_field: str,
    ) -> list[VpnAccount]:
        alert_column = getattr(VpnAccount, alert_field)
        result = await self._session.execute(
            select(VpnAccount)
            .join(User)
            .options(selectinload(VpnAccount.user))
            .where(
                VpnAccount.is_active.is_(True),
                VpnAccount.expires_at <= expires_before,
                VpnAccount.expires_at > datetime.now(expires_before.tzinfo),
                alert_column.is_(None),
            )
            .order_by(VpnAccount.expires_at.asc())
        )
        return list(result.scalars().all())

    async def mark_alert_sent(
        self,
        account: VpnAccount,
        *,
        alert_field: str,
        sent_at: datetime,
    ) -> VpnAccount:
        setattr(account, alert_field, sent_at)
        await self._session.flush()
        return account
