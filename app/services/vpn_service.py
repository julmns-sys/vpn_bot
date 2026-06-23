from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
import json

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.db.models import User, VpnAccount
from app.db.models import Subscription
from app.db.repositories.bot_settings import BotSettingRepository
from app.db.repositories.subscriptions import SubscriptionRepository
from app.db.repositories.users import UserRepository
from app.db.repositories.vpn_accounts import VpnAccountRepository
from app.services.config_builder import build_vless_config
from app.services.xui_client import XUIClient, XUIClientNotFoundError, XUIError

logger = logging.getLogger(__name__)

BOT_SETTING_PLAN_PRICES = "plan_prices"
BOT_SETTING_PRICE_TEXT = "price_text"
BOT_SETTING_PAYMENT_DETAILS = "payment_details"
BOT_SETTING_ADMIN_IDS = "admin_ids"


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
    ) -> tuple[User, VpnAccount | None, bool]:
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
                        await session.commit()
                        return user, None, False
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

            await session.commit()
            logger.info("Registered user without VPN account telegram_id=%s", telegram_id)
            return user, None, True

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

    async def build_payment_text(self) -> str:
        payment_text, payment_details, _ = await self.get_billing_settings()
        lines = [payment_text]
        if payment_details:
            lines.extend(["", payment_details])
        return "\n".join(lines)

    async def build_plan_payment_text(self, months: int) -> str:
        payment_text, payment_details, plan_prices = await self.get_billing_settings()
        amount = plan_prices.get(months)
        if amount is None:
            raise ValueError("Unknown payment plan")
        lines = [
            f"Выбран тариф: {months} мес. - {amount} руб.",
            "",
            payment_text or "Отправьте деньги по этим реквизитам:",
        ]
        if payment_details:
            lines.append(payment_details)
        else:
            lines.append("Реквизиты не настроены.")
        lines.append("")
        lines.append("После оплаты нажмите кнопку «Я оплатил».")
        return "\n".join(lines)

    async def get_billing_settings(self) -> tuple[str, str | None, dict[int, int]]:
        async with self._session_factory() as session:
            repo = BotSettingRepository(session)
            raw_settings = await repo.get_many(
                [
                    BOT_SETTING_PRICE_TEXT,
                    BOT_SETTING_PAYMENT_DETAILS,
                    BOT_SETTING_PLAN_PRICES,
                ]
            )
        return (
            raw_settings.get(BOT_SETTING_PRICE_TEXT) or self._settings.price_text,
            raw_settings.get(BOT_SETTING_PAYMENT_DETAILS) or self._default_payment_details(),
            self._deserialize_plan_prices(raw_settings.get(BOT_SETTING_PLAN_PRICES)),
        )

    async def get_admin_ids(self) -> set[int]:
        async with self._session_factory() as session:
            repo = BotSettingRepository(session)
            raw_settings = await repo.get_many([BOT_SETTING_ADMIN_IDS])
        return set(self._settings.admin_ids) | self._deserialize_admin_ids(
            raw_settings.get(BOT_SETTING_ADMIN_IDS)
        )

    async def add_admin_id(self, telegram_id: int) -> set[int]:
        async with self._session_factory() as session:
            repo = BotSettingRepository(session)
            raw_settings = await repo.get_many([BOT_SETTING_ADMIN_IDS])
            admin_ids = self._deserialize_admin_ids(raw_settings.get(BOT_SETTING_ADMIN_IDS))
            admin_ids.add(telegram_id)
            await repo.set(
                BOT_SETTING_ADMIN_IDS,
                json.dumps(sorted(admin_ids), ensure_ascii=True),
            )
            await session.commit()
        return await self.get_admin_ids()

    async def remove_admin_id(self, telegram_id: int) -> set[int]:
        async with self._session_factory() as session:
            repo = BotSettingRepository(session)
            raw_settings = await repo.get_many([BOT_SETTING_ADMIN_IDS])
            admin_ids = self._deserialize_admin_ids(raw_settings.get(BOT_SETTING_ADMIN_IDS))
            admin_ids.discard(telegram_id)
            await repo.set(
                BOT_SETTING_ADMIN_IDS,
                json.dumps(sorted(admin_ids), ensure_ascii=True),
            )
            await session.commit()
        return await self.get_admin_ids()

    async def get_user_by_username(self, username: str) -> User | None:
        async with self._session_factory() as session:
            users = UserRepository(session)
            return await users.get_by_username(username)

    async def get_admin_labels(self) -> list[tuple[int, str | None]]:
        admin_ids = sorted(await self.get_admin_ids())
        async with self._session_factory() as session:
            users = UserRepository(session)
            known_users = await users.get_by_telegram_ids(admin_ids)
        username_by_id = {user.telegram_id: user.username for user in known_users if user.username}
        return [(admin_id, username_by_id.get(admin_id)) for admin_id in admin_ids]

    async def update_plan_price(self, *, months: int, amount: int) -> dict[int, int]:
        async with self._session_factory() as session:
            repo = BotSettingRepository(session)
            raw_settings = await repo.get_many([BOT_SETTING_PLAN_PRICES])
            plan_prices = self._deserialize_plan_prices(raw_settings.get(BOT_SETTING_PLAN_PRICES))
            plan_prices[months] = amount
            await repo.set(BOT_SETTING_PLAN_PRICES, json.dumps(plan_prices, ensure_ascii=True, sort_keys=True))
            await session.commit()
            return dict(sorted(plan_prices.items()))

    async def update_payment_details(self, details: str) -> str:
        async with self._session_factory() as session:
            repo = BotSettingRepository(session)
            await repo.set(BOT_SETTING_PAYMENT_DETAILS, details.strip())
            await session.commit()
            return details.strip()

    async def update_price_text(self, text: str) -> str:
        async with self._session_factory() as session:
            repo = BotSettingRepository(session)
            await repo.set(BOT_SETTING_PRICE_TEXT, text.strip())
            await session.commit()
            return text.strip()

    async def create_payment_request(self, telegram_id: int, months: int) -> Subscription:
        async with self._session_factory() as session:
            users = UserRepository(session)
            subscriptions = SubscriptionRepository(session)

            user = await users.get_by_telegram_id(telegram_id)
            if not user:
                raise ValueError("User not found")

            settings_repo = BotSettingRepository(session)
            raw_settings = await settings_repo.get_many([BOT_SETTING_PLAN_PRICES])
            amount = self._deserialize_plan_prices(
                raw_settings.get(BOT_SETTING_PLAN_PRICES)
            ).get(months)
            if amount is None:
                raise ValueError("Unknown payment plan")

            pending = await subscriptions.get_pending_by_user_id(user.id)
            if pending:
                pending.period_days = months * 30
                pending.amount = amount
                pending.status = "pending"
                pending.meta = f"months={months}"
                await session.commit()
                return pending

            subscription = await subscriptions.create_placeholder(
                user_id=user.id,
                period_days=months * 30,
                amount=amount,
                status="pending",
            )
            subscription.meta = f"months={months}"
            await session.commit()
            return subscription

    async def mark_payment_submitted(self, telegram_id: int) -> Subscription:
        async with self._session_factory() as session:
            users = UserRepository(session)
            subscriptions = SubscriptionRepository(session)
            user = await users.get_by_telegram_id(telegram_id)
            if not user:
                raise ValueError("User not found")
            subscription = await subscriptions.get_pending_by_user_id(user.id)
            if not subscription:
                raise ValueError("Pending payment not found")
            await subscriptions.update_status(subscription, status="submitted")
            await session.commit()
            return subscription

    async def approve_payment(self, subscription_id: int) -> tuple[Subscription, VpnAccount]:
        async with self._session_factory() as session:
            subscriptions = SubscriptionRepository(session)
            users = UserRepository(session)
            accounts = VpnAccountRepository(session)

            subscription = await subscriptions.get_by_id(subscription_id)
            if not subscription:
                raise ValueError("Payment request not found")
            if subscription.status not in {"pending", "submitted"}:
                raise ValueError("Payment request already processed")

            user = await users.get_by_telegram_id(subscription.user.telegram_id)
            if not user:
                raise ValueError("User not found")
            account = await accounts.get_by_user_id(user.id)
            if account:
                account = await self._extend_existing_account_for_payment(
                    account=account,
                    days=subscription.period_days,
                    accounts=accounts,
                )
            else:
                account = await self._provision_paid_account_for_user(
                    user=user,
                    username=user.username,
                    days=subscription.period_days,
                    accounts=accounts,
                )
            await subscriptions.update_status(
                subscription,
                status="approved",
                starts_at=datetime.now(UTC),
                expires_at=account.expires_at,
            )
            await session.commit()
            return subscription, account

    async def reject_payment(self, subscription_id: int) -> Subscription:
        async with self._session_factory() as session:
            subscriptions = SubscriptionRepository(session)
            subscription = await subscriptions.get_by_id(subscription_id)
            if not subscription:
                raise ValueError("Payment request not found")
            if subscription.status not in {"pending", "submitted"}:
                raise ValueError("Payment request already processed")
            await subscriptions.update_status(subscription, status="rejected")
            await session.commit()
            return subscription

    @staticmethod
    def _build_client_email(telegram_id: int) -> str:
        return f"tg-{telegram_id}"

    def _default_payment_details(self) -> str | None:
        if self._settings.payment_phone:
            return f"СБП: {self._settings.payment_phone}"
        return None

    def _deserialize_plan_prices(self, raw_value: str | None) -> dict[int, int]:
        if not raw_value:
            return dict(self._settings.plan_prices)
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            logger.warning("Invalid plan_prices in bot settings, using defaults")
            return dict(self._settings.plan_prices)
        if not isinstance(parsed, dict):
            logger.warning("Invalid plan_prices shape in bot settings, using defaults")
            return dict(self._settings.plan_prices)
        try:
            return {int(key): int(value) for key, value in parsed.items()}
        except (TypeError, ValueError):
            logger.warning("Invalid plan_prices values in bot settings, using defaults")
            return dict(self._settings.plan_prices)

    def _deserialize_admin_ids(self, raw_value: str | None) -> set[int]:
        if not raw_value:
            return set()
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            logger.warning("Invalid admin_ids in bot settings, using defaults only")
            return set()
        if not isinstance(parsed, list):
            logger.warning("Invalid admin_ids shape in bot settings, using defaults only")
            return set()
        result: set[int] = set()
        for value in parsed:
            try:
                result.add(int(value))
            except (TypeError, ValueError):
                logger.warning("Skipping invalid admin id in bot settings: %s", value)
        return result

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
        duration_days: int | None = None,
    ) -> VpnAccount:
        expires_at = datetime.now(UTC) + timedelta(
            days=duration_days or self._settings.default_subscription_days
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
            period_days=duration_days or self._settings.default_subscription_days,
            status="active",
            starts_at=datetime.now(UTC),
            expires_at=xui_account.expires_at,
            amount=self._settings.plan_prices.get(
                max((duration_days or self._settings.default_subscription_days) // 30, 1),
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

    async def _extend_existing_account_for_payment(
        self,
        *,
        account: VpnAccount,
        days: int,
        accounts: VpnAccountRepository,
    ) -> VpnAccount:
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
        return account

    async def _provision_paid_account_for_user(
        self,
        *,
        user: User,
        username: str | None,
        days: int,
        accounts: VpnAccountRepository,
    ) -> VpnAccount:
        try:
            xui_account = await self._find_existing_xui_account(
                telegram_id=user.telegram_id,
                username=username,
                accounts=accounts,
            )
        except XUIClientNotFoundError:
            xui_account = None

        if xui_account:
            new_expires_at = datetime.now(UTC) + timedelta(days=days)
            activated_account = await self._xui_client.update_client_expiry(
                inbound_id=xui_account.inbound_id,
                client_id=xui_account.client_id,
                email=xui_account.email,
                expires_at=new_expires_at,
                enabled=True,
            )
            config_url = build_vless_config(
                settings=self._settings,
                uuid=activated_account.uuid,
                email=activated_account.email,
            )
            return await accounts.create(
                user_id=user.id,
                xui_client_id=activated_account.client_id,
                email=activated_account.email,
                uuid=activated_account.uuid,
                inbound_id=activated_account.inbound_id,
                config_url=config_url,
                expires_at=activated_account.expires_at,
                is_active=activated_account.enabled,
            )

        expires_at = datetime.now(UTC) + timedelta(days=days)
        email = self._build_client_email(user.telegram_id)
        created_account = await self._xui_client.create_client(
            email=email,
            expires_at=expires_at,
        )
        config_url = build_vless_config(
            settings=self._settings,
            uuid=created_account.uuid,
            email=created_account.email,
        )
        return await accounts.create(
            user_id=user.id,
            xui_client_id=created_account.client_id,
            email=created_account.email,
            uuid=created_account.uuid,
            inbound_id=created_account.inbound_id,
            config_url=config_url,
            expires_at=created_account.expires_at,
            is_active=created_account.enabled,
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
