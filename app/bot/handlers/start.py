from __future__ import annotations

from html import escape as quote
import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.user import main_menu_keyboard, main_menu_reply_keyboard
from app.services.vpn_service import VPNService
from app.services.xui_client import XUIError

logger = logging.getLogger(__name__)

router = Router(name="start")


def _profile_text(name: str, account_expires_at: datetime, is_active: bool) -> str:
    status = "активен" if is_active else "отключен"
    expires = account_expires_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Привет, {name}!\n\n"
        f"Статус: {status}\n"
        f"Подписка до: {expires}\n\n"
        "Выбери действие ниже."
    )


@router.message(CommandStart())
async def start_command(message: Message, vpn_service: VPNService) -> None:
    if not message.from_user:
        return
    try:
        user, account, created = await vpn_service.get_or_create_account(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    except XUIError as exc:
        logger.exception("Failed to provision account")
        await message.answer(
            "Не удалось связаться с VPN-панелью. Попробуй позже или напиши администратору."
        )
        return

    text = _profile_text(
        name=user.first_name or user.username or "пользователь",
        account_expires_at=account.expires_at,
        is_active=account.is_active,
    )
    if created:
        text += f"\n\nТвой конфиг:\n<code>{quote(account.config_url)}</code>"
    await message.answer(text, reply_markup=main_menu_reply_keyboard(), parse_mode="HTML")
    await message.answer("Быстрые действия:", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "get_config")
async def get_config_callback(callback: CallbackQuery, vpn_service: VPNService) -> None:
    if not callback.from_user:
        return
    data = await vpn_service.get_account_by_telegram_id(callback.from_user.id)
    if not data:
        await callback.message.answer("Аккаунт не найден. Нажми /start.")
        await callback.answer()
        return
    _, account = data
    await callback.message.answer(
        f"Твой конфиг:\n<code>{quote(account.config_url)}</code>",
        parse_mode="HTML",
    )
    await callback.answer()
