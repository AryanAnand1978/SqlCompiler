import pytest

from sqlopt.executor import ExecutionError, execute
from sqlopt.lexer import Lexer
from sqlopt.optimizer.engine import optimize
from sqlopt.parser import Parser


def run(sql):
    ast = Parser(Lexer(sql).tokenize()).parse()
    return execute(optimize(ast)[0])


def test_executes_filter_project_and_sort_against_demo_tables():
    rows = run("SELECT name, age FROM users WHERE age > 18 ORDER BY age DESC;")
    assert rows[0] == {"name": "Isha", "age": 42}
    assert rows[-1] == {"name": "Vivaan", "age": 19}
    assert len(rows) == 8


def test_executes_string_comparisons_and_constant_folded_queries():
    rows = run("SELECT id FROM orders WHERE status = 'shipped' AND 1 = 1 ORDER BY id ASC;")
    assert [row["id"] for row in rows] == [101, 103, 105, 107, 108, 110]


def test_execution_reports_unknown_table_and_column():
    with pytest.raises(ExecutionError, match="unknown table"):
        run("SELECT * FROM missing")
    with pytest.raises(ExecutionError, match="unknown column"):
        run("SELECT nope FROM users")
