"""In-memory executor for the v1 logical AST."""

from .ast_nodes import AndNode, ASTNode, BooleanNode, ConditionNode, DistinctNode, FilterNode, JoinNode, LimitNode, OrNode, ProjectNode, ScanNode, SortNode, StringLiteral
from .sample_data.tables import TABLES


class ExecutionError(ValueError):
    """Raised when a syntactically valid query cannot run against the demo data."""


def _has_join(node: ASTNode) -> bool:
    if isinstance(node, JoinNode): return True
    if hasattr(node, "left") and _has_join(getattr(node, "left")): return True
    if hasattr(node, "right") and _has_join(getattr(node, "right")): return True
    if hasattr(node, "child") and _has_join(getattr(node, "child")): return True
    return False


def execute(ast: ASTNode, tables: dict[str, list[dict]] | None = None) -> list[dict]:
    tables = TABLES if tables is None else tables
    if isinstance(ast, ScanNode):
        try:
            rows = [dict(row) for row in tables[ast.table.lower()]]
            prefix = ast.alias or ast.table
            return [{f"{prefix}.{column}": value for column, value in row.items()} for row in rows]
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
            if rows and not _has_join(ast):
                return [{k.split(".", 1)[-1]: v for k, v in row.items()} for row in rows]
            return rows
        _validate_columns(ast.columns, rows)
        return [{column: _get_column_value(row, column) for column in ast.columns} for row in rows]
    if isinstance(ast, DistinctNode):
        rows = execute(ast.child, tables)
        seen = set()
        distinct_rows = []
        for row in rows:
            key = tuple(row.items())
            if key not in seen:
                seen.add(key)
                distinct_rows.append(row)
        return distinct_rows
    if isinstance(ast, SortNode):
        rows = execute(ast.child, tables)
        _validate_columns((ast.column,), rows)
        return sorted(rows, key=lambda row: _get_column_value(row, ast.column), reverse=ast.direction == "DESC")
    if isinstance(ast, LimitNode):
        rows = execute(ast.child, tables)
        start = ast.offset
        end = start + ast.limit
        return rows[start:end]
    raise TypeError(f"unsupported AST node: {type(ast).__name__}")


def _get_column_value(row: dict, column: str):
    if column in row:
        return row[column]
    if "." in column:
        prefix, col_name = column.split(".", 1)
        if col_name in row:
            return row[col_name]
        matches = [v for k, v in row.items() if k.endswith(f".{col_name}")]
        if len(matches) == 1:
            return matches[0]
    else:
        matches = [v for k, v in row.items() if k.endswith(f".{column}")]
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            raise ExecutionError(f"ambiguous column {column!r}")
    raise ExecutionError(f"unknown column {column!r}")


def _validate_columns(columns: tuple[str, ...], rows: list[dict]) -> None:
    if not rows:
        return
    sample = rows[0]
    for column in columns:
        _get_column_value(sample, column)


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
    return _get_column_value(row, operand)

