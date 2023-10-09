from aiogram import Bot, F, Router, types
from aiogram.filters import Command

from services.gamecontroller import GameController

router = Router()


@router.message(Command("game"), F.chat.type.in_({"group", "supergroup"}))
async def command_game(message: types.Message, controller: GameController):
    await controller.create_game(
        group_id=message.chat.id,
        owner_id=message.from_user.id,
        owner_name=message.from_user.full_name,
    )


@router.message(Command("cancel"), F.chat.type.in_({"group", "supergroup"}))
async def command_cancel(message: types.Message, controller: GameController, bot: Bot):
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    await controller.cancel_game(
        group_id=message.chat.id,
        user_id=message.from_user.id,
        is_admin=isinstance(
            member, (types.ChatMemberOwner, types.ChatMemberAdministrator)
        ),
    )


@router.message(F.text, F.chat.type.in_({"group", "supergroup"}))
async def word_proccessing(message: types.Message, controller: GameController):
    await controller.check_word(
        group_id=message.chat.id,
        message_id=message.message_id,
        user_id=message.from_user.id,
        text=message.text,
    )
