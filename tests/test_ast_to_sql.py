import pytest

from sqlopt.ast_nodes import AndNode, ConditionNode, OrNode, StringLiteral
from sqlopt.lexer import Lexer
from sqlopt.optimizer.engine import optimize_steps
from sqlopt.optimizer.rule_metadata import RULE_INFO
from sqlopt.parser import Parser
from sqlopt.utils.relalg_printer import to_relalg_string
from sqlopt.utils.sql_printer import ast_to_sql, format_sql_condition


def parse_query(sql: str):
    return Parser(Lexer(sql).tokenize()).parse()


def test_basic_ast_to_sql():
    q = "SELECT * FROM users;"
    ast = parse_query(q)
    assert ast_to_sql(ast) == "SELECT * FROM users;"


def test_columns_and_order_ast_to_sql():
    q = "SELECT name, age FROM users ORDER BY age DESC;"
    ast = parse_query(q)
    assert ast_to_sql(ast) == "SELECT name, age FROM users ORDER BY age DESC;"


def test_aliased_join_ast_to_sql():
    q = "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE u.age > 18;"
    ast = parse_query(q)
    assert ast_to_sql(ast) == "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE u.age > 18;"


def test_condition_precedence_parentheses():
    # age > 18 AND (name = 'Aryan' OR name = 'Rahul')
    c_age = ConditionNode("age", ">", 18)
    c_aryan = ConditionNode("name", "=", StringLiteral("Aryan"))
    c_rahul = ConditionNode("name", "=", StringLiteral("Rahul"))
    or_node = OrNode(c_aryan, c_rahul)
    and_node = AndNode(c_age, or_node)

    rendered = format_sql_condition(and_node)
    assert rendered == "age > 18 AND (name = 'Aryan' OR name = 'Rahul')"

    # Left child is OR: (name = 'Aryan' OR name = 'Rahul') AND age > 18
    and_left = AndNode(or_node, c_age)
    assert format_sql_condition(and_left) == "(name = 'Aryan' OR name = 'Rahul') AND age > 18"


def test_optimization_snapshots_synchronized():
    q = "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND 1 = 1 AND name = name;"
    ast = parse_query(q)
    steps = optimize_steps(ast)

    for step in steps:
        assert step.before_sql == ast_to_sql(step.before)
        assert step.after_sql == ast_to_sql(step.after)
        assert step.before_ra == to_relalg_string(step.before)
        assert step.after_ra == to_relalg_string(step.after)


def test_prompt_example_query_step_by_step_sql():
    q = "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND 1 = 1 AND name = name;"
    ast = parse_query(q)
    initial_sql = ast_to_sql(ast)
    assert initial_sql == "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND 1 = 1 AND name = name;"

    steps = optimize_steps(ast)
    # Step 1: constant folding eliminates 1 = 1
    assert steps[0].rule_name == "constant_folding"
    assert steps[0].after_sql == "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND name = name;"

    # Step 2: projection pushdown updates scan node annotations
    assert steps[1].rule_name == "projection_pushdown"
    assert steps[1].after_sql == "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND name = name;"

    # Step 3: duplicate predicate elimination removes duplicate age > 18
    assert steps[2].rule_name == "redundant_filter_elimination"
    assert steps[2].after_sql == "SELECT name, age FROM users WHERE age > 18 AND name = name;"


def test_prompt_test_1_constant_folding():
    q = "SELECT name, age FROM users WHERE age > 18 AND 1 = 1;"
    ast = parse_query(q)
    steps = optimize_steps(ast)
    final_sql = ast_to_sql(steps[-1].after)
    assert final_sql == "SELECT name, age FROM users WHERE age > 18;"


def test_prompt_test_2_duplicate_predicate():
    q = "SELECT name, age FROM users WHERE age > 18 AND age > 18;"
    ast = parse_query(q)
    steps = optimize_steps(ast)
    final_sql = ast_to_sql(steps[-1].after)
    assert final_sql == "SELECT name, age FROM users WHERE age > 18;"


def test_prompt_test_3_multiple_rules():
    q = "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND 1 = 1 AND 2 = 2;"
    ast = parse_query(q)
    steps = optimize_steps(ast)
    final_sql = ast_to_sql(steps[-1].after)
    assert final_sql == "SELECT name, age FROM users WHERE age > 18;"


def test_prompt_test_4_no_optimization():
    q = "SELECT name, age FROM users WHERE age > 18;"
    ast = parse_query(q)
    steps = optimize_steps(ast)
    final_tree = steps[-1].after if steps else ast

    # Original SQL == Optimized SQL
    assert ast_to_sql(ast) == ast_to_sql(final_tree)
    # Original RA == Optimized RA
    assert to_relalg_string(ast) == to_relalg_string(final_tree)

    # For queries already in canonical form with *, no rule fires at all
    star_query = "SELECT * FROM users;"
    assert len(optimize_steps(parse_query(star_query))) == 0


def test_prompt_test_5_null_sensitive_condition():
    q = "SELECT name, age FROM users WHERE age > 18 AND name = name;"
    ast = parse_query(q)
    steps = optimize_steps(ast)
    final_sql = ast_to_sql(steps[-1].after if steps else ast)
    # Must preserve name = name
    assert "name = name" in final_sql


def test_feature_9_rule_metadata_correction():
    info = RULE_INFO["redundant_filter_elimination"]
    assert info["display_name"] == "Duplicate Predicate Elimination"
    assert info["identity"] == "c ∧ c = c"
