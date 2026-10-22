from dataclasses import fields, is_dataclass
from typing import Any


def print_tree(node, indent: int = 0) -> str:
    """Return a stable, indented representation of an AST or execution plan."""
    lines: list[str] = []

    def visit(current, depth: int) -> None:
        label = type(current).__name__
        children = getattr(current, "children", None)
        child = getattr(current, "child", None)
        values = []
        if is_dataclass(current):
            for field in fields(current):
                if field.name not in {"child", "children", "node_id"}:
                    values.append(f"{field.name}={getattr(current, field.name)!r}")
        lines.append("  " * depth + label + (f" ({', '.join(values)})" if values else ""))
        if child is not None:
            visit(child, depth + 1)
        if children:
            for nested in children:
                visit(nested, depth + 1)

    visit(node, indent)
    return "\n".join(lines)


def print_tree_highlighted(node, changed_node_id: Any = None, indent: int = 0) -> str:
    """Return an indented representation of an AST with changed node(s) wrapped in >>> ... <<<."""
    lines: list[str] = []
    if changed_node_id is None:
        target_ids: set[Any] = set()
    elif isinstance(changed_node_id, (set, list, tuple)):
        target_ids = set(changed_node_id)
    else:
        target_ids = {changed_node_id}

    def visit(current, depth: int) -> None:
        label = type(current).__name__
        children = getattr(current, "children", None)
        child = getattr(current, "child", None)
        values = []
        if is_dataclass(current):
            for field in fields(current):
                if field.name not in {"child", "children", "node_id"}:
                    values.append(f"{field.name}={getattr(current, field.name)!r}")
        line_content = label + (f" ({', '.join(values)})" if values else "")
        curr_id = getattr(current, "node_id", None)
        if curr_id is not None and curr_id in target_ids:
            lines.append("  " * depth + f">>> {line_content} <<<")
        else:
            lines.append("  " * depth + line_content)
        if child is not None:
            visit(child, depth + 1)
        if children:
            for nested in children:
                visit(nested, depth + 1)

    visit(node, indent)
    return "\n".join(lines)
