from __future__ import annotations

import argparse
import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher

from app.bot.router import setup_routers
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import create_engine, create_session_factory
from app.services.notification_service import NotificationService
from app.services.vpn_service import VPNService
from app.services.xui_client import XUIClient

logger = logging.getLogger(__name__)


def build_dispatcher(vpn_service: VPNService) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher["vpn_service"] = vpn_service
    setup_routers(dispatcher)
    return dispatcher


async def run_bot() -> None:
    settings = get_settings()
    setup_logging()

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    xui_client = XUIClient(settings)
    vpn_service = VPNService(session_factory, xui_client, settings)

    bot = Bot(token=settings.bot_token)
    dispatcher = build_dispatcher(vpn_service)
    notification_service = NotificationService(session_factory, bot)
    notification_task = asyncio.create_task(notification_service.run_forever())

    logger.info("Starting bot polling")
    try:
        await dispatcher.start_polling(bot)
    finally:
        notification_task.cancel()
        with suppress(asyncio.CancelledError):
            await notification_task
        await bot.session.close()
        await xui_client.close()
        await engine.dispose()


async def check_xui() -> None:
    settings = get_settings()
    setup_logging()
    xui_client = XUIClient(settings)
    try:
        await xui_client.check_connection()
        print("3x-ui connection OK")
    finally:
        await xui_client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VPN bot runner")
    parser.add_argument(
        "--check-xui",
        action="store_true",
        help="Check 3x-ui connection and exit",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    coroutine = check_xui() if args.check_xui else run_bot()
    with suppress(KeyboardInterrupt):
        asyncio.run(coroutine)


if __name__ == "__main__":
    main()
