import random
from typing import NamedTuple, Protocol

import aiofiles

from common.awaitable import aenumerate


class WordProvider(Protocol):
    async def generate(self, locale: str = "en") -> str:
        """Generate word depends on [locale]

        Args:
            locale (str, optional): Locale language code. Defaults to "en".

        Returns:
            str: Generated word
        """
        raise NotImplementedError


class FileWords(NamedTuple):
    locale: str
    filepath: str
    lines: int


class FileWordProvider(WordProvider):
    def __init__(
        self, *files: FileWords, default_locale="en", default_word="word"
    ) -> None:
        """Word provider from local files

        Args:
            files (*FileWords): Words local files configs.
            default_locale (str, optional): Default language code. Defaults to "en".
            default_word (str, optional): Default word. Defaults to "word".
        """
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
