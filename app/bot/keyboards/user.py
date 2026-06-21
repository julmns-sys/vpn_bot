from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Мой профиль", callback_data="profile")
    builder.button(text="Получить конфиг", callback_data="get_config")
    builder.button(text="Продлить", callback_data="renew")
    builder.button(text="Помощь", callback_data="help")
    builder.adjust(1)
    return builder.as_markup()
