from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.services.vpn_service import VPNService

router = Router(name="billing")


@router.callback_query(F.data == "renew")
async def renew_callback(callback: CallbackQuery, vpn_service: VPNService) -> None:
    await callback.message.answer(vpn_service.build_payment_text())
    await callback.answer()
