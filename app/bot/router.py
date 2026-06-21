from aiogram import Dispatcher

from app.bot.handlers import admin, billing, help, menu, profile, start


def setup_routers(dispatcher: Dispatcher, admin_ids: set[int]) -> None:
    dispatcher.include_router(start.router)
    dispatcher.include_router(profile.router)
    dispatcher.include_router(billing.router)
    dispatcher.include_router(help.router)
    dispatcher.include_router(menu.router)
    dispatcher.include_router(admin.create_admin_router(admin_ids))
