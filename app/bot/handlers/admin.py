from __future__ import annotations

from datetime import UTC
from html import escape as quote

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.admin import admin_menu_keyboard
from app.bot.middlewares.admin import AdminCallbackFilter, AdminFilter
from app.services.vpn_service import VPNService
from app.services.xui_client import XUIError


ADMIN_COMMANDS_TEXT = (
    "Команды администратора:\n"
    "/admin\n"
    "/admin_help\n"
    "/admin_find <telegram_id>\n"
    "/admin_import <telegram_id>\n"
    "/admin_import_email <telegram_id> <email>\n"
    "/admin_disable <telegram_id>\n"
    "/admin_extend <telegram_id> <days>\n"
    "/admin_recreate <telegram_id>\n"
    "/admin_billing\n"
    "/admin_set_price <months> <amount>\n"
    "/admin_set_requisites <text>\n"
    "/admin_set_price_text <text>\n"
    "/admin_list\n"
    "/admin_add\n\n"
    "Для /admin_add отправь команду ответом на сообщение пользователя, на пересланное сообщение или на контакт."
)


def create_admin_router() -> Router:
    router = Router(name="admin")
    router.message.filter(AdminFilter())
    router.callback_query.filter(AdminCallbackFilter())

    @router.message(Command("admin"))
    async def admin_menu(message: Message) -> None:
        await message.answer(ADMIN_COMMANDS_TEXT, reply_markup=admin_menu_keyboard())

    @router.message(Command("admin_help"))
    async def admin_help_command(message: Message) -> None:
        await message.answer(ADMIN_COMMANDS_TEXT, reply_markup=admin_menu_keyboard())

    @router.callback_query(F.data == "admin:stats")
    async def admin_stats(callback: CallbackQuery, vpn_service: VPNService) -> None:
        total = await vpn_service.count_users()
        await callback.message.answer(f"Всего пользователей: {total}")
        await callback.answer()

    @router.callback_query(F.data == "admin:help")
    async def admin_help(callback: CallbackQuery) -> None:
        await callback.message.answer(ADMIN_COMMANDS_TEXT)
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
            "Оплата прошла успешно.\n"
            f"Подписка действует до: {account.expires_at.astimezone(UTC).strftime('%Y-%m-%d')}\n\n"
            f"Твой конфиг:\n<code>{quote(account.config_url)}</code>",
            parse_mode="HTML",
        )
        await callback.message.answer(
            f"Оплата подтверждена для Telegram ID {subscription.user.telegram_id}.\n"
            f"Подписка до: {account.expires_at.astimezone(UTC).strftime('%Y-%m-%d')}"
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

    @router.message(Command("admin_billing"))
    async def admin_billing(message: Message, vpn_service: VPNService) -> None:
        price_text, payment_details, plan_prices = await vpn_service.get_billing_settings()
        lines = [
            "Текущие настройки оплаты:",
            f"Текст: {price_text}",
            f"Реквизиты: {payment_details or '-'}",
            "Тарифы:",
        ]
        for months, amount in sorted(plan_prices.items()):
            lines.append(f"{months} мес. - {amount} руб.")
        await message.answer("\n".join(lines))

    @router.message(Command("admin_set_price"))
    async def admin_set_price(message: Message, vpn_service: VPNService) -> None:
        parts = (message.text or "").split()
        if len(parts) != 3:
            await message.answer("Использование: /admin_set_price <months> <amount>")
            return
        try:
            months = int(parts[1])
            amount = int(parts[2])
        except ValueError:
            await message.answer("Months и amount должны быть числами.")
            return
        if months <= 0 or amount <= 0:
            await message.answer("Months и amount должны быть больше нуля.")
            return
        plan_prices = await vpn_service.update_plan_price(months=months, amount=amount)
        lines = ["Тариф обновлён:"]
        for item_months, item_amount in sorted(plan_prices.items()):
            lines.append(f"{item_months} мес. - {item_amount} руб.")
        await message.answer("\n".join(lines))

    @router.message(Command("admin_set_requisites"))
    async def admin_set_requisites(message: Message, vpn_service: VPNService) -> None:
        raw_text = (message.text or "").removeprefix("/admin_set_requisites").strip()
        if not raw_text:
            await message.answer("Использование: /admin_set_requisites <text>")
            return
        details = await vpn_service.update_payment_details(raw_text)
        await message.answer(f"Реквизиты обновлены:\n{details}")

    @router.message(Command("admin_set_price_text"))
    async def admin_set_price_text(message: Message, vpn_service: VPNService) -> None:
        raw_text = (message.text or "").removeprefix("/admin_set_price_text").strip()
        if not raw_text:
            await message.answer("Использование: /admin_set_price_text <text>")
            return
        text_value = await vpn_service.update_price_text(raw_text)
        await message.answer(f"Текст оплаты обновлён:\n{text_value}")

    @router.message(Command("admin_list"))
    async def admin_list(message: Message, vpn_service: VPNService) -> None:
        admin_ids = sorted(await vpn_service.get_admin_ids())
        lines = ["Список администраторов:"]
        for admin_id in admin_ids:
            lines.append(str(admin_id))
        await message.answer("\n".join(lines))

    @router.message(Command("admin_add"))
    async def admin_add(message: Message, vpn_service: VPNService) -> None:
        target_id = _extract_admin_candidate_id(message)
        if target_id is None:
            await message.answer(
                "Не удалось определить Telegram ID.\n"
                "Используй /admin_add ответом на сообщение пользователя, на пересланное сообщение или на контакт."
            )
            return
        admin_ids = await vpn_service.add_admin_id(target_id)
        await message.answer(
            f"Администратор добавлен: {target_id}\n"
            f"Всего администраторов: {len(admin_ids)}"
        )

    return router


def _extract_admin_candidate_id(message: Message) -> int | None:
    if message.contact and message.contact.user_id:
        return int(message.contact.user_id)

    if message.reply_to_message:
        reply = message.reply_to_message
        if reply.contact and reply.contact.user_id:
            return int(reply.contact.user_id)
        if reply.from_user:
            return int(reply.from_user.id)
        forward_origin = getattr(reply, "forward_origin", None)
        sender_user = getattr(forward_origin, "sender_user", None)
        if sender_user:
            return int(sender_user.id)

    forward_origin = getattr(message, "forward_origin", None)
    sender_user = getattr(forward_origin, "sender_user", None)
    if sender_user:
        return int(sender_user.id)

    return None
