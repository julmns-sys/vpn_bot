from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.user import payment_plans_reply_keyboard
from app.services.vpn_service import VPNService

router = Router(name="billing")


@router.callback_query(F.data == "renew")
async def renew_callback(callback: CallbackQuery, vpn_service: VPNService) -> None:
    await callback.message.answer(
        vpn_service.build_payment_text(),
        reply_markup=payment_plans_reply_keyboard(),
    )
    await callback.answer()


async def send_payment_info(message: Message, vpn_service: VPNService) -> None:
    await message.answer(
        vpn_service.build_payment_text(),
        reply_markup=payment_plans_reply_keyboard(),
    )
