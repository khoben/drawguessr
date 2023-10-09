import datetime
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, List, Optional, Sequence, Tuple

from psycopg import AsyncCursor, errors
from psycopg.rows import class_row
from psycopg_pool import AsyncConnectionPool

from common.retry import AsyncRetryProtocol
from database import Database, Game, User


class PsycopgDatabase(
    Database, metaclass=AsyncRetryProtocol, expects=errors.OperationalError
):
    MIN_CONN = 1
    MAX_CONN = 50

    def __init__(
        self,
        connection_string: str,
        min_conn: int = MIN_CONN,
        max_conn: int = MAX_CONN,
        **kwargs: Any
    ) -> "PsycopgDatabase":
        self.__conn_info = connection_string
        self.__min_conn = min_conn
        self.__max_conn = max_conn
        self.__kwargs = kwargs

    async def _async__init__(self: "PsycopgDatabase") -> "PsycopgDatabase":
        self.connection_pool = AsyncConnectionPool(
            conninfo=self.__conn_info,
            min_size=self.__min_conn,
            max_size=self.__max_conn,
            **self.__kwargs
        )
        await self.__create_db_if_not_exists()
        return self

    async def close(self: "PsycopgDatabase") -> None:
        await self.connection_pool.close()

    async def sql(
        self: "PsycopgDatabase", sql: str, params: Optional[Sequence[Any]] = None
    ) -> List[Any]:
        """Execute plain sql"""
        async with self.__pg_cursor() as cursor:
            await cursor.execute(sql, params)

            result: List[Any] = await cursor.fetchall()

        return result

    async def get_user_or_create(
        self: "PsycopgDatabase", user_id: int
    ) -> Tuple[User, bool]:
        """Get or create user"""
        user_created = False

        async with self.__pg_cursor() as cursor:
            cursor.row_factory = class_row(User)
            await cursor.execute(
                """
                SELECT users.id, users.telegram_id,
                users.banned, users.available_for_broadcast
                FROM users
                WHERE users.telegram_id = %s
                """,
                (user_id,),
            )
            user: Optional[User] = await cursor.fetchone()

            if not user:
                created_at = self.__current_timestamp()
                await cursor.execute(
                    """
                    INSERT INTO users (telegram_id, created_at) VALUES (%s, %s)
                    """,
                    (
                        user_id,
                        created_at,
                    ),
                )

                await cursor.execute(
                    """
                    SELECT users.id, users.telegram_id,
                    users.banned, users.available_for_broadcast
                    FROM users
                    WHERE users.telegram_id = %s
                    """,
                    (user_id,),
                )

                user: User = await cursor.fetchone()
                user_created = True

        return user, user_created

    async def get_users(self: "PsycopgDatabase") -> List[User]:
        """Get all users"""
        async with self.__pg_cursor() as cursor:
            cursor.row_factory = class_row(User)
            await cursor.execute(
                """
                SELECT users.id, users.telegram_id,
                users.banned, users.available_for_broadcast
                FROM users
                """
            )
            result: List[User] = await cursor.fetchall()

        return result

    async def create_game(
        self: "PsycopgDatabase",
        game_id: str,
        group_id: int,
        owner_id: int,
        owner_name: str,
        word: str,
    ) -> Game:
        """Create new game"""
        created_at = self.__current_timestamp()
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO games (game_id, group_id, owner_id, owner_name, word, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    game_id,
                    group_id,
                    owner_id,
                    owner_name,
                    word,
                    created_at,
                ),
            )
            internal_game_id: int = (await cursor.fetchone())[0]

        return Game(
            id=internal_game_id,
            game_id=game_id,
            group_id=group_id,
            message_id=0,  # Will be updated
            owner_id=owner_id,
            owner_name=owner_name,
            word=word,
            created_at=created_at,
            finished=False,
        )

    async def get_game(self: "PsycopgDatabase", game_id: str) -> Optional[Game]:
        """Get game"""
        game: Optional[Game] = None
        async with self.__pg_cursor() as cursor:
            cursor.row_factory = class_row(Game)
            await cursor.execute(
                """
                SELECT games.id, games.game_id,
                games.group_id, games.message_id,
                games.owner_id, games.owner_name,
                games.word, games.created_at, games.finished
                FROM games
                WHERE games.game_id = %s and games.finished IS NOT TRUE
                LIMIT 1
                """,
                (game_id,),
            )
            game = await cursor.fetchone()

        return game

    async def get_group_game(self: "PsycopgDatabase", group_id: str) -> Optional[Game]:
        """Get current group game"""
        game: Optional[Game] = None
        async with self.__pg_cursor() as cursor:
            cursor.row_factory = class_row(Game)
            await cursor.execute(
                """
                SELECT games.id, games.game_id,
                games.group_id, games.message_id,
                games.owner_id, games.owner_name,
                games.word, games.created_at, games.finished
                FROM games
                WHERE games.group_id = %s and games.finished IS NOT TRUE
                ORDER BY id DESC
                LIMIT 1
                """,
                (group_id,),
            )
            game = await cursor.fetchone()

        return game

    async def update_game_message(
        self: "PsycopgDatabase", game_id: int, new_message_id: int
    ) -> None:
        """Update game message id"""
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                UPDATE games
                SET message_id = %s
                WHERE id = %s
                """,
                (new_message_id, game_id),
            )

    async def game_finished(
        self: "PsycopgDatabase", game_id: int
    ) -> None:
        """Update finished game: delete"""
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                DELETE FROM games
                WHERE id = %s
                """,
                (game_id, ),
            )

    async def delete_games(
        self: "PsycopgDatabase", group_id: int
    ) -> None:
        """Delete all games in group"""
        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                DELETE FROM games
                WHERE group_id = %s
                """,
                (group_id, ),
            )

    async def __create_db_if_not_exists(self: "PsycopgDatabase"):
        """Create tables if not exists"""

        async with self.__pg_cursor() as cursor:
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users(   
                    id serial primary key not null,
                    telegram_id bigint not null unique,
                    created_at bigint not null,
                    banned boolean not null default false,
                    available_for_broadcast boolean not null default true
                );

                CREATE TABLE IF NOT EXISTS games(   
                    id serial primary key not null,
                    game_id varchar(128) not null,
                    group_id bigint not null,
                    message_id bigint not null default 0,
                    owner_id bigint not null,
                    owner_name varchar(128) not null,
                    word varchar(128) not null,
                    created_at bigint not null,
                    finished boolean not null default false
                );
                """
            )

    def __current_timestamp(self) -> int:
        """Returns current UTC timestamp, in sec"""
        return int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    @asynccontextmanager
    async def __pg_cursor(self: "PsycopgDatabase") -> AsyncIterator[AsyncCursor[Any]]:
        """
        Gets connection from pool and yields cursor within current context
        Yields:
            (`psycopg.AsyncCursor`): Cursor
        """
        async with self.connection_pool.connection() as con:
            try:
                async with con.cursor() as cur:
                    yield cur
            except errors.OperationalError as e:
                # If we get an operational error check the pool
                await self.connection_pool.check()
                raise e
            except errors.DatabaseError as e:
                if con is not None:
                    await con.rollback()
                raise e
