from sqlopt.ast_nodes import ConditionNode, FilterNode, ProjectNode, ScanNode, SortNode
from sqlopt.optimizer.engine import optimize
from sqlopt.planner import generate_plan


def test_scan_uses_known_table_rows_and_projection_metadata():
    plan = generate_plan(ScanNode("users", ("age", "name")))
    assert plan.operator == "SeqScan"
    assert plan.estimated_rows == 10.0
    assert plan.estimated_cost == 20.0
    assert dict(plan.details)["columns"] == "age, name"


def test_filter_projection_and_sort_have_deterministic_costs():
    ast = SortNode("name", "ASC", ProjectNode(("name",), FilterNode(ConditionNode("age", ">", 18), ScanNode("users"))))
    plan = generate_plan(ast)
    assert plan.operator == "Sort"
    assert plan.estimated_rows == 3.0
    assert plan.children[0].operator == "Project"
    assert plan.children[0].children[0].operator == "Filter"
    assert plan.estimated_cost > plan.children[0].estimated_cost > 50.0


def test_unknown_table_gets_default_estimate():
    assert generate_plan(ScanNode("events")).estimated_rows == 1000.0


def test_projection_pushdown_reduces_the_estimated_scan_cost():
    original = ProjectNode(("name",), FilterNode(ConditionNode("age", ">", 18), ScanNode("users")))
    optimized, _ = optimize(original)
    assert generate_plan(optimized).estimated_cost < generate_plan(original).estimated_cost
