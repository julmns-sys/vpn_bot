from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.db.models import User, VpnAccount
from app.db.repositories.subscriptions import SubscriptionRepository
from app.db.repositories.users import UserRepository
from app.db.repositories.vpn_accounts import VpnAccountRepository
from app.services.config_builder import build_vless_config
from app.services.xui_client import XUIClient, XUIClientNotFoundError, XUIError

logger = logging.getLogger(__name__)


class VPNService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        xui_client: XUIClient,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._xui_client = xui_client
        self._settings = settings

    async def get_or_create_account(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> tuple[User, VpnAccount, bool]:
        async with self._session_factory() as session:
            users = UserRepository(session)
            accounts = VpnAccountRepository(session)
            subscriptions = SubscriptionRepository(session)

            user = await users.get_by_telegram_id(telegram_id)
            if user:
                account = await accounts.get_by_user_id(user.id)
                if not account:
                    try:
                        account = await self._import_existing_xui_account(
                            telegram_id=telegram_id,
                            username=username or user.username,
                            user=user,
                            accounts=accounts,
                            subscriptions=subscriptions,
                        )
                        await session.commit()
                        return user, account, False
                    except XUIClientNotFoundError:
                        account = await self._create_new_account(
                            user=user,
                            telegram_id=telegram_id,
                            accounts=accounts,
                            subscriptions=subscriptions,
                        )
                        await session.commit()
                        return user, account, True
                return user, account, False

            try:
                xui_account = await self._find_existing_xui_account(
                    telegram_id=telegram_id,
                    username=username,
                    accounts=accounts,
                )
            except XUIClientNotFoundError:
                xui_account = None
            except XUIError:
                await session.rollback()
                raise

            user = await users.create(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
            )

            if xui_account:
                account = await self._persist_imported_account(
                    user=user,
                    xui_account=xui_account,
                    accounts=accounts,
                    subscriptions=subscriptions,
                    status="active",
                )
                await session.commit()
                logger.info("Imported existing XUI account for telegram_id=%s", telegram_id)
                return user, account, False

            account = await self._create_new_account(
                user=user,
                telegram_id=telegram_id,
                accounts=accounts,
                subscriptions=subscriptions,
            )
            await session.commit()
            logger.info("Created VPN account for telegram_id=%s", telegram_id)
            return user, account, True

    async def get_account_by_telegram_id(self, telegram_id: int) -> tuple[User, VpnAccount] | None:
        async with self._session_factory() as session:
            users = UserRepository(session)
            accounts = VpnAccountRepository(session)
            user = await users.get_by_telegram_id(telegram_id)
            if not user:
                return None
            account = await accounts.get_by_user_id(user.id)
            if not account:
                return None
            return user, account

    async def extend_subscription(self, telegram_id: int, days: int) -> VpnAccount:
        async with self._session_factory() as session:
            users = UserRepository(session)
            accounts = VpnAccountRepository(session)
            user = await users.get_by_telegram_id(telegram_id)
            if not user:
                raise ValueError("User not found")
            account = await accounts.get_by_user_id(user.id)
            if not account:
                raise ValueError("VPN account not found")

            base_date = max(account.expires_at, datetime.now(UTC))
            new_expires_at = base_date + timedelta(days=days)
            xui_account = await self._xui_client.update_client_expiry(
                inbound_id=account.inbound_id,
                client_id=account.xui_client_id,
                email=account.email,
                expires_at=new_expires_at,
                enabled=True,
            )
            await accounts.update_config(
                account,
                config_url=account.config_url,
                expires_at=xui_account.expires_at,
                is_active=True,
            )
            await session.commit()
            return account

    async def disable_account(self, telegram_id: int) -> VpnAccount:
        async with self._session_factory() as session:
            users = UserRepository(session)
            accounts = VpnAccountRepository(session)
            user = await users.get_by_telegram_id(telegram_id)
            if not user:
                raise ValueError("User not found")
            account = await accounts.get_by_user_id(user.id)
            if not account:
                raise ValueError("VPN account not found")
            xui_account = await self._xui_client.update_client_expiry(
                inbound_id=account.inbound_id,
                client_id=account.xui_client_id,
                email=account.email,
                expires_at=account.expires_at,
                enabled=False,
            )
            await accounts.update_config(
                account,
                config_url=account.config_url,
                expires_at=xui_account.expires_at,
                is_active=False,
            )
            await session.commit()
            return account

    async def recreate_config(self, telegram_id: int) -> VpnAccount:
        async with self._session_factory() as session:
            users = UserRepository(session)
            accounts = VpnAccountRepository(session)
            user = await users.get_by_telegram_id(telegram_id)
            if not user:
                raise ValueError("User not found")
            account = await accounts.get_by_user_id(user.id)
            if not account:
                raise ValueError("VPN account not found")
            config_url = build_vless_config(
                settings=self._settings,
                uuid=account.uuid,
                email=account.email,
            )
            await accounts.update_config(
                account,
                config_url=config_url,
                expires_at=account.expires_at,
                is_active=account.is_active,
            )
            await session.commit()
            return account

    async def count_users(self) -> int:
        async with self._session_factory() as session:
            users = UserRepository(session)
            return await users.count()

    async def import_account(self, telegram_id: int) -> tuple[User, VpnAccount]:
        email = self._build_client_email(telegram_id)
        return await self.import_account_by_email(telegram_id=telegram_id, email=email)

    async def import_account_by_email(
        self,
        *,
        telegram_id: int,
        email: str,
    ) -> tuple[User, VpnAccount]:
        async with self._session_factory() as session:
            users = UserRepository(session)
            accounts = VpnAccountRepository(session)
            subscriptions = SubscriptionRepository(session)

            user = await users.get_by_telegram_id(telegram_id)
            if not user:
                user = await users.create(
                    telegram_id=telegram_id,
                    username=None,
                    first_name=None,
                )

            existing_account = await accounts.get_by_user_id(user.id)
            if existing_account:
                return user, existing_account

            existing_link = await accounts.get_by_email(email)
            if existing_link:
                raise RuntimeError(
                    f"VPN account with email {email} already linked to another user in the database"
                )

            xui_account = await self._xui_client.get_client(
                email=email,
                inbound_id=self._settings.xui_inbound_id,
            )
            account = await self._persist_imported_account(
                user=user,
                xui_account=xui_account,
                accounts=accounts,
                subscriptions=subscriptions,
                status="active",
            )
            await session.commit()
            return user, account

    def build_payment_text(self) -> str:
        lines = [self._settings.price_text]
        if self._settings.payment_phone:
            lines.append(f"СБП: {self._settings.payment_phone}")
        if self._settings.plan_prices:
            lines.append("")
            lines.append("Тарифы:")
            for months, amount in sorted(self._settings.plan_prices.items()):
                lines.append(f"{months} мес. - {amount} руб.")
        return "\n".join(lines)

    @staticmethod
    def _build_client_email(telegram_id: int) -> str:
        return f"tg-{telegram_id}"

    async def _import_existing_xui_account(
        self,
        *,
        telegram_id: int,
        username: str | None,
        user: User,
        accounts: VpnAccountRepository,
        subscriptions: SubscriptionRepository,
    ) -> VpnAccount:
        xui_account = await self._find_existing_xui_account(
            telegram_id=telegram_id,
            username=username,
            accounts=accounts,
        )
        return await self._persist_imported_account(
            user=user,
            xui_account=xui_account,
            accounts=accounts,
            subscriptions=subscriptions,
            status="active",
        )

    async def _create_new_account(
        self,
        *,
        user: User,
        telegram_id: int,
        accounts: VpnAccountRepository,
        subscriptions: SubscriptionRepository,
    ) -> VpnAccount:
        expires_at = datetime.now(UTC) + timedelta(
            days=self._settings.default_subscription_days
        )
        email = self._build_client_email(telegram_id)
        try:
            xui_account = await self._xui_client.create_client(
                email=email,
                expires_at=expires_at,
            )
        except XUIError:
            raise

        config_url = build_vless_config(
            settings=self._settings,
            uuid=xui_account.uuid,
            email=xui_account.email,
        )
        account = await accounts.create(
            user_id=user.id,
            xui_client_id=xui_account.client_id,
            email=xui_account.email,
            uuid=xui_account.uuid,
            inbound_id=xui_account.inbound_id,
            config_url=config_url,
            expires_at=xui_account.expires_at,
            is_active=xui_account.enabled,
        )
        await subscriptions.create_placeholder(
            user_id=user.id,
            period_days=self._settings.default_subscription_days,
            status="active",
            starts_at=datetime.now(UTC),
            expires_at=xui_account.expires_at,
            amount=self._settings.plan_prices.get(
                self._settings.default_subscription_days,
                None,
            ),
        )
        return account

    async def _persist_imported_account(
        self,
        *,
        user: User,
        xui_account,
        accounts: VpnAccountRepository,
        subscriptions: SubscriptionRepository,
        status: str,
    ) -> VpnAccount:
        activated_account = await self._activate_imported_xui_account(xui_account)
        config_url = build_vless_config(
            settings=self._settings,
            uuid=activated_account.uuid,
            email=activated_account.email,
        )
        account = await accounts.create(
            user_id=user.id,
            xui_client_id=activated_account.client_id,
            email=activated_account.email,
            uuid=activated_account.uuid,
            inbound_id=activated_account.inbound_id,
            config_url=config_url,
            expires_at=activated_account.expires_at,
            is_active=activated_account.enabled,
        )
        await subscriptions.create_placeholder(
            user_id=user.id,
            period_days=self._settings.default_subscription_days,
            status=status,
            starts_at=datetime.now(UTC),
            expires_at=activated_account.expires_at,
            amount=None,
        )
        return account

    async def _find_existing_xui_account(
        self,
        *,
        telegram_id: int,
        username: str | None,
        accounts: VpnAccountRepository,
    ):
        for candidate_email in self._candidate_client_emails(telegram_id=telegram_id, username=username):
            existing_account = await accounts.get_by_email(candidate_email)
            if existing_account:
                raise RuntimeError(
                    f"VPN account with email {candidate_email} already linked to another user in the database"
                )
            try:
                return await self._xui_client.get_client(
                    email=candidate_email,
                    inbound_id=self._settings.xui_inbound_id,
                )
            except XUIClientNotFoundError:
                continue
        raise XUIClientNotFoundError("Existing XUI client not found")

    async def _activate_imported_xui_account(self, xui_account):
        new_expires_at = datetime.now(UTC) + timedelta(
            days=self._settings.default_subscription_days
        )
        return await self._xui_client.update_client_expiry(
            inbound_id=xui_account.inbound_id,
            client_id=xui_account.client_id,
            email=xui_account.email,
            expires_at=new_expires_at,
            enabled=True,
        )

    def _candidate_client_emails(
        self,
        *,
        telegram_id: int,
        username: str | None,
    ) -> list[str]:
        candidates: list[str] = []
        if username:
            normalized_username = username.strip().lstrip("@")
            if normalized_username:
                candidates.append(normalized_username)
        candidates.append(self._build_client_email(telegram_id))
        return list(dict.fromkeys(candidates))
