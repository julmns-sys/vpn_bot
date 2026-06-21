from __future__ import annotations

from html import escape as quote

from aiogram import F, Router
from aiogram.types import Message

from app.bot.handlers.billing import send_payment_info
from app.bot.handlers.help import HELP_TEXT, RULES_TEXT
from app.bot.handlers.profile import _format_profile
from app.bot.keyboards.user import (
    BACK_TO_MENU_TEXT,
    PLAN_1_TEXT,
    PLAN_2_TEXT,
    PLAN_3_TEXT,
    PLAN_6_TEXT,
    main_menu_reply_keyboard,
)
from app.services.vpn_service import VPNService

router = Router(name="menu")


def _normalized_menu_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


@router.message(F.text)
async def menu_buttons_handler(message: Message, vpn_service: VPNService) -> None:
    text = _normalized_menu_text(message.text or "")
    if "моя подписка" in text:
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
        return

    if "оплатить подписку" in text or text == "продлить":
        await send_payment_info(message, vpn_service)
        return

    if text in {
        PLAN_1_TEXT.lower(),
        PLAN_2_TEXT.lower(),
        PLAN_3_TEXT.lower(),
        PLAN_6_TEXT.lower(),
    }:
        await message.answer(
            "Для оплаты переведи сумму по реквизитам ниже и после оплаты напиши администратору.",
            reply_markup=main_menu_reply_keyboard(),
        )
        await message.answer(vpn_service.build_payment_text(), reply_markup=main_menu_reply_keyboard())
        return

    if text == BACK_TO_MENU_TEXT.lower():
        await message.answer("Главное меню:", reply_markup=main_menu_reply_keyboard())
        return

    if "нужна помощь" in text or text == "помощь":
        await message.answer(HELP_TEXT, reply_markup=main_menu_reply_keyboard())
        return

    if "правила использования" in text:
        await message.answer(RULES_TEXT, reply_markup=main_menu_reply_keyboard())
        return

    if "получить конфиг" in text:
        if not message.from_user:
            return
        data = await vpn_service.get_account_by_telegram_id(message.from_user.id)
        if not data:
            await message.answer("Аккаунт не найден. Нажми /start.")
            return
        _, account = data
        await message.answer(
            f"Твой конфиг:\n<code>{quote(account.config_url)}</code>",
            parse_mode="HTML",
            reply_markup=main_menu_reply_keyboard(),
        )
