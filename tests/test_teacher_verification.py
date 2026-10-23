import pytest
from sqlopt.sample_data.tables import TABLES
from sqlopt.lexer import Lexer
from sqlopt.parser import Parser
from sqlopt.optimizer.engine import optimize_steps
from sqlopt.planner import generate_plan, estimate_cost
from sqlopt.executor import execute
from sqlopt.utils.sql_printer import ast_to_sql

# All 21 standard examples with their verified expected row counts and properties
STANDARD_EXAMPLES = [
    (
        "Join: Predicate Pushdown through Join",
        "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE u.age > 25 AND o.amount > 1000;",
        2,
        [{"u.name": "Kabir", "o.amount": 2200}, {"u.name": "Arjun", "o.amount": 3100}],
        ["predicate_pushdown"]
    ),
    (
        "Join: Redundant Self-Join Elimination (Join Pruning)",
        "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id JOIN users u2 ON u.id = u2.id WHERE o.status = 'shipped';",
        6,
        None,
        ["redundant_join_elimination"]
    ),
    (
        "Join: Employees & Departments (Filtered + Sorted)",
        "SELECT e.name, d.dept_name, e.salary FROM employees e JOIN departments d ON e.dept_id = d.id WHERE e.salary > 60000 ORDER BY e.salary DESC;",
        5,
        None,
        ["predicate_pushdown"]
    ),
    (
        "Join: All Rules Fired (Join + Tautology + Duplicates + Projection)",
        "SELECT e.name, d.dept_name, e.salary FROM employees e JOIN departments d ON e.dept_id = d.id WHERE e.salary > 50000 AND 1 = 1 AND e.salary > 50000 ORDER BY e.salary DESC;",
        7,
        None,
        ["constant_folding", "redundant_filter_elimination", "predicate_pushdown", "projection_pushdown"]
    ),
    (
        "Join: Users & Orders (Status filter + Tautology)",
        "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE u.age > 18 AND o.status = 'shipped' AND 1 = 1 AND u.age > 18;",
        6,
        None,
        ["constant_folding", "redundant_filter_elimination"]
    ),
    (
        "Edge Case: Syntactic Sugar (BETWEEN Predicate)",
        "SELECT name, age FROM users WHERE age BETWEEN 18 AND 30 ORDER BY age ASC;",
        5,
        [
            {"name": "Vivaan", "age": 19},
            {"name": "Meera", "age": 22},
            {"name": "Aarav", "age": 24},
            {"name": "Ananya", "age": 28},
            {"name": "Sara", "age": 29},
        ],
        []
    ),
    (
        "Edge Case: Syntactic Sugar (IN List Predicate)",
        "SELECT name, category, price FROM products WHERE category IN ('Books', 'Furniture') ORDER BY price ASC;",
        5,
        [
            {"name": "SQL Guide", "category": "Books", "price": 650},
            {"name": "Compilers Book", "category": "Books", "price": 1200},
            {"name": "Coffee Table", "category": "Furniture", "price": 4200},
            {"name": "Desk Chair", "category": "Furniture", "price": 8500},
            {"name": "Standing Desk", "category": "Furniture", "price": 18000},
        ],
        []
    ),
    (
        "Edge Case: Duplicate Elimination (SELECT DISTINCT)",
        "SELECT DISTINCT city FROM users WHERE active = 1 AND active = 1;",
        5,
        [{"city": "Delhi"}, {"city": "Mumbai"}, {"city": "Pune"}, {"city": "Chennai"}, {"city": "Bengaluru"}],
        ["redundant_filter_elimination"]
    ),
    (
        "Edge Case: Contradiction / Dead Predicate (1 = 0)",
        "SELECT name, price FROM products WHERE price > 1000 AND 1 = 0;",
        0,
        [],
        ["constant_folding"]
    ),
    (
        "Edge Case: Tautology Elimination (1 = 1)",
        "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND 1 = 1;",
        8,
        None,
        ["constant_folding", "redundant_filter_elimination"]
    ),
    (
        "Edge Case: Duplicate Filter Deduplication (c ∧ c = c)",
        "SELECT name, age FROM users WHERE age > 18 AND age > 18;",
        8,
        None,
        ["redundant_filter_elimination"]
    ),
    (
        "Edge Case: Self-Comparison (name = name)",
        "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND 1 = 1 AND name = name;",
        8,
        None,
        ["constant_folding", "redundant_filter_elimination"]
    ),
    (
        "Edge Case: Disjunction / OR Predicates",
        "SELECT name, category, price FROM products WHERE category = 'Books' OR category = 'Furniture' ORDER BY price ASC;",
        5,
        None,
        []
    ),
    (
        "Edge Case: Massive Projection Pushdown (1 of 5 columns)",
        "SELECT name FROM products;",
        10,
        None,
        ["projection_pushdown"]
    ),
    (
        "Edge Case: Wildcard (SELECT *) — Proves Pushdown is Safely Skipped",
        "SELECT * FROM products WHERE stock > 0;",
        8,
        None,
        []
    ),
    (
        "Edge Case: Filtered Column Not in SELECT List",
        "SELECT name FROM products WHERE price > 5000;",
        5,
        [{"name": "Laptop"}, {"name": "Smartphone"}, {"name": "Desk Chair"}, {"name": "Standing Desk"}, {"name": "Monitor"}],
        ["projection_pushdown"]
    ),
    (
        "Limit: Top 3 Highest Paid Employees",
        "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 3;",
        3,
        [{"name": "Karan", "salary": 92000}, {"name": "Aditi", "salary": 85000}, {"name": "Priya", "salary": 78000}],
        []
    ),
    (
        "Limit: Paged Results (LIMIT 2 OFFSET 2)",
        "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 2 OFFSET 2;",
        2,
        [{"name": "Priya", "salary": 78000}, {"name": "Vikram", "salary": 71000}],
        []
    ),
    (
        "Sort: Products by Price Descending",
        "SELECT name, category, price FROM products WHERE stock > 0 ORDER BY price DESC;",
        8,
        None,
        []
    ),
    (
        "Sort: Shipped Orders by Amount",
        "SELECT id, user_id, amount FROM orders WHERE status = 'shipped' ORDER BY amount DESC;",
        6,
        None,
        []
    ),
    (
        "Filter: Adult Active Users",
        "SELECT name, city, age FROM users WHERE active = 1 AND age >= 18 ORDER BY age ASC;",
        6,
        [
            {"name": "Vivaan", "city": "Pune", "age": 19},
            {"name": "Meera", "city": "Bengaluru", "age": 22},
            {"name": "Aarav", "city": "Delhi", "age": 24},
            {"name": "Ananya", "city": "Delhi", "age": 28},
            {"name": "Sara", "city": "Delhi", "age": 29},
            {"name": "Arjun", "city": "Chennai", "age": 35},
        ],
        []
    ),
]

