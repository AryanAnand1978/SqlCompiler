"""In-memory executor for the v1 logical AST."""

from .ast_nodes import AndNode, ASTNode, BooleanNode, ConditionNode, FilterNode, JoinNode, OrNode, ProjectNode, ScanNode, SortNode, StringLiteral
from .sample_data.tables import TABLES


class ExecutionError(ValueError):
    """Raised when a syntactically valid query cannot run against the demo data."""


def execute(ast: ASTNode, tables: dict[str, list[dict]] | None = None) -> list[dict]:
    tables = TABLES if tables is None else tables
    if isinstance(ast, ScanNode):
        try:
            rows = [dict(row) for row in tables[ast.table.lower()]]
            if ast.alias:
                return [{f"{ast.alias}.{column}": value for column, value in row.items()} for row in rows]
            return rows
        except KeyError as exc:
            raise ExecutionError(f"unknown table {ast.table!r}; available tables: {', '.join(sorted(tables))}") from exc
    if isinstance(ast, JoinNode):
        joined = []
        for left in execute(ast.left, tables):
            for right in execute(ast.right, tables):
                row = left | right
                if _evaluate(ast.condition, row): joined.append(row)
        return joined
    if isinstance(ast, FilterNode):
        return [row for row in execute(ast.child, tables) if _evaluate(ast.condition, row)]
    if isinstance(ast, ProjectNode):
        rows = execute(ast.child, tables)
        if ast.columns == ("*",):
            return rows
        _validate_columns(ast.columns, rows)
        return [{column: row[column] for column in ast.columns} for row in rows]
    if isinstance(ast, SortNode):
        rows = execute(ast.child, tables)
        _validate_columns((ast.column,), rows)
        return sorted(rows, key=lambda row: row[ast.column], reverse=ast.direction == "DESC")
    raise TypeError(f"unsupported AST node: {type(ast).__name__}")


def _validate_columns(columns: tuple[str, ...], rows: list[dict]) -> None:
    if not rows:
        return
    unavailable = [column for column in columns if column not in rows[0]]
    if unavailable:
        raise ExecutionError(f"unknown column(s): {', '.join(unavailable)}")


def _evaluate(condition, row: dict) -> bool:
    if isinstance(condition, BooleanNode): return condition.value
    if isinstance(condition, AndNode): return _evaluate(condition.left, row) and _evaluate(condition.right, row)
    if isinstance(condition, OrNode): return _evaluate(condition.left, row) or _evaluate(condition.right, row)
    if isinstance(condition, ConditionNode):
        left, right = _operand_value(condition.left, row), _operand_value(condition.right, row)
        return {"=": left == right, "!=": left != right, "<": left < right, ">": left > right, "<=": left <= right, ">=": left >= right}[condition.op]
    raise TypeError(f"unsupported condition: {type(condition).__name__}")


def _operand_value(operand: str | int, row: dict):
    if isinstance(operand, StringLiteral): return str(operand)
    if isinstance(operand, int): return operand
    try:
        return row[operand]
    except KeyError as exc:
        raise ExecutionError(f"unknown column {operand!r}") from exc
