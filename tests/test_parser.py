import pytest

from sqlopt.ast_nodes import AndNode, ConditionNode, FilterNode, OrNode, ProjectNode, ScanNode, SortNode, StringLiteral
from sqlopt.lexer import Lexer
from sqlopt.parser import ParseError, Parser


def parse(sql):
    return Parser(Lexer(sql).tokenize()).parse()


def test_base_query_shape():
    tree = parse("SELECT * FROM users;")
    assert tree == ProjectNode(("*",), ScanNode("users"))


def test_filter_project_and_sort_have_canonical_nesting():
    tree = parse("SELECT id, name FROM orders WHERE status = 'shipped' ORDER BY id DESC;")
    assert tree == SortNode("id", "DESC", ProjectNode(("id", "name"), FilterNode(
        ConditionNode("status", "=", StringLiteral("shipped")), ScanNode("orders")
    )))


def test_and_or_conditions_are_parsed_left_to_right():
    tree = parse("SELECT name FROM users WHERE age > 18 AND active = 1 OR id = 2")
    condition = tree.child.condition
    assert isinstance(condition, OrNode)
    assert isinstance(condition.left, AndNode)


@pytest.mark.parametrize("sql", [
    "SELECT name FROM users WHERE age > 18",
    "SELECT name FROM users WHERE age > 18 AND 1=1",
    "SELECT name FROM users WHERE age > 18 AND age > 18",
])
def test_documented_filter_examples_parse(sql):
    assert isinstance(parse(sql), ProjectNode)


@pytest.mark.parametrize("sql", ["FROM users", "SELECT FROM users", "SELECT name users", "SELECT name FROM users junk extra"])
def test_invalid_syntax_raises_helpful_parse_error(sql):
    with pytest.raises(ParseError, match="position"):
        parse(sql)
