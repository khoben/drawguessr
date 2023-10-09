from aiogram import F, Router, types
from aiogram.filters import CommandStart
from aiogram.utils.i18n import gettext as _

router = Router()


@router.message(CommandStart(), F.chat.type == "private")
async def command_start(message: types.Message):
    await message.answer(
        text=_("Hi, <b>{user}</b>! Add me to the group and we'll play a game.").format(
            user=message.from_user.first_name
        )
    )


@router.message(CommandStart(), F.chat.type.in_({"group", "supergroup"}))
async def command_start_group(message: types.Message):
    await message.answer(
        text=_("Hi, <b>{user}</b>! Send /game to create new game").format(
            user=message.from_user.first_name
        )
    )
