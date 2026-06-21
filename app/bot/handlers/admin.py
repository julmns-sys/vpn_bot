from __future__ import annotations

from html import escape as quote

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.admin import admin_menu_keyboard
from app.bot.middlewares.admin import AdminFilter
from app.services.vpn_service import VPNService
from app.services.xui_client import XUIError


def create_admin_router(admin_ids: set[int]) -> Router:
    router = Router(name="admin")
    router.message.filter(AdminFilter(admin_ids))
    router.callback_query.filter(lambda query: bool(query.from_user and query.from_user.id in admin_ids))

    @router.message(Command("admin"))
    async def admin_menu(message: Message) -> None:
        await message.answer(
            "Админ-панель:\n"
            "/admin_find <telegram_id>\n"
            "/admin_import <telegram_id>\n"
            "/admin_import_email <telegram_id> <email>\n"
            "/admin_disable <telegram_id>\n"
            "/admin_extend <telegram_id> <days>\n"
            "/admin_recreate <telegram_id>",
            reply_markup=admin_menu_keyboard(),
        )

    @router.callback_query(F.data == "admin:stats")
    async def admin_stats(callback: CallbackQuery, vpn_service: VPNService) -> None:
        total = await vpn_service.count_users()
        await callback.message.answer(f"Всего пользователей: {total}")
        await callback.answer()

    @router.callback_query(F.data == "admin:help")
    async def admin_help(callback: CallbackQuery) -> None:
        await callback.message.answer(
            "Команды администратора:\n"
            "/admin_find <telegram_id>\n"
            "/admin_import <telegram_id>\n"
            "/admin_import_email <telegram_id> <email>\n"
            "/admin_disable <telegram_id>\n"
            "/admin_extend <telegram_id> <days>\n"
            "/admin_recreate <telegram_id>"
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("payment:approve:"))
    async def approve_payment(callback: CallbackQuery, vpn_service: VPNService, bot: Bot) -> None:
        subscription_id = int(callback.data.rsplit(":", 1)[1])
        try:
            subscription, account = await vpn_service.approve_payment(subscription_id)
        except (ValueError, XUIError) as exc:
            await callback.message.answer(f"Ошибка подтверждения: {exc}")
            await callback.answer()
            return
        await bot.send_message(
            subscription.user.telegram_id,
            "Оплата прошла успешно. Подписка продлена.",
        )
        await callback.message.answer(
            f"Оплата подтверждена для Telegram ID {subscription.user.telegram_id}.\n"
            f"Подписка до: {account.expires_at.isoformat()}"
        )
        await callback.answer("Подтверждено")

    @router.callback_query(F.data.startswith("payment:reject:"))
    async def reject_payment(callback: CallbackQuery, vpn_service: VPNService, bot: Bot) -> None:
        subscription_id = int(callback.data.rsplit(":", 1)[1])
        try:
            subscription = await vpn_service.reject_payment(subscription_id)
        except ValueError as exc:
            await callback.message.answer(f"Ошибка отклонения: {exc}")
            await callback.answer()
            return
        await bot.send_message(
            subscription.user.telegram_id,
            "Оплата не пришла. Проверь перевод и свяжись с администратором.",
        )
        await callback.message.answer(
            f"Заявка отклонена для Telegram ID {subscription.user.telegram_id}."
        )
        await callback.answer("Отклонено")

    @router.message(Command("admin_find"))
    async def admin_find(message: Message, vpn_service: VPNService) -> None:
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Использование: /admin_find <telegram_id>")
            return
        telegram_id = int(parts[1])
        data = await vpn_service.get_account_by_telegram_id(telegram_id)
        if not data:
            await message.answer("Пользователь не найден.")
            return
        user, account = data
        await message.answer(
            f"Пользователь: {user.first_name or '-'} (@{user.username or '-'})\n"
            f"Telegram ID: {user.telegram_id}\n"
            f"Статус: {'активен' if account.is_active else 'отключен'}\n"
            f"Подписка до: {account.expires_at.isoformat()}\n"
            f"Email: {account.email}"
        )

    @router.message(Command("admin_disable"))
    async def admin_disable(message: Message, vpn_service: VPNService) -> None:
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Использование: /admin_disable <telegram_id>")
            return
        try:
            account = await vpn_service.disable_account(int(parts[1]))
        except (ValueError, XUIError) as exc:
            await message.answer(f"Ошибка отключения: {exc}")
            return
        await message.answer(f"Пользователь отключен. Активность: {account.is_active}")

    @router.message(Command("admin_import"))
    async def admin_import(message: Message, vpn_service: VPNService) -> None:
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Использование: /admin_import <telegram_id>")
            return
        try:
            user, account = await vpn_service.import_account(int(parts[1]))
        except (ValueError, RuntimeError, XUIError) as exc:
            await message.answer(f"Ошибка импорта: {exc}")
            return
        await message.answer(
            f"Импорт выполнен.\n"
            f"Telegram ID: {user.telegram_id}\n"
            f"Email: {account.email}\n"
            f"Подписка до: {account.expires_at.isoformat()}"
        )

    @router.message(Command("admin_import_email"))
    async def admin_import_email(message: Message, vpn_service: VPNService) -> None:
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) != 3:
            await message.answer("Использование: /admin_import_email <telegram_id> <email>")
            return
        try:
            user, account = await vpn_service.import_account_by_email(
                telegram_id=int(parts[1]),
                email=parts[2].strip(),
            )
        except (ValueError, RuntimeError, XUIError) as exc:
            await message.answer(f"Ошибка импорта: {exc}")
            return
        await message.answer(
            f"Импорт выполнен.\n"
            f"Telegram ID: {user.telegram_id}\n"
            f"Email: {account.email}\n"
            f"Подписка до: {account.expires_at.isoformat()}"
        )

    @router.message(Command("admin_extend"))
    async def admin_extend(message: Message, vpn_service: VPNService) -> None:
        parts = (message.text or "").split()
        if len(parts) != 3:
            await message.answer("Использование: /admin_extend <telegram_id> <days>")
            return
        try:
            account = await vpn_service.extend_subscription(int(parts[1]), int(parts[2]))
        except (ValueError, XUIError) as exc:
            await message.answer(f"Ошибка продления: {exc}")
            return
        await message.answer(f"Подписка продлена до {account.expires_at.isoformat()}")

    @router.message(Command("admin_recreate"))
    async def admin_recreate(message: Message, vpn_service: VPNService) -> None:
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Использование: /admin_recreate <telegram_id>")
            return
        try:
            account = await vpn_service.recreate_config(int(parts[1]))
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await message.answer(
            f"Конфиг пересобран:\n<code>{quote(account.config_url)}</code>",
            parse_mode="HTML",
        )

    return router
