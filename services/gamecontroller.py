import asyncio
import re
import uuid
from enum import Enum
from typing import NamedTuple, Optional

from aiogram import Bot, types
from aiogram.utils.i18n import I18n
from aiogram.utils.web_app import WebAppInitData, safe_parse_webapp_init_data

from config import config
from database import Database, Game
from services.wordprovider import WordProvider


class GameWordStatus(str, Enum):
    Ok = 'ok'
    NotHost = 'not_host'
    Ended = 'ended'
    NotAuth = 'not_auth'


class GameWordResult(NamedTuple):
    word: Optional[str]
    status: GameWordStatus


class GameController:
    def __init__(
        self,
        bot: Bot,
        db: Database,
        i18n: I18n,
        word_provider: WordProvider,
        initial_canvas_file_id: str,
    ) -> None:
        """Draw&Guess game controller

        Args:
            bot (Bot): Bot instance
            db (Database): Database instance
            i18n (I18n): i18n localization instance
            word_provider (WordProvider): Word provider
            initial_canvas_file_id (str): Initial empty image `file_id`
        """
        self.__bot = bot
        self.__db = db
        self.__i18n = i18n
        self.__word_provider = word_provider
        self.__initial_canvas_file_id = initial_canvas_file_id
        self.__regex_cache: dict[str, re.Pattern] = {}
        self.__game_listeners: dict[str, set[asyncio.Queue]] = {}

    def extract_init_data(self, init_data: str) -> Optional[WebAppInitData]:
        """Extract Telegram Web App initData safe string

        Args:
            init_data (str): Telegram Web App initData safe string

        Returns:
            Optional[WebAppInitData]: WebAppInitData
        """
        try:
            return safe_parse_webapp_init_data(
                token=self.__bot.token, init_data=init_data
            )
        except ValueError:
            return None

    async def sub(self, init_data: str, game_id: str) -> Optional[asyncio.Queue]:
        """Subscribe to game events

        Args:
            init_data (str): Telegram Web App initData safe string
            game_id (str): Game id

        Returns:
            Optional[asyncio.Queue]: Event queue
        """
        if not self.extract_init_data(init_data=init_data):
            return None

        queue = asyncio.Queue()
        self.__game_listeners.setdefault(game_id, set()).add(queue)
        return queue

    async def unsub(self, game_id: str, queue: asyncio.Queue) -> None:
        """Unsub from game events

        Args:
            game_id (str): _description_
        """
        listeners = self.__game_listeners.get(game_id)
        if listeners:
            listeners.remove(queue)

    async def create_game(self, group_id: int, owner_id: int, owner_name: str) -> None:
        """Create new game

        Args:
            group_id (int): Requested group id for a game
            owner_id (int): Requested owner (user) id for a game
            owner_name (str): Requested owner (user) name for a game
        """
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
            photo=self.__initial_canvas_file_id,
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

    async def update_state(self, init_data: str, game_id: str, image) -> bool:
        """Update game state

        Args:
            init_data (str): Telegram Web App initData safe string
            game_id (str): Game id
            image (_type_): Updated canvas image

        Returns:
            bool: State has been updated
        """
        safe_init_data = self.extract_init_data(init_data=init_data)
        if not safe_init_data:
            return False

        game = await self.__db.get_game(game_id=game_id)
        if game is None:
            return False

        if game.owner_id != safe_init_data.user.id:
            return False

        media_image = types.BufferedInputFile(
            image.file.read(), filename=image.filename
        )
        try_resend = False
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
            try_resend = True

        if try_resend:
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
        """Check [text] for game word

        Args:
            group_id (int): Group id
            message_id (int): Message id
            user_id (int): User id
            text (str): Message text
        """
        game = await self.__db.get_group_game(group_id=group_id)
        if game is None:
            return

        if game.owner_id == user_id:
            return

        regex = self.__regex_cache.get(game.game_id)
        if not regex:
            regex = re.compile(game.word, re.IGNORECASE)
            self.__regex_cache[game.game_id] = regex

        if regex.match(text):
            await self.__game_finished(game=game)

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
        """Get current word for game with [game_id]

        Args:
            init_data (str): Telegram Web App initData safe string
            game_id (str): Game id

        Returns:
            GameWordResult: Game's word response
        """
        safe_init_data = self.extract_init_data(init_data=init_data)
        if not safe_init_data:
            return GameWordResult(None, GameWordStatus.NotAuth)

        game = await self.__db.get_game(game_id=game_id)
        if game is None:
            return GameWordResult(None, GameWordStatus.Ended)

        if game.owner_id != safe_init_data.user.id:
            return GameWordResult(None, GameWordStatus.NotHost)

        return GameWordResult(game.word, GameWordStatus.Ok)

    async def cancel_game(self, group_id: int, user_id: int, is_admin: bool) -> None:
        """Cancel current group game

        Args:
            group_id (int): Group id
            user_id (int): User id
            is_admin (bool): User is admin in group
        """
        game = await self.__db.get_group_game(group_id=group_id)
        if game is None:
            return

        if game.owner_id != user_id and not is_admin:
            return

        await self.__game_finished(game=game)

        _ = self.__i18n.gettext
        try:
            await self.__bot.send_message(
                chat_id=group_id,
                reply_to_message_id=game.message_id,
                text=_("The game is cancelled. Type /game to create new one"),
            )
        except Exception:
            pass

    async def delete_games(self, group_id: int) -> None:
        """Delete all game for group with [group_id]

        Args:
            group_id (int): Group id
        """
        await self.__db.delete_games(group_id=group_id)

    async def __game_finished(self, game: Game) -> None:
        await self.__db.game_finished(game_id=game.id)

        await asyncio.gather(
            *[
                listener.put(GameWordStatus.Ended)
                for listener in self.__game_listeners.get(game.game_id, set())
            ]
        )

        self.__game_listeners.pop(game.game_id, None)
        self.__regex_cache.pop(game.game_id, None)

    def __generate_game_id(self) -> str:
        return f"gameId__{uuid.uuid4()}"
