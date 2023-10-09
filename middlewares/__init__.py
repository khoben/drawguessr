from aiogram import Dispatcher, F, exceptions
from aiogram.types.error_event import ErrorEvent
from aiogram.utils.i18n import I18n
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n.middleware import SimpleI18nMiddleware

from database import Database
from logger import logger
from middlewares.throttling import ThrottlingMiddleware
from middlewares.usercontext import UserContextMiddleware


def register_error_handler(dp: Dispatcher):
    async def error_handler(error: ErrorEvent):
        update = error.update
        exception = error.exception
        exception_message = (
            exception.message if hasattr(
                exception, "message") else str(exception)
        )
        logger.exception(
            f"Caused {type(exception).__name__} "
            f"in update {update.model_dump_json()}: {exception_message}"
        )

        if update.message and not (
            isinstance(exception, exceptions.TelegramBadRequest)
            and exception.method == "editMessageText"
        ):
            try:
                await update.message.reply(
                    text=_(
                        "An unexpected error has occurred. Retry the request at a later time"
                    )
                )
            except Exception:
                pass

        return True

    dp.errors.register(error_handler)


def register_throttle(
    dp: Dispatcher,
    timeframe_sec: float = 60,
    capacity: int = 20,
    cache_size: int = 10_000,
):
    middleware = ThrottlingMiddleware(timeframe_sec, capacity, cache_size)
    dp.message.middleware.register(middleware)
    dp.callback_query.middleware.register(middleware)


def restrict_to_private_chats(dp: Dispatcher):
    dp.message.filter(F.chat.type == "private")


def ignore_channels(dp: Dispatcher):
    dp.message.filter(F.chat.type != "channel")


def register_i18n(dp: Dispatcher, i18n: I18n):
    SimpleI18nMiddleware(i18n).setup(dp)


def register_user_context(dp: Dispatcher, db: Database):
    """Register user context middleware"""
    middleware = UserContextMiddleware(
        get_or_create_user=db.get_user_or_create)
    dp.message.middleware.register(middleware)
    dp.callback_query.middleware.register(middleware)
