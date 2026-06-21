from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Статистика", callback_data="admin:stats")
    builder.button(text="Инструкция", callback_data="admin:help")
    builder.adjust(1)
    return builder.as_markup()
