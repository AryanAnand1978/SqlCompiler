from dataclasses import dataclass
from math import log2
from .ast_nodes import ASTNode, DistinctNode, FilterNode, JoinNode, LimitNode, ProjectNode, ScanNode, SortNode
from .sample_data.tables import TABLE_ROW_COUNTS, TABLES

TABLE_COLUMN_COUNTS = {name: len(rows[0]) for name, rows in TABLES.items()}
SELECTIVITY_HEURISTIC = 0.4


@dataclass(frozen=True)
class PlanNode:
    operator: str
    estimated_rows: float
    estimated_cost: float
    details: tuple[tuple[str, str], ...] = ()
    children: tuple["PlanNode", ...] = ()


def generate_plan(ast: ASTNode) -> PlanNode:
    if isinstance(ast, ScanNode):
        rows = float(TABLE_ROW_COUNTS.get(ast.table.lower(), 1000))
        total_columns = TABLE_COLUMN_COUNTS.get(ast.table.lower(), 8)
        read_columns = total_columns if ast.required_columns is None else len(ast.required_columns)
        details = [("table", ast.table)]
        if ast.alias: details.append(("alias", ast.alias))
        details.append(("columns_read", str(read_columns)))
        if ast.required_columns is not None: details.append(("columns", ", ".join(ast.required_columns)))
        # A scan's work scales with the number of rows * columns read.  This
        # makes projection pushdown visible in the interactive cost comparison.
        return PlanNode("SeqScan", rows, rows * read_columns, tuple(details))
    if isinstance(ast, JoinNode):
        left, right = generate_plan(ast.left), generate_plan(ast.right)
        rows = max(1.0, left.estimated_rows * right.estimated_rows * 0.1)
        cost = left.estimated_cost + right.estimated_cost + left.estimated_rows * right.estimated_rows
        return PlanNode("NestedLoopJoin", rows, cost, (("condition", repr(ast.condition)),), (left, right))
    if isinstance(ast, FilterNode):
        child = generate_plan(ast.child); rows = max(1.0, child.estimated_rows * 0.3)
        return PlanNode("Filter", rows, child.estimated_cost + child.estimated_rows * 0.1, (("condition", repr(ast.condition)),), (child,))
    if isinstance(ast, ProjectNode):
        child = generate_plan(ast.child)
        return PlanNode("Project", child.estimated_rows, child.estimated_cost + child.estimated_rows * 0.05, (("columns", ", ".join(ast.columns)),), (child,))
    if isinstance(ast, SortNode):
        child = generate_plan(ast.child); extra = child.estimated_rows * log2(max(2.0, child.estimated_rows))
        return PlanNode("Sort", child.estimated_rows, child.estimated_cost + extra, (("column", ast.column), ("direction", ast.direction)), (child,))
    if isinstance(ast, DistinctNode):
        child = generate_plan(ast.child)
        rows = max(1.0, child.estimated_rows * 0.7)
        return PlanNode("Distinct", rows, child.estimated_cost + child.estimated_rows * 0.1, (), (child,))
    if isinstance(ast, LimitNode):
        child = generate_plan(ast.child)
        rows = min(child.estimated_rows, float(ast.limit))
        details = [("limit", str(ast.limit))]
        if ast.offset: details.append(("offset", str(ast.offset)))
        return PlanNode("Limit", rows, child.estimated_cost + rows * 0.01, tuple(details), (child,))
    raise TypeError(f"unsupported AST node: {type(ast).__name__}")


def estimate_cost(node: ASTNode, table_row_counts: dict[str, int] | None = None) -> int:
    """Recursively estimate output row count for an AST node using educational heuristics.

    - ScanNode: table_row_counts[table] (defaults to TABLE_ROW_COUNTS or 1000).
    - FilterNode: estimate_cost(child) * SELECTIVITY_HEURISTIC (0.4).
    - ProjectNode / SortNode: preserves child row count.
    - JoinNode: multiplies inputs by 0.1 join selectivity.
    """
    if table_row_counts is None:
        table_row_counts = TABLE_ROW_COUNTS

    if isinstance(node, ScanNode):
        return int(table_row_counts.get(node.table.lower(), 1000))
    if isinstance(node, FilterNode):
        child_rows = estimate_cost(node.child, table_row_counts)
        return max(1, int(round(child_rows * SELECTIVITY_HEURISTIC)))
    if isinstance(node, (ProjectNode, SortNode)):
        return estimate_cost(node.child, table_row_counts)
    if isinstance(node, DistinctNode):
        child_rows = estimate_cost(node.child, table_row_counts)
        return max(1, int(round(child_rows * 0.7)))
    if isinstance(node, LimitNode):
        return min(estimate_cost(node.child, table_row_counts), node.limit)
    if isinstance(node, JoinNode):
        left_rows = estimate_cost(node.left, table_row_counts)
        right_rows = estimate_cost(node.right, table_row_counts)
        return max(1, int(round(left_rows * right_rows * 0.1)))
    return 1000
