from dataclasses import replace
from ..ast_nodes import AndNode, ASTNode, BooleanNode, Condition, ConditionNode, DistinctNode, FilterNode, JoinNode, LimitNode, OrNode, ProjectNode, ScanNode, SortNode, StringLiteral


def _format_operand(val: str | int) -> str:
    if isinstance(val, StringLiteral):
        return f"'{val}'"
    return str(val)


def format_sql_condition(cond: Condition, parent_precedence: int = 0) -> str:
    """Format an AST Condition into a SQL WHERE expression preserving operator precedence."""
    if isinstance(cond, ConditionNode):
        return f"{_format_operand(cond.left)} {cond.op} {_format_operand(cond.right)}"
    if isinstance(cond, BooleanNode):
        return "1 = 1" if cond.value else "1 = 0"
    if isinstance(cond, AndNode):
        # AND has precedence 2; child OrNodes (precedence 1) require parentheses
        left_str = format_sql_condition(cond.left, parent_precedence=2)
        right_str = format_sql_condition(cond.right, parent_precedence=2)
        res = f"{left_str} AND {right_str}"
        return f"({res})" if parent_precedence > 2 else res
    if isinstance(cond, OrNode):
        # OR has precedence 1; wrapped in parentheses if inside AND (precedence 2)
        left_str = format_sql_condition(cond.left, parent_precedence=1)
        right_str = format_sql_condition(cond.right, parent_precedence=1)
        res = f"{left_str} OR {right_str}"
        return f"({res})" if parent_precedence > 1 else res
    return str(cond)


def _render_from(node: ASTNode) -> str:
    if isinstance(node, ScanNode):
        if node.alias:
            return f"{node.table} {node.alias}"
        return node.table
    if isinstance(node, JoinNode):
        left_str = _render_from(node.left)
        right_str = _render_from(node.right)
        cond_str = format_sql_condition(node.condition)
        join_kw = "JOIN" if node.join_type == "INNER" else f"{node.join_type} JOIN"
        return f"{left_str} {join_kw} {right_str} ON {cond_str}"
    return str(node)


def _extract_where_conditions(from_node: ASTNode) -> tuple[ASTNode, list[Condition]]:
    if isinstance(from_node, FilterNode):
        cleaned_child, conds = _extract_where_conditions(from_node.child)
        return cleaned_child, [from_node.condition] + conds
    if isinstance(from_node, JoinNode):
        cleaned_left, left_conds = _extract_where_conditions(from_node.left)
        cleaned_right, right_conds = _extract_where_conditions(from_node.right)
        new_join = replace(from_node, left=cleaned_left, right=cleaned_right)
        return new_join, left_conds + right_conds
    return from_node, []


def _unpack_query(node: ASTNode):
    limit = None
    offset = None
    order_by = None
    distinct = False
    columns = None
    where_cond = None
    curr = node

    if isinstance(curr, LimitNode):
        limit = curr.limit
        offset = curr.offset
        curr = curr.child

    if isinstance(curr, SortNode):
        order_by = (curr.column, curr.direction)
        curr = curr.child

    if isinstance(curr, DistinctNode):
        distinct = True
        curr = curr.child

    if isinstance(curr, ProjectNode):
        columns = curr.columns
        curr = curr.child

    if isinstance(curr, FilterNode):
        where_cond = curr.condition
        curr = curr.child

    from_node, extracted_conds = _extract_where_conditions(curr)
    all_conds = ([where_cond] if where_cond is not None else []) + extracted_conds
    if all_conds:
        combined = all_conds[0]
        for c in all_conds[1:]:
            combined = AndNode(combined, c)
        where_cond = combined

    return columns, from_node, where_cond, order_by, distinct, limit, offset


def ast_to_sql(node: ASTNode) -> str:
    """Render an ASTNode tree into a canonical SQL query string."""
    columns, from_node, where_cond, order_by, distinct, limit, offset = _unpack_query(node)

    parts: list[str] = []
    col_str = ", ".join(columns) if columns else "*"
    distinct_str = "DISTINCT " if distinct else ""
    parts.append(f"SELECT {distinct_str}{col_str}")

    if from_node is not None:
        parts.append(f"FROM {_render_from(from_node)}")

    if where_cond is not None:
        parts.append(f"WHERE {format_sql_condition(where_cond)}")

    if order_by is not None:
        parts.append(f"ORDER BY {order_by[0]} {order_by[1]}")

    if limit is not None:
        parts.append(f"LIMIT {limit}")
        if offset:
            parts.append(f"OFFSET {offset}")

    return " ".join(parts) + ";"
