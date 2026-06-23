from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.keyboard import ReplyKeyboardBuilder

MENU_PROFILE_TEXT = "⭐ Моя подписка"
MENU_RENEW_TEXT = "🐝 Оплатить подписку"
MENU_HELP_TEXT = "📲 Инструкция по подключению"
MENU_SUPPORT_TEXT = "🆘 Нужна помощь?"
MENU_RULES_TEXT = "📜 Правила использования"
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
    builder.button(text=MENU_SUPPORT_TEXT)
    builder.button(text=MENU_RULES_TEXT)
    builder.adjust(1)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выбери действие...",
    )


def format_plan_button_text(months: int, amount: int) -> str:
    suffix = "месяц" if months == 1 else "месяца" if months in {2, 3} else "месяцев"
    return f"{months} {suffix} - {amount} руб"


def payment_plans_reply_keyboard(plan_prices: dict[int, int]) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for months, amount in sorted(plan_prices.items()):
        builder.button(text=format_plan_button_text(months, amount))
    builder.button(text=BACK_TO_MENU_TEXT)
    builder.adjust(1)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выбери тариф...",
    )


def payment_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Я оплатил", callback_data="payment:submitted")
    return builder.as_markup()


def admin_payment_decision_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data=f"payment:approve:{subscription_id}")
    builder.button(text="Отклонить", callback_data=f"payment:reject:{subscription_id}")
    builder.adjust(1)
    return builder.as_markup()
