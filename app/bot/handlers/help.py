from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.user import main_menu_reply_keyboard

router = Router(name="help")

HELP_TEXT = (
    "Если возникли вопросы по оплате, конфигу или подключению, напиши администратору:\n"
    "<a href=\"https://t.me/nmnby\">@nmnby</a>"
)
INSTRUCTION_TEXT = (
    "Инструкция по подключению:\n\n"
    "1. Оплати подписку и получи свой конфиг.\n"
    "2. Скопируй VLESS-ссылку из бота.\n"
    "3. Установи VPN-клиент:\n"
    "iPhone: Happ\n"
    "Android: Happ или v2rayNG\n"
    "Windows: Hiddify Next, Nekoray или v2rayN\n"
    "macOS: Happ или Hiddify Next\n\n"
    "4. Открой приложение и импортируй конфиг по ссылке.\n"
    "Обычно это кнопка `Добавить` -> `Импорт из буфера обмена` или `Import from clipboard`.\n\n"
    "5. Сохрани профиль и нажми `Подключить`.\n\n"
    "Если конфиг не добавляется, напиши администратору и отправь скриншот ошибки."
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
    await message.answer(HELP_TEXT, reply_markup=main_menu_reply_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery) -> None:
    await callback.message.answer(HELP_TEXT, reply_markup=main_menu_reply_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(Command("instruction"))
async def instruction_command(message: Message) -> None:
    await message.answer(INSTRUCTION_TEXT, reply_markup=main_menu_reply_keyboard())


@router.message(Command("rules"))
async def rules_command(message: Message) -> None:
    await message.answer(RULES_TEXT, reply_markup=main_menu_reply_keyboard())
