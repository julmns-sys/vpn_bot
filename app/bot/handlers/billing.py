from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.user import (
    admin_payment_decision_keyboard,
    payment_confirmation_keyboard,
    payment_plans_reply_keyboard,
)
from app.services.vpn_service import VPNService

router = Router(name="billing")


@router.callback_query(F.data == "renew")
async def renew_callback(callback: CallbackQuery, vpn_service: VPNService) -> None:
    _, _, plan_prices = await vpn_service.get_billing_settings()
    await callback.message.answer(
        "Выберите срок подписки:",
        reply_markup=payment_plans_reply_keyboard(plan_prices),
    )
    await callback.answer()


async def send_payment_info(message: Message, vpn_service: VPNService) -> None:
    _, _, plan_prices = await vpn_service.get_billing_settings()
    await message.answer(
        "Выберите срок подписки:",
        reply_markup=payment_plans_reply_keyboard(plan_prices),
    )


@router.callback_query(F.data == "payment:submitted")
async def payment_submitted_callback(
    callback: CallbackQuery,
    vpn_service: VPNService,
    bot: Bot,
) -> None:
    if not callback.from_user:
        await callback.answer()
        return
    try:
        subscription = await vpn_service.mark_payment_submitted(callback.from_user.id)
    except ValueError as exc:
        await callback.message.answer(str(exc))
        await callback.answer()
        return

    months = max(subscription.period_days // 30, 1)
    await notify_admins_about_payment(
        bot=bot,
        admin_ids=await vpn_service.get_admin_ids(),
        subscription_id=subscription.id,
        user_telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        months=months,
        amount=subscription.amount,
    )
    await callback.message.answer("Заявка отправлена администратору. Ожидай подтверждения оплаты.")
    await callback.answer("Заявка отправлена")


async def notify_admins_about_payment(
    *,
    bot: Bot,
    admin_ids: set[int],
    subscription_id: int,
    user_telegram_id: int,
    username: str | None,
    months: int,
    amount: int | None,
) -> None:
    username_part = f"@{username}" if username else "-"
    text = (
        "Новая заявка на оплату.\n"
        f"Subscription ID: {subscription_id}\n"
        f"Telegram ID: {user_telegram_id}\n"
        f"Username: {username_part}\n"
        f"Тариф: {months} мес.\n"
        f"Сумма: {amount or '-'} руб."
    )
    for admin_id in admin_ids:
        await bot.send_message(
            admin_id,
            text,
            reply_markup=admin_payment_decision_keyboard(subscription_id),
        )
