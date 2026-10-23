from ..ast_nodes import AndNode, ASTNode, BooleanNode, Condition, ConditionNode, DistinctNode, FilterNode, JoinNode, OrNode, ProjectNode, ScanNode, SortNode, StringLiteral


def _format_operand(val: str | int) -> str:
    if isinstance(val, StringLiteral):
        return f"'{val}'"
    return str(val)


def format_condition(cond: Condition) -> str:
    if isinstance(cond, ConditionNode):
        return f"{_format_operand(cond.left)} {cond.op} {_format_operand(cond.right)}"
    if isinstance(cond, BooleanNode):
        return "true" if cond.value else "false"
    if isinstance(cond, AndNode):
        return f"{format_condition(cond.left)} ∧ {format_condition(cond.right)}"
    if isinstance(cond, OrNode):
        return f"({format_condition(cond.left)} ∨ {format_condition(cond.right)})"
    return str(cond)


def to_relalg_string(node: ASTNode) -> str:
    """Recursively render an AST into formal relational algebra notation with Unicode symbols."""
    if isinstance(node, ScanNode):
        return f"{node.table} {node.alias}" if node.alias else node.table

    if isinstance(node, FilterNode):
        cond_str = format_condition(node.condition)
        return f"σ_{{{cond_str}}}({to_relalg_string(node.child)})"

    if isinstance(node, ProjectNode):
        cols_str = ", ".join(node.columns)
        return f"π_{{{cols_str}}}({to_relalg_string(node.child)})"

    if isinstance(node, SortNode):
        return f"τ_{{{node.column} {node.direction}}}({to_relalg_string(node.child)})"

    if isinstance(node, DistinctNode):
        return f"δ({to_relalg_string(node.child)})"

    if isinstance(node, JoinNode):
        cond_str = format_condition(node.condition)
        return f"({to_relalg_string(node.left)} ⋈_{{{cond_str}}} {to_relalg_string(node.right)})"

    return str(node)
