from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol, Sequence, Tuple


@dataclass
class User:
    id: int
    telegram_id: int
    banned: bool
    available_for_broadcast: bool


@dataclass
class Game:
    id: int
    game_id: str
    group_id: int
    message_id: int
    owner_id: int
    owner_name: str
    word: str
    created_at: int
    finished: bool


class Database(Protocol):
    @abstractmethod
    async def _async__init__(self: "Database") -> "Database":
        """Async initializer"""
        raise NotImplementedError

    def __await__(self):
        return self._async__init__().__await__()

    async def open(self: "Database") -> None:
        """Create connection pool"""
        await self

    @abstractmethod
    async def close(self: "Database") -> None:
        """Close connection pool"""
        raise NotImplementedError

    @abstractmethod
    async def sql(
        self: "Database", sql: str, params: Optional[Sequence[Any]] = None
    ) -> Any:
        """Execute plain sql"""
        raise NotImplementedError

    @abstractmethod
    async def get_user_or_create(self: "Database", user_id: int) -> Tuple[User, bool]:
        """Get or create user"""
        raise NotImplementedError

    async def get_users(self: "Database") -> List[User]:
        """Get all users"""
        raise NotImplementedError

    async def create_game(
        self: "Database",
        game_id: str,
        group_id: int,
        owner_id: int,
        owner_name: str,
        word: str,
    ) -> Game:
        """Create new game"""
        raise NotImplementedError

    async def get_game(self: "Database", game_id: str) -> Optional[Game]:
        """Get game"""
        raise NotImplementedError

    async def get_group_game(self: "Database", group_id: str) -> Optional[Game]:
        """Get current group game"""
        raise NotImplementedError

    async def update_game_message(
        self: "Database", game_id: int, new_message_id: int
    ) -> None:
        """Update game message id"""
        raise NotImplementedError

    async def game_finished(
        self: "Database", game_id: int
    ) -> None:
        """Update finished game: delete"""
        raise NotImplementedError

    async def delete_games(
        self: "Database", group_id: int
    ) -> None:
        """Delete all games in group"""
        raise NotImplementedError
