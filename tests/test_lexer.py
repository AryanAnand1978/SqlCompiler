import pytest

from sqlopt.lexer import LexError, Lexer
from sqlopt.tokens import TokenType


def types(sql):
    return [token.type for token in Lexer(sql).tokenize()]


def test_lexes_case_insensitive_keywords_and_punctuation():
    assert types("select name, * from users;") == [
        TokenType.SELECT, TokenType.IDENTIFIER, TokenType.COMMA, TokenType.STAR,
        TokenType.FROM, TokenType.IDENTIFIER, TokenType.SEMICOLON, TokenType.EOF,
    ]


def test_lexes_literals_and_all_comparison_operators():
    tokens = Lexer("WHERE a=1 AND b!=2 OR c<3 AND d>4 AND e<=5 AND f>=6 AND x='hi'").tokenize()
    assert [token.type for token in tokens if token.type in {TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE}] == [
        TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE, TokenType.EQ
    ]
    assert tokens[-2].value == "hi"


def test_invalid_and_unterminated_input_has_position():
    with pytest.raises(LexError, match="position 7"):
        Lexer("SELECT @").tokenize()
    with pytest.raises(LexError, match="unterminated"):
        Lexer("SELECT 'x").tokenize()
