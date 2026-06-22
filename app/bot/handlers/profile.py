from __future__ import annotations

from datetime import UTC
from html import escape as quote

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.user import main_menu_reply_keyboard
from app.services.vpn_service import VPNService

router = Router(name="profile")

UNPAID_TEXT = (
    "Статус: не активна\n"
    "Подписка ещё не оплачена.\n\n"
    "Сначала нажми «Оплатить подписку», после подтверждения оплаты появится конфиг."
)


def _format_profile(account_expires_at, is_active: bool, config_url: str) -> str:
    status = "активно" if is_active else "отключено"
    expires = account_expires_at.astimezone(UTC).strftime("%Y-%m-%d")
    return (
        f"Статус: {status}\n"
        f"Действует до: {expires}\n\n"
        f"Конфиг:\n<code>{quote(config_url)}</code>"
    )


@router.message(Command("profile"))
async def profile_command(message: Message, vpn_service: VPNService) -> None:
    if not message.from_user:
        return
    data = await vpn_service.get_account_by_telegram_id(message.from_user.id)
    if not data:
        await message.answer(UNPAID_TEXT, reply_markup=main_menu_reply_keyboard())
        return
    _, account = data
    await message.answer(
        _format_profile(account.expires_at, account.is_active, account.config_url),
        reply_markup=main_menu_reply_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery, vpn_service: VPNService) -> None:
    if not callback.from_user:
        return
    data = await vpn_service.get_account_by_telegram_id(callback.from_user.id)
    if not data:
        await callback.message.answer(UNPAID_TEXT, reply_markup=main_menu_reply_keyboard())
        await callback.answer()
        return
    _, account = data
    await callback.message.answer(
        _format_profile(account.expires_at, account.is_active, account.config_url),
        parse_mode="HTML",
    )
    await callback.answer()
