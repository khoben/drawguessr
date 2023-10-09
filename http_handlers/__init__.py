from aiohttp import web

from http_handlers.webapp import miniapp
from services.gamecontroller import GameController

app = web.Application()
app.add_subapp("/app", miniapp.app)


def provide_gamecontroller(controller: GameController) -> None:
    miniapp.app["controller"] = controller
