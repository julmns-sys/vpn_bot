from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.user import main_menu_reply_keyboard

router = Router(name="help")

HELP_TEXT = (
    "Команды бота:\n"
    "/start - открыть бота и получить аккаунт\n"
    "/profile - посмотреть профиль\n"
    "/help - помощь\n\n"
    "Кнопка «Получить конфиг» повторно покажет твою VLESS-ссылку.\n"
    "Кнопка «Продлить» покажет реквизиты и доступные тарифы."
)
RULES_TEXT = (
    "Правила использования:\n"
    "1. Не передавай конфиг третьим лицам.\n"
    "2. Не используй VPN для спама, атак и незаконной активности.\n"
    "3. При проблемах с подключением напиши администратору.\n"
    "4. Один аккаунт привязан к одному пользователю Telegram."
)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_reply_keyboard())


@router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery) -> None:
    await callback.message.answer(HELP_TEXT)
    await callback.answer()


@router.message(Command("rules"))
async def rules_command(message: Message) -> None:
    await message.answer(RULES_TEXT, reply_markup=main_menu_reply_keyboard())
