import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.i18n import I18n
from aiogram.webhook.aiohttp_server import (SimpleRequestHandler,
                                            ip_filter_middleware,
                                            setup_application)
from aiogram.webhook.security import IPFilter
from aiohttp import web

import http_handlers
from config import config
from database.postgres import Database, PsycopgDatabase
from handlers import game, invite, start
from logger import setup_logger
from middlewares import (ignore_channels, register_error_handler,
                         register_i18n, register_throttle)
from services.gamecontroller import GameController
from services.wordprovider import FileWordProvider, FileWords

i18n = I18n(path="locales", default_locale="en", domain="messages")


def register_middlewares(dp: Dispatcher) -> None:
    register_i18n(dp, i18n)
    register_error_handler(dp)
    ignore_channels(dp)
    register_throttle(dp, timeframe_sec=10, capacity=7)


async def set_bot_commands(bot: Bot) -> None:
    _ = i18n.gettext
    private_commands = asyncio.gather(
        *[
            bot.set_my_commands(
                [
                    types.BotCommand(
                        command="start",
                        description=_("Start", locale=lang),
                    ),
                ],
                scope=types.BotCommandScopeAllPrivateChats(),
                language_code=lang,
            )
            for lang in i18n.available_locales
        ]
    )
    group_commands = asyncio.gather(
        *[
            bot.set_my_commands(
                [
                    types.BotCommand(
                        command="start",
                        description=_("Start", locale=lang),
                    ),
                    types.BotCommand(
                        command="game",
                        description=_("Create game", locale=lang),
                    ),
                    types.BotCommand(
                        command="cancel",
                        description=_("Cancel game", locale=lang),
                    ),
                ],
                scope=types.BotCommandScopeAllGroupChats(),
                language_code=lang,
            )
            for lang in i18n.available_locales
        ]
    )

    await asyncio.gather(private_commands, group_commands)


async def on_startup(dispatcher: Dispatcher, bot: Bot, db: Database) -> None:
    await db.open()
    await asyncio.gather(
        bot.set_webhook(
            f"{config.host}/bot/{config.webhook_endpoint_secret.get_secret_value()}",
            allowed_updates=dispatcher.resolve_used_update_types(),
            secret_token=config.telegram_bot_api_secret_token.get_secret_value(),
        ),
        set_bot_commands(bot),
    )


async def on_shutdown(db: Database) -> None:
    try:
        await db.close()
    except Exception:
        pass


def start_app() -> None:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_routers(start.router, game.router, invite.router)

    database = PsycopgDatabase(config.db_url.get_secret_value())
    dispatcher["db"] = database

    register_middlewares(dispatcher)

    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    bot = Bot(token=config.bot_token.get_secret_value(), parse_mode="HTML")

    game_controller = GameController(
        bot=bot,
        db=database,
        i18n=i18n,
        word_provider=FileWordProvider(
            FileWords(
                locale="en", filepath="./resources/words/en.txt", lines=1524),
        ),
        initial_canvas_file_id=config.initial_canvas_file_id,
    )
    http_handlers.provide_gamecontroller(game_controller)
    dispatcher["controller"] = game_controller

    app = web.Application()

    bot_app = web.Application()
    # bot_app.middlewares.append(ip_filter_middleware(IPFilter.default()))

    SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=config.telegram_bot_api_secret_token.get_secret_value(),
    ).register(bot_app, path=f"/{config.webhook_endpoint_secret.get_secret_value()}")

    setup_application(app, dispatcher, bot=bot)

    app.add_subapp("/bot", bot_app)
    app.add_subapp("/web", http_handlers.app)

    web.run_app(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    setup_logger()

    import sys

    if sys.platform == "win32":
        # required by psycopg async pool
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    else:
        import uvloop

        uvloop.install()

    start_app()
