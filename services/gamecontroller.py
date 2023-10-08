from aiogram import Bot, types
from aiogram.utils.web_app import safe_parse_webapp_init_data
from database import Database, Game
from config import config
from aiogram.utils.i18n import I18n
import uuid
from services.wordprovider import WordProvider
import re
from typing import Optional, NamedTuple
from enum import IntEnum


class GameWordStatus(IntEnum):
    Ok = 0
    NotHost = 1
    Ended = 2
    NotAuth = 3


class GameWordResult(NamedTuple):
    word: Optional[str]
    status: GameWordStatus


class GameController:
    def __init__(
        self, bot: Bot, db: Database, i18n: I18n, word_provider: WordProvider
    ) -> None:
        self.__bot = bot
        self.__db = db
        self.__i18n = i18n
        self.__word_provider = word_provider
        self.__regex_cache: dict[int, re.Pattern] = {}

    async def create_game(self, group_id: int, owner_id: int, owner_name: str) -> Game:
        already_running_game = await self.__db.get_group_game(group_id=group_id)
        if already_running_game:
            _ = self.__i18n.gettext
            try:
                await self.__bot.send_message(
                    chat_id=already_running_game.group_id,
                    reply_to_message_id=already_running_game.message_id,
                    text=_("The game has already started"),
                )
            except Exception:
                pass
            return

        word = await self.__word_provider.generate()
        self.__regex_cache[group_id] = re.compile(word, re.IGNORECASE)
        game = await self.__db.create_game(
            game_id=self.__generate_game_id(),
            group_id=group_id,
            owner_id=owner_id,
            owner_name=owner_name,
            word=word,
        )

        _ = self.__i18n.gettext

        game_message = await self.__bot.send_photo(
            chat_id=group_id,
            photo="AgACAgIAAxkBAAEPm_FlIjhc7y2OogMFZ_PAnSCCd6rmdwACJ9UxG1itEUkI7Wj41sWHigEAAwIAA20AAzAE",
            caption=_(
                "<a href='tg://user?id={owner_id}'>{owner_name}</a> draws for guessing"
            ).format(owner_id=owner_id, owner_name=owner_name),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=_("Start drawing"),
                            url=f"{config.telegram_bot_web_app_url}?startapp={game.game_id}",
                        )
                    ]
                ]
            ),
        )

        await self.__db.update_game_message(
            game_id=game.id, new_message_id=game_message.message_id
        )

        return game

    async def update_state(self, init_data: str, game_id: str, image) -> bool:
        try:
            safe_init_data = safe_parse_webapp_init_data(
                token=self.__bot.token, init_data=init_data
            )
        except ValueError:
            return False

        game = await self.__db.get_game(game_id=game_id)
        if game is None:
            return False

        if game.owner_id != safe_init_data.user.id:
            return False

        media_image = types.BufferedInputFile(
            image.file.read(), filename=image.filename
        )
        not_edited = False
        _ = self.__i18n.gettext
        try:
            await self.__bot.edit_message_media(
                media=types.InputMediaPhoto(
                    media=media_image,
                    caption=_(
                        "<a href='tg://user?id={owner_id}'>{owner_name}</a> draws for guessing"
                    ).format(owner_id=game.owner_id, owner_name=game.owner_name),
                ),
                chat_id=game.group_id,
                message_id=game.message_id,
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=_("Start drawing"),
                                url=f"{config.telegram_bot_web_app_url}?startapp={game.game_id}",
                            )
                        ]
                    ]
                ),
            )
        except Exception:
            not_edited = True

        if not_edited:
            try:
                new_message = await self.__bot.send_photo(
                    chat_id=game.group_id,
                    photo=media_image,
                    caption=_(
                        "<a href='tg://user?id={owner_id}'>{owner_name}</a> draws for guessing"
                    ).format(owner_id=game.owner_id, owner_name=game.owner_name),
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                types.InlineKeyboardButton(
                                    text=_("Start drawing"),
                                    url=f"{config.telegram_bot_web_app_url}?startapp={game.game_id}",
                                )
                            ]
                        ]
                    ),
                )
                await self.__db.update_game_message(
                    game_id=game.id, new_message_id=new_message.message_id
                )
            except Exception:
                return False

        return True

    async def check_word(
        self, group_id: int, message_id: int, user_id: int, text: str
    ) -> None:
        game = await self.__db.get_group_game(group_id=group_id)
        if game is None:
            return

        if game.owner_id == user_id:
            return

        regex = self.__regex_cache.get(group_id)
        if not regex:
            regex = re.compile(game.word, re.IGNORECASE)
            self.__regex_cache[group_id] = regex

        if regex.match(text):
            await self.__db.game_finished(game_id=game.id)
            del self.__regex_cache[group_id]

            _ = self.__i18n.gettext
            try:
                await self.__bot.send_message(
                    chat_id=group_id,
                    reply_to_message_id=message_id,
                    text=_(
                        "Correct! Word: <b>{word}</b>.\nType /game to start new game"
                    ).format(word=game.word),
                )
            except Exception:
                pass

    async def get_word(self, init_data: str, game_id: str) -> GameWordResult:
        try:
            safe_init_data = safe_parse_webapp_init_data(
                token=self.__bot.token, init_data=init_data
            )
        except ValueError:
            return GameWordResult(None, GameWordStatus.NotAuth)

        game = await self.__db.get_game(game_id=game_id)
        if game is None:
            return GameWordResult(None, GameWordStatus.Ended)

        if game.owner_id != safe_init_data.user.id:
            return GameWordResult(None, GameWordStatus.NotHost)

        return GameWordResult(game.word, GameWordStatus.Ok)

    async def delete_games(self, group_id: int) -> None:
        await self.__db.delete_games(group_id=group_id)

    def __generate_game_id(self) -> str:
        return f"gameId__{uuid.uuid4()}"
