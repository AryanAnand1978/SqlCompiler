from collections import OrderedDict
from dataclasses import dataclass
from typing import Any
from ..ast_nodes import ASTNode
from ..utils.relalg_printer import to_relalg_string
from ..utils.sql_printer import ast_to_sql
from .rule_metadata import RULE_INFO
from .rules import constant_folding, predicate_pushdown, projection_pushdown, redundant_filter_elimination

_RULES = (constant_folding, predicate_pushdown, projection_pushdown, redundant_filter_elimination)


@dataclass
class OptimizationStep:
    rule_name: str
    before: ASTNode
    after: ASTNode
    identity: str = ""
    changed_node_id: Any = None
    iteration: int = 1
    before_sql: str = ""
    after_sql: str = ""
    before_ra: str = ""
    after_ra: str = ""


def optimize_steps(ast: ASTNode) -> list[OptimizationStep]:
    """Apply rewrite rules to a fixed point and record each transformation step."""
    tree = ast
    steps: list[OptimizationStep] = []
    for iteration in range(1, 21):
        changed = False
        for rule in _RULES:
            res = rule(tree)
            new_tree, applied = res[0], res[1]
            if applied:
                changed = True
                rule_name = rule.__name__
                meta = RULE_INFO.get(rule_name, {})
                identity = meta.get("identity", "")
                changed_id = getattr(res, "changed_node_id", None)
                steps.append(
                    OptimizationStep(
                        rule_name=rule_name,
                        before=tree,
                        after=new_tree,
                        identity=identity,
                        changed_node_id=changed_id,
                        iteration=iteration,
                        before_sql=ast_to_sql(tree),
                        after_sql=ast_to_sql(new_tree),
                        before_ra=to_relalg_string(tree),
                        after_ra=to_relalg_string(new_tree),
                    )
                )
                tree = new_tree
        if not changed:
            break
    return steps


def optimize(ast: ASTNode) -> tuple[ASTNode, list[str]]:
    """Apply rewrite rules to a fixed point and report each firing count in order.

    Backwards-compatible wrapper around optimize_steps().
    """
    steps = optimize_steps(ast)
    if not steps:
        return ast, []
    final_tree = steps[-1].after
    counts: OrderedDict[str, int] = OrderedDict()
    for step in steps:
        counts[step.rule_name] = counts.get(step.rule_name, 0) + 1
    return final_tree, [f"{name} ({count}x)" for name, count in counts.items()]