TEACHER_CURVEBALLS = [
    ("Empty result query", "SELECT name FROM users WHERE age > 100;", 0),
    ("Filter on string equality", "SELECT name, city FROM users WHERE city = 'Delhi';", 3),
    ("BETWEEN combined with string equality", "SELECT name, salary FROM employees WHERE salary BETWEEN 60000 AND 90000 AND city = 'Bengaluru';", 2),
    ("IN with single element", "SELECT name FROM users WHERE city IN ('Mumbai');", 2),
    ("LIMIT without OFFSET", "SELECT name FROM users ORDER BY name ASC LIMIT 2;", 2),
    ("LIMIT greater than table size", "SELECT name FROM users LIMIT 50;", 10),
    ("OFFSET greater than table size", "SELECT name FROM users LIMIT 5 OFFSET 50;", 0),
    ("DISTINCT across two columns", "SELECT DISTINCT active, city FROM users;", 8),
    ("Negative comparison !=", "SELECT name, city FROM users WHERE city != 'Delhi';", 7),
    ("Comparison <= and >=", "SELECT name, age FROM users WHERE age >= 24 AND age <= 28;", 2),
    (
        "Three-way condition on join",
        "SELECT e.name, d.dept_name FROM employees e JOIN departments d ON e.dept_id = d.id WHERE e.salary > 50000 AND d.budget > 200000 AND e.city = 'Delhi';",
        2
    ),
    (
        "JOIN with table names instead of aliases",
        "SELECT users.name, orders.amount FROM users JOIN orders ON users.id = orders.user_id WHERE orders.amount > 2000;",
        2
    ),
]


@pytest.mark.parametrize("title, sql, expected_count, expected_rows, expected_rules", STANDARD_EXAMPLES)
def test_standard_example_execution(title, sql, expected_count, expected_rows, expected_rules):
    tokens = Lexer(sql).tokenize()
    ast_tree = Parser(tokens).parse()
    assert ast_tree is not None, f"Failed to parse: {sql}"

    steps = optimize_steps(ast_tree)
    final_ast = steps[-1].after if steps else ast_tree

    rules_fired = [s.rule_name for s in steps]
    for rule in expected_rules:
        assert rule in rules_fired, f"Expected rule '{rule}' to fire for query '{title}', but fired: {rules_fired}"

    # Plan generation & Costing should succeed without error
    plan = generate_plan(final_ast)
    cost = estimate_cost(plan)
    assert cost > 0

    # SQL generation should succeed
    sql_out = ast_to_sql(final_ast)
    assert sql_out.upper().startswith("SELECT")

    # Execution against catalog
    result = execute(final_ast, TABLES)
    assert len(result) == expected_count, f"Row count mismatch for '{title}'. Expected {expected_count}, got {len(result)}"

    if expected_rows is not None:
        assert result == expected_rows, f"Rows mismatch for '{title}'.\nExpected: {expected_rows}\nGot: {result}"


@pytest.mark.parametrize("title, sql, expected_count", TEACHER_CURVEBALLS)
def test_teacher_curveball_queries(title, sql, expected_count):
    tokens = Lexer(sql).tokenize()
    ast_tree = Parser(tokens).parse()
    assert ast_tree is not None

    steps = optimize_steps(ast_tree)
    final_ast = steps[-1].after if steps else ast_tree

    plan = generate_plan(final_ast)
    assert plan is not None

    result = execute(final_ast, TABLES)
    assert len(result) == expected_count, f"Expected {expected_count} rows for '{title}', got {len(result)}"
