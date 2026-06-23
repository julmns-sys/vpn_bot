from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.services.vpn_service import VPNService


class AdminFilter(BaseFilter):
    async def __call__(self, message: Message, vpn_service: VPNService) -> bool:
        if not message.from_user:
            return False
        return message.from_user.id in await vpn_service.get_admin_ids()


class AdminCallbackFilter(BaseFilter):
    async def __call__(self, query: CallbackQuery, vpn_service: VPNService) -> bool:
        if not query.from_user:
            return False
        return query.from_user.id in await vpn_service.get_admin_ids()
