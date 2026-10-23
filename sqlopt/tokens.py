from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    SELECT = auto(); DISTINCT = auto(); FROM = auto(); WHERE = auto(); AND = auto(); OR = auto()
    ORDER = auto(); BY = auto(); ASC = auto(); DESC = auto(); JOIN = auto(); INNER = auto(); ON = auto()
    LIMIT = auto(); OFFSET = auto(); BETWEEN = auto(); IN = auto()
    IDENTIFIER = auto(); NUMBER = auto(); STRING = auto()
    COMMA = auto(); STAR = auto(); EQ = auto(); NEQ = auto(); LT = auto(); GT = auto()
    LTE = auto(); GTE = auto(); SEMICOLON = auto(); DOT = auto(); LPAREN = auto(); RPAREN = auto(); EOF = auto()


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    position: int
