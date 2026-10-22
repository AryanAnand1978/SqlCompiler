import itertools
from dataclasses import dataclass, field
from typing import TypeAlias

_ID_COUNTER = itertools.count(1)


def next_node_id() -> int:
    return next(_ID_COUNTER)


@dataclass(frozen=True)
class ASTNode:
    """Base type for immutable logical-query tree nodes."""
    node_id: int = field(default_factory=next_node_id, compare=False, repr=False, kw_only=True)


class StringLiteral(str):
    """Marks a string literal so it remains distinct from an identifier."""


@dataclass(frozen=True)
class ConditionNode(ASTNode):
    left: str | int
    op: str
    right: str | int


@dataclass(frozen=True)
class BooleanNode(ASTNode):
    value: bool


@dataclass(frozen=True)
class AndNode(ASTNode):
    left: "Condition"
    right: "Condition"


@dataclass(frozen=True)
class OrNode(ASTNode):
    left: "Condition"
    right: "Condition"


Condition: TypeAlias = ConditionNode | BooleanNode | AndNode | OrNode


@dataclass(frozen=True)
class ScanNode(ASTNode):
    table: str
    required_columns: tuple[str, ...] | None = None
    alias: str | None = None


@dataclass(frozen=True)
class JoinNode(ASTNode):
    left: ASTNode
    right: ASTNode
    condition: Condition
    join_type: str = "INNER"


@dataclass(frozen=True)
class FilterNode(ASTNode):
    condition: Condition
    child: ASTNode


@dataclass(frozen=True)
class ProjectNode(ASTNode):
    columns: tuple[str, ...]
    child: ASTNode


@dataclass(frozen=True)
class SortNode(ASTNode):
    column: str
    direction: str
    child: ASTNode
