from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.keyboard import ReplyKeyboardBuilder

MENU_PROFILE_TEXT = "⭐ Моя подписка"
MENU_RENEW_TEXT = "🐝 Оплатить подписку"
MENU_HELP_TEXT = "🆘 Нужна помощь?"
MENU_RULES_TEXT = "📜 Правила использования"
PLAN_1_TEXT = "1 месяц - 100 руб"
PLAN_2_TEXT = "2 месяца - 190 руб"
PLAN_3_TEXT = "3 месяца - 280 руб"
PLAN_6_TEXT = "6 месяцев - 555 руб"
BACK_TO_MENU_TEXT = "⬅️ Назад в меню"


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


def payment_plans_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=PLAN_1_TEXT)
    builder.button(text=PLAN_2_TEXT)
    builder.button(text=PLAN_3_TEXT)
    builder.button(text=PLAN_6_TEXT)
    builder.button(text=BACK_TO_MENU_TEXT)
    builder.adjust(1)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выбери тариф...",
    )
