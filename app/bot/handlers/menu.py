from __future__ import annotations

from html import escape as quote

from aiogram import F, Router
from aiogram.types import Message

from app.bot.handlers.billing import send_payment_info
from app.bot.handlers.help import HELP_TEXT, INSTRUCTION_TEXT, RULES_TEXT
from app.bot.handlers.profile import _format_profile
from app.bot.keyboards.user import (
    BACK_TO_MENU_TEXT,
    format_plan_button_text,
    main_menu_reply_keyboard,
)
from app.services.vpn_service import VPNService

router = Router(name="menu")


UNPAID_TEXT = (
    "Подписка ещё не оплачена.\n"
    "Сначала нажми «Оплатить подписку», после подтверждения оплаты бот выдаст конфиг."
)


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
            await message.answer(UNPAID_TEXT, reply_markup=main_menu_reply_keyboard())
            return
        _, account = data
        await message.answer(
            _format_profile(account.expires_at, account.is_active, account.config_url),
            reply_markup=main_menu_reply_keyboard(),
            parse_mode="HTML",
        )
        return

    if "оплатить подписку" in text or text == "продлить":
        await send_payment_info(message, vpn_service)
        return

    plan_prices = (await vpn_service.get_billing_settings())[2]
    matched_plan = next(
        (
            months
            for months, amount in plan_prices.items()
            if text == format_plan_button_text(months, amount).lower()
        ),
        None,
    )
    if matched_plan is not None:
        if not message.from_user:
            return
        await vpn_service.create_payment_request(
            message.from_user.id,
            matched_plan,
        )
        await message.answer(
            await vpn_service.build_plan_payment_text(matched_plan),
            reply_markup=main_menu_reply_keyboard(),
        )
        from app.bot.keyboards.user import payment_confirmation_keyboard

        await message.answer(
            "Когда переведёте деньги, нажмите кнопку ниже.",
            reply_markup=payment_confirmation_keyboard(),
        )
        return

    if text == BACK_TO_MENU_TEXT.lower():
        await message.answer("Главное меню:", reply_markup=main_menu_reply_keyboard())
        return

    if "инструкция по подключению" in text:
        await message.answer(INSTRUCTION_TEXT, reply_markup=main_menu_reply_keyboard())
        return

    if "нужна помощь" in text or text == "помощь":
        await message.answer(HELP_TEXT, reply_markup=main_menu_reply_keyboard(), parse_mode="HTML")
        return

    if "правила использования" in text:
        await message.answer(RULES_TEXT, reply_markup=main_menu_reply_keyboard())
        return

    if "получить конфиг" in text:
        if not message.from_user:
            return
        data = await vpn_service.get_account_by_telegram_id(message.from_user.id)
        if not data:
            await message.answer(UNPAID_TEXT, reply_markup=main_menu_reply_keyboard())
            return
        _, account = data
        await message.answer(
            f"Твой конфиг:\n<code>{quote(account.config_url)}</code>",
            parse_mode="HTML",
            reply_markup=main_menu_reply_keyboard(),
        )
