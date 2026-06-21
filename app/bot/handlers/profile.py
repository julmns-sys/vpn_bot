from __future__ import annotations

from datetime import UTC

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.user import main_menu_keyboard, main_menu_reply_keyboard
from app.services.vpn_service import VPNService

router = Router(name="profile")


def _format_profile(account_expires_at, is_active: bool) -> str:
    status = "активен" if is_active else "отключен"
    expires = account_expires_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Статус: {status}\n"
        f"Подписка до: {expires}"
    )


@router.message(Command("profile"))
async def profile_command(message: Message, vpn_service: VPNService) -> None:
    if not message.from_user:
        return
    data = await vpn_service.get_account_by_telegram_id(message.from_user.id)
    if not data:
        await message.answer("Профиль не найден. Нажми /start.")
        return
    _, account = data
    await message.answer(
        _format_profile(account.expires_at, account.is_active),
        reply_markup=main_menu_reply_keyboard(),
    )
    await message.answer("Быстрые действия:", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery, vpn_service: VPNService) -> None:
    if not callback.from_user:
        return
    data = await vpn_service.get_account_by_telegram_id(callback.from_user.id)
    if not data:
        await callback.message.answer("Профиль не найден. Нажми /start.")
        await callback.answer()
        return
    _, account = data
    await callback.message.answer(_format_profile(account.expires_at, account.is_active))
    await callback.answer()
