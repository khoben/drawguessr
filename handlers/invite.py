from aiogram import F, Router, types
from aiogram.filters import IS_MEMBER, IS_NOT_MEMBER, ChatMemberUpdatedFilter
from aiogram.utils.i18n import gettext as _

from services.gamecontroller import GameController

router = Router()


@router.my_chat_member(
    ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER),
    F.chat.type.in_({"group", "supergroup"}),
)
async def on_my_leave(event: types.ChatMemberUpdated, controller: GameController):
    group_id = event.chat.id
    await controller.delete_game(group_id=group_id)


@router.my_chat_member(
    ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER),
    F.chat.type.in_({"group", "supergroup"}),
)
async def on_my_join(event: types.ChatMemberUpdated):
    group_name = event.chat.full_name
    await event.answer(
        text=_("Hi, <b>{user}</b>! Send /game to create new game").format(
            user=group_name
        )
    )
