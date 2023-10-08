import time
from contextlib import suppress
from typing import Any, Awaitable, Callable, Dict, Union, NamedTuple

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from cachetools import TTLCache
from aiogram.utils.i18n import gettext as _

class ThrottledUserData(NamedTuple):
    start_time: float
    count: int


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(
        self, timeframe_sec: float = 60, capacity: int = 20, cache_size: int = 10_000
    ) -> None:
        self.timer = time.monotonic
        self.timeframe_sec = timeframe_sec
        self.capacity = capacity
        # [id, [start_time, count]]
        self.throttle_cache = TTLCache[int, ThrottledUserData](
            maxsize=cache_size, ttl=timeframe_sec
        )

    async def __call__(
        self,
        handler: Callable[
            [Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]
        ],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        throttled = self.throttle_cache.get(user_id)
        current_time = self.timer()
        if throttled:
            if throttled.start_time + self.timeframe_sec > current_time:
                # check count within timeframe
                req_num = throttled.count + 1
                if req_num <= self.capacity:
                    self.throttle_cache[user_id] = ThrottledUserData(
                        throttled.start_time, req_num
                    )
                    return await handler(event, data)
                else:
                    if req_num == self.capacity + 1:
                        self.throttle_cache[user_id] = ThrottledUserData(
                            throttled.start_time, req_num + 1
                        )
                        with suppress(Exception):
                            await event.answer(_("Slow down please"))
                    return
            else:
                # reset timeframe
                self.throttle_cache[user_id] = ThrottledUserData(current_time, 1)
        else:
            self.throttle_cache[user_id] = ThrottledUserData(current_time, 1)

        return await handler(event, data)
