from dataclasses import replace
from typing import Any
from ..ast_nodes import AndNode, ASTNode, BooleanNode, Condition, ConditionNode, FilterNode, JoinNode, OrNode, ProjectNode, ScanNode, SortNode, StringLiteral


class RuleResult(tuple):
    """2-tuple (rewritten_ast, was_applied) carrying metadata like changed_node_id."""

    def __new__(cls, rewritten: ASTNode, applied: bool, changed_node_id: Any = None):
        inst = super().__new__(cls, (rewritten, applied))
        inst.rewritten = rewritten
        inst.applied = applied
        inst.changed_node_id = changed_node_id
        return inst


def _comparison_value(node: ConditionNode) -> bool | None:
    if not ((isinstance(node.left, int) and isinstance(node.right, int)) or (isinstance(node.left, StringLiteral) and isinstance(node.right, StringLiteral))):
        return None
    return {"=": node.left == node.right, "!=": node.left != node.right, "<": node.left < node.right, ">": node.left > node.right, "<=": node.left <= node.right, ">=": node.left >= node.right}[node.op]


def _fold_condition(node: Condition) -> Condition:
    if isinstance(node, ConditionNode):
        value = _comparison_value(node)
        return BooleanNode(value) if value is not None else node
    if isinstance(node, (AndNode, OrNode)):
        left, right = _fold_condition(node.left), _fold_condition(node.right)
        if isinstance(left, BooleanNode) and isinstance(right, BooleanNode):
            return BooleanNode(left.value and right.value if isinstance(node, AndNode) else left.value or right.value)
        if isinstance(node, AndNode):
            if isinstance(left, BooleanNode): return right if left.value else left
            if isinstance(right, BooleanNode): return left if right.value else right
        else:
            if isinstance(left, BooleanNode): return left if left.value else right
            if isinstance(right, BooleanNode): return right if right.value else left
        return type(node)(left, right)
    return node


def _rewrite_children(node: ASTNode, transform):
    if isinstance(node, FilterNode): return replace(node, child=transform(node.child))
    if isinstance(node, ProjectNode): return replace(node, child=transform(node.child))
    if isinstance(node, SortNode): return replace(node, child=transform(node.child))
    if isinstance(node, JoinNode): return replace(node, left=transform(node.left), right=transform(node.right))
    return node


def constant_folding(node: ASTNode) -> RuleResult:
    changed_id = None

    def _transform(child):
        nonlocal changed_id
        res = constant_folding(child)
        if res[1] and res.changed_node_id is not None:
            changed_id = res.changed_node_id
        return res[0]

    rewritten = _rewrite_children(node, _transform)
    if isinstance(rewritten, FilterNode):
        condition = _fold_condition(rewritten.condition)
        if isinstance(condition, BooleanNode) and condition.value:
            return RuleResult(rewritten.child, True, (rewritten.node_id, getattr(rewritten.child, "node_id", None)))
        if condition != rewritten.condition:
            rewritten = replace(rewritten, condition=condition)
            changed_id = rewritten.node_id
    applied = rewritten != node
    if applied and changed_id is None:
        changed_id = getattr(rewritten, "node_id", None)
    return RuleResult(rewritten, applied, changed_id)


def redundant_filter_elimination(node: ASTNode) -> RuleResult:
    changed_id = None

    def _transform(child):
        nonlocal changed_id
        res = redundant_filter_elimination(child)
        if res[1] and res.changed_node_id is not None:
            changed_id = res.changed_node_id
        return res[0]

    rewritten = _rewrite_children(node, _transform)
    if isinstance(rewritten, FilterNode):
        condition = _deduplicate(rewritten.condition)
        if condition != rewritten.condition:
            rewritten = replace(rewritten, condition=condition)
            changed_id = rewritten.node_id
    applied = rewritten != node
    if applied and changed_id is None:
        changed_id = getattr(rewritten, "node_id", None)
    return RuleResult(rewritten, applied, changed_id)


def _deduplicate(condition: Condition) -> Condition:
    if isinstance(condition, AndNode):
        predicates = _and_predicates(condition)
        unique: list[Condition] = []
        for predicate in predicates:
            if predicate not in unique: unique.append(predicate)
        result = unique[0]
        for predicate in unique[1:]: result = AndNode(result, predicate)
        return result
    if isinstance(condition, OrNode): return OrNode(_deduplicate(condition.left), _deduplicate(condition.right))
    return condition


def _and_predicates(condition: Condition) -> list[Condition]:
    if isinstance(condition, AndNode):
        return _and_predicates(condition.left) + _and_predicates(condition.right)
    return [_deduplicate(condition)]


def predicate_pushdown(node: ASTNode) -> RuleResult:
    """No-op in v1: with only scans, filters are already at the lowest valid point."""
    return RuleResult(node, False, None)


def _condition_columns(condition: Condition) -> set[str]:
    if isinstance(condition, ConditionNode):
        return {value for value in (condition.left, condition.right) if isinstance(value, str) and not isinstance(value, StringLiteral)}
    if isinstance(condition, (AndNode, OrNode)): return _condition_columns(condition.left) | _condition_columns(condition.right)
    return set()


def projection_pushdown(node: ASTNode) -> RuleResult:
    project = _find_project(node)
    if project is None or project.columns == ("*",): return RuleResult(node, False, None)
    required = set(project.columns)
    _collect_required(node, required)
    annotated, changed_id = _annotate_scan(node, tuple(sorted(required)))
    applied = annotated != node
    return RuleResult(annotated, applied, changed_id)


def _find_project(node: ASTNode) -> ProjectNode | None:
    if isinstance(node, ProjectNode): return node
    if isinstance(node, (FilterNode, SortNode)): return _find_project(node.child)
    if isinstance(node, JoinNode): return _find_project(node.left) or _find_project(node.right)
    return None


def _collect_required(node: ASTNode, required: set[str]) -> None:
    if isinstance(node, FilterNode):
        required.update(_condition_columns(node.condition)); _collect_required(node.child, required)
    elif isinstance(node, SortNode):
        required.add(node.column); _collect_required(node.child, required)
    elif isinstance(node, ProjectNode): _collect_required(node.child, required)
    elif isinstance(node, JoinNode):
        required.update(_condition_columns(node.condition)); _collect_required(node.left, required); _collect_required(node.right, required)


def _annotate_scan(node: ASTNode, columns: tuple[str, ...]) -> tuple[ASTNode, Any]:
    if isinstance(node, ScanNode):
        if node.alias:
            prefix = node.alias + "."
            relevant = tuple(sorted(column[len(prefix):] for column in columns if column.startswith(prefix)))
            res = replace(node, required_columns=relevant or None)
            return res, res.node_id
        relevant = tuple(column for column in columns if "." not in column)
        res = replace(node, required_columns=relevant or None)
        return res, res.node_id
    changed_id = None

    def _transform(child):
        nonlocal changed_id
        c, cid = _annotate_scan(child, columns)
        if cid is not None:
            changed_id = cid
        return c

    return _rewrite_children(node, _transform), changed_id
