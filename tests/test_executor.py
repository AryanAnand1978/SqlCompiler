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


def test_executes_products_with_contradiction_and_disjunction():
    # Contradiction (1 = 0) returns 0 rows
    rows_empty = run("SELECT name, price FROM products WHERE price > 1000 AND 1 = 0;")
    assert rows_empty == []

    # Disjunction and projection
    rows = run("SELECT name, category FROM products WHERE category = 'Books' OR category = 'Furniture';")
    assert len(rows) == 5
    assert all(r["category"] in ("Books", "Furniture") for r in rows)


def test_executes_employees_and_departments_join():
    rows = run(
        "SELECT e.name, d.dept_name, e.salary FROM employees e "
        "JOIN departments d ON e.dept_id = d.id "
        "WHERE e.salary > 60000 AND 1 = 1 AND e.salary > 60000 "
        "ORDER BY e.salary DESC;"
    )
    assert len(rows) == 5
    assert rows[0]["e.name"] == "Karan"
    assert rows[0]["d.dept_name"] == "Engineering"
    assert rows[0]["e.salary"] == 92000


def test_executes_select_distinct():
    rows = run("SELECT DISTINCT city FROM users WHERE active = 1 AND active = 1;")
    cities = [r["city"] for r in rows]
    assert len(cities) == len(set(cities))
    assert set(cities) == {"Delhi", "Mumbai", "Pune", "Chennai", "Bengaluru"}


def test_executes_between_and_in_predicates():
    # BETWEEN: age >= 18 AND age <= 24 -> Aarav (24), Vivaan (19), Meera (22)
    rows_between = run("SELECT name, age FROM users WHERE age BETWEEN 18 AND 24 ORDER BY age ASC;")
    assert [r["name"] for r in rows_between] == ["Vivaan", "Meera", "Aarav"]

    # IN: category IN ('Books', 'Furniture')
    rows_in = run("SELECT name, category FROM products WHERE category IN ('Books', 'Furniture');")
    assert len(rows_in) == 5
    assert all(r["category"] in ("Books", "Furniture") for r in rows_in)


def test_executes_limit_and_offset():
    # LIMIT: top 3 highest paid employees
    rows_limit = run("SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 3;")
    assert len(rows_limit) == 3
    assert [r["name"] for r in rows_limit] == ["Karan", "Aditi", "Priya"]

    # LIMIT + OFFSET: skip 2, take 2
    rows_offset = run("SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 2 OFFSET 2;")
    assert len(rows_offset) == 2
    assert [r["name"] for r in rows_offset] == ["Priya", "Vikram"]


def test_executes_predicate_pushdown_through_join():
    rows = run("SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE u.age > 25 AND o.amount > 1000;")
    assert len(rows) == 2
    assert all(r["o.amount"] > 1000 for r in rows)


