from .tokens import Token, TokenType


class LexError(ValueError):
    """Raised when SQL source contains an unsupported character or literal."""

    def __init__(self, message: str, position: int):
        super().__init__(f"Lex error at position {position}: {message}")
        self.position = position


_KEYWORDS = {name: TokenType[name] for name in (
    "SELECT", "DISTINCT", "FROM", "WHERE", "AND", "OR", "ORDER", "BY", "ASC", "DESC", "JOIN", "INNER", "ON",
    "LIMIT", "OFFSET", "BETWEEN", "IN",
)}
_SINGLE = {
    ",": TokenType.COMMA, "*": TokenType.STAR, "=": TokenType.EQ,
    "<": TokenType.LT, ">": TokenType.GT, ";": TokenType.SEMICOLON, ".": TokenType.DOT,
    "(": TokenType.LPAREN, ")": TokenType.RPAREN,
}
_DOUBLE = {"!=": TokenType.NEQ, "<=": TokenType.LTE, ">=": TokenType.GTE}


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.position < len(self.source):
            char = self.source[self.position]
            if char.isspace():
                self.position += 1
            elif char.isalpha() or char == "_":
                tokens.append(self._identifier())
            elif char.isdigit():
                tokens.append(self._number())
            elif char in "'\"":
                tokens.append(self._string())
            elif self.source[self.position:self.position + 2] in _DOUBLE:
                value = self.source[self.position:self.position + 2]
                tokens.append(Token(_DOUBLE[value], value, self.position))
                self.position += 2
            elif char in _SINGLE:
                tokens.append(Token(_SINGLE[char], char, self.position))
                self.position += 1
            else:
                raise LexError(f"unexpected character {char!r}", self.position)
        tokens.append(Token(TokenType.EOF, "", self.position))
        return tokens

    def _identifier(self) -> Token:
        start = self.position
        while self.position < len(self.source) and (self.source[self.position].isalnum() or self.source[self.position] == "_"):
            self.position += 1
        value = self.source[start:self.position]
        return Token(_KEYWORDS.get(value.upper(), TokenType.IDENTIFIER), value, start)

    def _number(self) -> Token:
        start = self.position
        while self.position < len(self.source) and self.source[self.position].isdigit():
            self.position += 1
        return Token(TokenType.NUMBER, self.source[start:self.position], start)

    def _string(self) -> Token:
        start = self.position
        quote = self.source[self.position]
        self.position += 1
        value_start = self.position
        while self.position < len(self.source) and self.source[self.position] != quote:
            self.position += 1
        if self.position == len(self.source):
            raise LexError("unterminated string literal", start)
        value = self.source[value_start:self.position]
        self.position += 1
        return Token(TokenType.STRING, value, start)
