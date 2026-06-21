from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.keyboard import ReplyKeyboardBuilder

MENU_PROFILE_TEXT = "⭐ Моя подписка"
MENU_RENEW_TEXT = "🐝 Оплатить подписку"
MENU_HELP_TEXT = "🆘 Нужна помощь?"
MENU_RULES_TEXT = "📜 Правила использования"


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Мой профиль", callback_data="profile")
    builder.button(text="Получить конфиг", callback_data="get_config")
    builder.button(text="Продлить", callback_data="renew")
    builder.button(text="Помощь", callback_data="help")
    builder.adjust(1)
    return builder.as_markup()


def main_menu_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=MENU_PROFILE_TEXT)
    builder.button(text=MENU_RENEW_TEXT)
    builder.button(text=MENU_HELP_TEXT)
    builder.button(text=MENU_RULES_TEXT)
    builder.adjust(1)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выбери действие...",
    )
