from aiohttp import web
from services.gamecontroller import GameController
from http_handlers.webapp import miniapp

app = web.Application()
app.add_subapp("/app", miniapp.app)


def provide_gamecontroller(controller: GameController) -> None:
    miniapp.app["controller"] = controller
