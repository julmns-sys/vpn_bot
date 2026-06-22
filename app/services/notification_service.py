from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.repositories.vpn_accounts import VpnAccountRepository

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        bot: Bot,
        poll_interval_seconds: int = 3600,
    ) -> None:
        self._session_factory = session_factory
        self._bot = bot
        self._poll_interval_seconds = poll_interval_seconds

    async def run_forever(self) -> None:
        while True:
            try:
                await self.process_expiration_alerts()
            except Exception:
                logger.exception("Failed while processing expiration alerts")
            await asyncio.sleep(self._poll_interval_seconds)

    async def process_expiration_alerts(self) -> None:
        await self._process_alert_window(days=3, alert_field="alert_3d_sent_at")
        await self._process_alert_window(days=1, alert_field="alert_1d_sent_at")

    async def _process_alert_window(self, *, days: int, alert_field: str) -> None:
        async with self._session_factory() as session:
            repo = VpnAccountRepository(session)
            expires_before = datetime.now(UTC) + timedelta(days=days)
            accounts = await repo.list_accounts_for_alert(
                expires_before=expires_before,
                alert_field=alert_field,
            )
            for account in accounts:
                if not account.user:
                    continue
                await self._bot.send_message(
                    account.user.telegram_id,
                    self._build_alert_text(days=days, expires_at=account.expires_at),
                )
                await repo.mark_alert_sent(
                    account,
                    alert_field=alert_field,
                    sent_at=datetime.now(UTC),
                )
            if accounts:
                await session.commit()
                logger.info("Sent %s expiration alerts for %s day window", len(accounts), days)

    @staticmethod
    def _build_alert_text(*, days: int, expires_at: datetime) -> str:
        expires = expires_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
        if days == 1:
            return (
                "Подписка истечет завтра.\n"
                f"Действует до: {expires}\n"
                "Чтобы не потерять доступ, продли подписку заранее."
            )
        return (
            "Подписка истечет через 3 дня.\n"
            f"Действует до: {expires}\n"
            "Чтобы не потерять доступ, продли подписку заранее."
        )
