import asyncio
from pathlib import Path
from typing import Union

import aiohttp_jinja2
import jinja2
from aiohttp import web
from aiohttp_sse import EventSourceResponse, sse_response
from aiohttplimiter import Limiter, default_keyfunc

from services.gamecontroller import (GameController, GameEvent, GameEventType,
                                     GameWordStatus)

limiter = Limiter(keyfunc=default_keyfunc)


@limiter.limit("1/second")
async def miniapp_handler(request: web.Request) -> web.Response:
    return await aiohttp_jinja2.render_template_async(
        "paint.html", request, context=None
    )


@limiter.limit("1/second")
async def update_canvas_handler(request: web.Request) -> web.Response:
    if request.content_type != "multipart/form-data":
        return web.Response(status=401, text="Incorrect content type")

    params = await request.post()

    if "_auth" not in params or "image" not in params or "gameId" not in params:
        return web.Response(status=401, text="Some keys are missing")

    controller: GameController = request.app["controller"]

    return (
        web.Response(text="OK")
        if await controller.update_state(
            init_data=params["_auth"], game_id=params["gameId"], image=params["image"]
        )
        else web.Response(text="error", status=401)
    )


@limiter.limit("1/second")
async def get_word_handler(request: web.Request) -> web.Response:
    params = request.rel_url.query

    if "_auth" not in params or "gameId" not in params:
        return web.Response(status=401, text="Some keys are missing")

    controller: GameController = request.app["controller"]
    word_result = await controller.get_word(
        init_data=params["_auth"], game_id=params["gameId"]
    )

    match word_result.status:
        case GameWordStatus.Ok:
            return web.Response(text=word_result.word)
        case _:
            return web.Response(text=word_result.status, status=401)


class EventSourceResponsePatched(EventSourceResponse):
    """Patched EventSourceResponse:

    `_ping()` - Cancellation on ConnectionResetError

    `is_connected()` - Check connection is prepared and ping task is not done
    """

    async def _ping(self):
        """https://github.com/aio-libs/aiohttp-sse/pull/370"""
        # periodically send ping to the browser. Any message that
        # starts with ":" colon ignored by a browser and could be used
        # as ping message.
        while True:
            await asyncio.sleep(self._ping_interval)
            try:
                await self.write(": ping{0}{0}".format(self._sep).encode("utf-8"))
            except ConnectionResetError:
                self._ping_task.cancel()

    def is_connected(self) -> bool:
        """Check connection is prepared and ping task is not done.
        https://github.com/aio-libs/aiohttp-sse/pull/401
        """
        return self.prepared and not self._ping_task.done()


@limiter.limit("1/second")
async def game_events_handler(request: web.Request) -> web.Response:
    params = request.rel_url.query

    if "_auth" not in params or "gameId" not in params:
        return web.Response(status=204)

    controller: GameController = request.app["controller"]
    _auth = params["_auth"]
    game_id = params["gameId"]

    queue = await controller.sub(init_data=_auth, game_id=game_id)

    resp: EventSourceResponsePatched
    async with sse_response(request, response_cls=EventSourceResponsePatched) as resp:
        resp.ping_interval = 5

        async def stop_event_on_disconnect() -> None:
            await resp.wait()
            await queue.put(GameEventType.Disconnect)

        asyncio.create_task(stop_event_on_disconnect())

        try:
            while resp.is_connected():
                event: Union[GameEvent, GameEventType]
                event = await queue.get()
                queue.task_done()

                if event == GameEventType.Disconnect:
                    break

                await resp.send(data=event.data, event=event.type)

                if event.type == GameEventType.Error:
                    await resp.send("reset", event="reset")
                    break
        except ConnectionResetError:
            pass
        finally:
            await controller.unsub(
                game_id=game_id,
                session_queue=queue
            )

    return resp


app = web.Application()
aiohttp_jinja2.setup(
    app,
    enable_async=True,
    loader=jinja2.FileSystemLoader(
        Path(__file__).parent.resolve() / "templates"),
)
app.add_routes(
    [
        web.get("", miniapp_handler),
        web.post("/update", update_canvas_handler),
        web.get("/word", get_word_handler),
        web.get("/events", game_events_handler),
        web.static(
            "/static", Path(__file__).parent.resolve() / "static", name="static"
        ),
    ]
)
app["static_root_url"] = "/web/app/static"
