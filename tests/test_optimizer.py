from sqlopt.ast_nodes import AndNode, BooleanNode, ConditionNode, FilterNode, ProjectNode, ScanNode
from sqlopt.optimizer.engine import optimize
from sqlopt.optimizer.rules import constant_folding, redundant_filter_elimination


def test_constant_true_removes_filter():
    original = FilterNode(ConditionNode(1, "=", 1), ScanNode("users"))
    rewritten, applied = constant_folding(original)
    assert applied is True
    assert rewritten == ScanNode("users")


def test_constant_false_remains_explicit():
    rewritten, applied = constant_folding(FilterNode(ConditionNode(1, "=", 2), ScanNode("users")))
    assert applied is True
    assert rewritten == FilterNode(BooleanNode(False), ScanNode("users"))


def test_duplicate_and_predicate_is_removed():
    age = ConditionNode("age", ">", 18)
    rewritten, applied = redundant_filter_elimination(FilterNode(AndNode(age, age), ScanNode("users")))
    assert applied is True
    assert rewritten == FilterNode(age, ScanNode("users"))


def test_optimizer_reports_rules_and_marks_required_scan_columns():
    age = ConditionNode("age", ">", 18)
    original = ProjectNode(("name",), FilterNode(AndNode(age, age), ScanNode("users")))
    optimized, applied = optimize(original)
    assert applied == ["projection_pushdown (1x)", "redundant_filter_elimination (1x)"]
    assert optimized == ProjectNode(("name",), FilterNode(age, ScanNode("users", ("age", "name"))))
