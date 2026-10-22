from sqlopt.ast_nodes import FilterNode, JoinNode, ProjectNode, ScanNode
from sqlopt.executor import execute
from sqlopt.lexer import Lexer
from sqlopt.optimizer.engine import optimize
from sqlopt.parser import Parser
from sqlopt.planner import generate_plan

QUERY = """SELECT u.name, o.amount
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.age > 18 AND o.status = 'shipped' AND 1 = 1 AND u.age > 18;"""


def test_aliased_join_parses_to_the_expected_logical_shape():
    ast = Parser(Lexer(QUERY).tokenize()).parse()
    assert isinstance(ast, ProjectNode)
    assert isinstance(ast.child, FilterNode)
    assert isinstance(ast.child.child, JoinNode)
    assert ast.child.child.left == ScanNode("users", alias="u")
    assert ast.child.child.right == ScanNode("orders", alias="o")


def test_aliased_join_optimizes_plans_and_executes():
    original = Parser(Lexer(QUERY).tokenize()).parse()
    optimized, rules = optimize(original)
    assert "constant_folding (1x)" in rules
    assert "redundant_filter_elimination (1x)" in rules
    plan = generate_plan(optimized)
    assert plan.children[0].children[0].operator == "NestedLoopJoin"
    assert execute(optimized) == [
        {"u.name": "Aarav", "o.amount": 1200},
        {"u.name": "Kabir", "o.amount": 2200},
        {"u.name": "Ananya", "o.amount": 980},
        {"u.name": "Isha", "o.amount": 430},
        {"u.name": "Arjun", "o.amount": 3100},
        {"u.name": "Sara", "o.amount": 540},
    ]
