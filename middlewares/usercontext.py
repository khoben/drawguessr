from contextlib import suppress
from typing import Any, Awaitable, Callable, Dict, Tuple, Union

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _

from database import User


class UserContextMiddleware(BaseMiddleware):
    def __init__(
        self, get_or_create_user: Callable[[int], Awaitable[Tuple[User, bool]]]
    ) -> None:
        self.__get_or_create_user = get_or_create_user

    async def __call__(
        self,
        handler: Callable[
            [Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]
        ],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        user, created = await self.__get_or_create_user(user_id)
        if user.banned:
            with suppress(Exception):
                await event.answer(text=_("🚫 Denied service"))
            return

        data["user"] = user
        data["user_created"] = created

        return await handler(event, data)
