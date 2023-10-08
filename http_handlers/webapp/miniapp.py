from pathlib import Path

from aiohttp import web
from aiohttplimiter import default_keyfunc, Limiter
import aiohttp_jinja2
import jinja2

from services.gamecontroller import GameController, GameWordStatus

limiter = Limiter(keyfunc=default_keyfunc)


@limiter.limit("1/second")
async def miniapp_handler(request: web.Request) -> web.Response:
    return await aiohttp_jinja2.render_template_async(
        "paint.html", request, context=None
    )


@limiter.limit("1/second")
async def update_handler(request: web.Request) -> web.Response:
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
async def word_handler(request: web.Request) -> web.Response:
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
        case GameWordStatus.NotAuth:
            return web.Response(text="not_auth", status=401)
        case GameWordStatus.NotHost:
            return web.Response(text="not_host", status=401)
        case GameWordStatus.Ended:
            return web.Response(text="ended", status=401)
        case _:
            return web.Response(text="error", status=401)


app = web.Application()
aiohttp_jinja2.setup(
    app,
    enable_async=True,
    loader=jinja2.FileSystemLoader(Path(__file__).parent.resolve() / "templates"),
)
app.add_routes(
    [
        web.get("", miniapp_handler),
        web.post("/update", update_handler),
        web.get("/word", word_handler),
        web.static(
            "/static", Path(__file__).parent.resolve() / "static", name="static"
        ),
    ]
)
app["static_root_url"] = "/web/app/static"
