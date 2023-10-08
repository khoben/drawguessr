from typing import Protocol, NamedTuple
import aiofiles
import random
from common.awaitable import aenumerate


class WordProvider(Protocol):
    async def generate(self, locale: str = "en") -> str:
        """Get word depends on locale"""
        raise NotImplementedError


class FileWord(NamedTuple):
    locale: str
    filepath: str
    lines: int


class FileWordProvider(WordProvider):
    def __init__(
        self, *files: FileWord, default_locale="en", default_word="word"
    ) -> None:
        self.__words = {file.locale: file for file in files}
        self.__default_config = self.__words.get(default_locale)
        self.__default_word = default_word

    async def generate(self, locale: str = "en") -> str:
        word_config = self.__words.get(locale, self.__default_config)
        word_idx = random.randint(0, word_config.lines)
        word = self.__default_word
        async with aiofiles.open(word_config.filepath, mode="r") as f:
            async for idx, line in aenumerate(f):
                if idx == word_idx:
                    word = line
                    break
        return word.strip()
