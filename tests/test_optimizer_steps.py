import pytest

from sqlopt.ast_nodes import AndNode, ConditionNode, FilterNode, ProjectNode, ScanNode
from sqlopt.lexer import Lexer
from sqlopt.optimizer.engine import optimize, optimize_steps
from sqlopt.optimizer.rule_metadata import RULE_INFO
from sqlopt.parser import Parser
from sqlopt.planner import estimate_cost
from sqlopt.utils.relalg_printer import to_relalg_string
from sqlopt.utils.tree_printer import print_tree_highlighted


def parse_query(sql: str):
    return Parser(Lexer(sql).tokenize()).parse()


SAMPLE_QUERIES = [
    "SELECT * FROM users;",
    "SELECT name, age FROM users WHERE age > 18 ORDER BY age DESC;",
    "SELECT name FROM users WHERE age > 18 AND 1=1;",
    "SELECT id, amount FROM orders WHERE status = 'shipped' ORDER BY id DESC;",
    "SELECT name FROM users WHERE age > 18 AND age > 18;",
    "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND 1 = 1;",
    "SELECT name, city FROM users WHERE active = 1 AND active = 1 AND age > 18 ORDER BY name ASC;",
    "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE u.age > 18 AND o.status = 'shipped' AND 1 = 1 AND u.age > 18;",
]


@pytest.mark.parametrize("sql", SAMPLE_QUERIES)
def test_optimize_steps_matches_optimize_final_tree(sql):
    ast = parse_query(sql)
    steps = optimize_steps(ast)
    opt_tree, rules = optimize(ast)

    if not steps:
        assert opt_tree == ast
        assert rules == []
    else:
        assert steps[-1].after == opt_tree
        # Verify step count matches sum of rule fires reported by optimize()
        total_fires = sum(int(r.split("(")[1].split("x")[0]) for r in rules)
        assert len(steps) == total_fires


def test_worked_example_1_step_sequence():
    sql = "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND 1 = 1;"
    ast = parse_query(sql)
    steps = optimize_steps(ast)

    assert len(steps) >= 2
    rule_names = [s.rule_name for s in steps]
    assert "constant_folding" in rule_names
    assert "redundant_filter_elimination" in rule_names
    assert "projection_pushdown" in rule_names

    # Check rule justifications and identities
    for step in steps:
        assert step.rule_name in RULE_INFO
        assert step.identity == RULE_INFO[step.rule_name]["identity"]
        assert step.before is not None
        assert step.after is not None


def test_worked_example_2_step_sequence():
    sql = "SELECT name, city FROM users WHERE active = 1 AND active = 1 AND age > 18 ORDER BY name ASC;"
    ast = parse_query(sql)
    steps = optimize_steps(ast)

    rule_names = [s.rule_name for s in steps]
    assert "redundant_filter_elimination" in rule_names
    assert "projection_pushdown" in rule_names

    # Final tree should have pushed down projection
    final_tree = steps[-1].after
    # Find scan node and check required columns
    scan = final_tree.child.child.child  # Sort -> Project -> Filter -> Scan
    assert scan.required_columns == ("active", "age", "city", "name")


def test_parse_trace_recording():
    parser = Parser(Lexer("SELECT name FROM users WHERE age > 18;").tokenize())
    ast, trace = parser.parse_with_trace()
    assert isinstance(ast, ProjectNode)
    assert len(trace) > 0
    assert any("parse_query" in line for line in trace)
    assert any("parse_where_clause" in line for line in trace)
    assert parser.trace == trace


def test_relalg_printer_unicode():
    sql = "SELECT name, age FROM users WHERE age > 18 ORDER BY name ASC;"
    ast = parse_query(sql)
    relalg = to_relalg_string(ast)
    assert "τ_{name ASC}" in relalg
    assert "π_{name, age}" in relalg
    assert "σ_{age > 18}" in relalg
    assert "users" in relalg


def test_estimate_cost_heuristics():
    scan = ScanNode("users")
    cost_scan = estimate_cost(scan, {"users": 100})
    assert cost_scan == 100

    cond = ConditionNode("age", ">", 18)
    flt = FilterNode(cond, scan)
    cost_flt = estimate_cost(flt, {"users": 100})
    assert cost_flt == 40  # 100 * 0.4 = 40

    proj = ProjectNode(("name",), flt)
    cost_proj = estimate_cost(proj, {"users": 100})
    assert cost_proj == 40  # Preserves rows


def test_tree_printer_highlighting():
    ast = parse_query("SELECT name FROM users WHERE age > 18;")
    # Highlight the FilterNode (ast.child)
    flt_id = ast.child.node_id
    highlighted = print_tree_highlighted(ast, flt_id)
    assert ">>> FilterNode" in highlighted
    assert ">>> ProjectNode" not in highlighted
