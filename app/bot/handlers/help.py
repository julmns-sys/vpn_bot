from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

router = Router(name="help")

HELP_TEXT = (
    "Команды бота:\n"
    "/start - открыть бота и получить аккаунт\n"
    "/profile - посмотреть профиль\n"
    "/help - помощь\n\n"
    "Кнопка «Получить конфиг» повторно покажет твою VLESS-ссылку.\n"
    "Кнопка «Продлить» покажет реквизиты и доступные тарифы."
)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery) -> None:
    await callback.message.answer(HELP_TEXT)
    await callback.answer()
