from enum import Enum


class StrEnum(str, Enum):
    def __str__(self):
        return str(self.value)
