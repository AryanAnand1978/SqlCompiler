from .ast_nodes import AndNode, ASTNode, Condition, ConditionNode, DistinctNode, FilterNode, JoinNode, LimitNode, OrNode, ProjectNode, ScanNode, SortNode, StringLiteral
from .tokens import Token, TokenType


class ParseError(ValueError):
    def __init__(self, message: str, token: Token):
        super().__init__(f"Parse error at position {token.position}: {message}; got {token.type.name} ({token.value!r})")
        self.token = token


_OPS = {TokenType.EQ: "=", TokenType.NEQ: "!=", TokenType.LT: "<", TokenType.GT: ">", TokenType.LTE: "<=", TokenType.GTE: ">="}


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.current = 0
        self.depth = 0
        self.trace: list[str] = []

    def _log(self, rule_name: str, depth: int | None = None) -> None:
        if depth is None:
            depth = self.depth
        token = self.peek()
        token_str = token.value if token.value else token.type.name
        self.trace.append("  " * depth + f"{rule_name}() @ token={token_str}")

    def parse(self) -> ASTNode:
        tree = self.parse_query()
        self.match(TokenType.SEMICOLON)
        self.expect(TokenType.EOF, "expected end of query")
        return tree

    def parse_with_trace(self) -> tuple[ASTNode, list[str]]:
        tree = self.parse()
        return tree, self.trace

    def parse_query(self) -> ASTNode:
        self._log("parse_query", depth=self.depth)
        self.depth += 1
        try:
            self.expect(TokenType.SELECT, "query must start with SELECT")
            is_distinct = bool(self.match(TokenType.DISTINCT))
            columns = self.parse_column_list()
            self.expect(TokenType.FROM, "expected FROM after select list")
            tree: ASTNode = self.parse_table_reference()
            while self.peek().type in (TokenType.JOIN, TokenType.INNER):
                if self.match(TokenType.INNER):
                    self.expect(TokenType.JOIN, "expected JOIN after INNER")
                else:
                    self.expect(TokenType.JOIN, "expected JOIN")
                right = self.parse_table_reference()
                self.expect(TokenType.ON, "expected ON after joined table")
                tree = JoinNode(tree, right, self.parse_condition())
            if self.match(TokenType.WHERE):
                tree = FilterNode(self.parse_where_clause(), tree)
            tree = ProjectNode(columns, tree)
            if is_distinct:
                tree = DistinctNode(tree)
            if self.match(TokenType.ORDER):
                column, direction = self.parse_order_clause()
                tree = SortNode(column, direction, tree)
            if self.match(TokenType.LIMIT):
                limit_tok = self.expect(TokenType.NUMBER, "expected number after LIMIT")
                offset = 0
                if self.match(TokenType.OFFSET):
                    offset_tok = self.expect(TokenType.NUMBER, "expected number after OFFSET")
                    offset = int(offset_tok.value)
                tree = LimitNode(int(limit_tok.value), offset, tree)
            return tree
        finally:
            self.depth -= 1

    def parse_where_clause(self) -> Condition:
        self._log("parse_where_clause", depth=self.depth)
        self.depth += 1
        try:
            return self.parse_condition()
        finally:
            self.depth -= 1

    def parse_order_clause(self) -> tuple[str, str]:
        self._log("parse_order_clause", depth=self.depth)
        self.depth += 1
        try:
            self.expect(TokenType.BY, "expected BY after ORDER")
            column = self.parse_name("expected ORDER BY column")
            direction = "ASC"
            if self.match(TokenType.ASC):
                direction = "ASC"
            elif self.match(TokenType.DESC):
                direction = "DESC"
            return column, direction
        finally:
            self.depth -= 1

    def parse_column_list(self) -> tuple[str, ...]:
        self._log("parse_column_list", depth=self.depth)
        self.depth += 1
        try:
            if self.match(TokenType.STAR):
                return ("*",)
            columns = [self.parse_name("expected column name")]
            while self.match(TokenType.COMMA):
                columns.append(self.parse_name("expected column name after comma"))
            return tuple(columns)
        finally:
            self.depth -= 1

    def parse_table_reference(self) -> ScanNode:
        self._log("parse_table_reference", depth=self.depth)
        self.depth += 1
        try:
            table = self.expect(TokenType.IDENTIFIER, "expected table name").value
            alias = self.advance().value if self.peek().type == TokenType.IDENTIFIER else None
            return ScanNode(table, alias=alias)
        finally:
            self.depth -= 1

    def parse_name(self, message: str) -> str:
        self._log("parse_name", depth=self.depth)
        self.depth += 1
        try:
            name = self.expect(TokenType.IDENTIFIER, message).value
            if self.match(TokenType.DOT):
                name += "." + self.expect(TokenType.IDENTIFIER, "expected name after dot").value
            return name
        finally:
            self.depth -= 1

    def parse_condition(self) -> Condition:
        self._log("parse_condition", depth=self.depth)
        self.depth += 1
        try:
            node = self.parse_comparison()
            while self.peek().type in (TokenType.AND, TokenType.OR):
                operator = self.advance().type
                right = self.parse_comparison()
                node = AndNode(node, right) if operator == TokenType.AND else OrNode(node, right)
            return node
        finally:
            self.depth -= 1

    def parse_comparison(self) -> Condition:
        self._log("parse_comparison", depth=self.depth)
        self.depth += 1
        try:
            left = self.parse_operand()
            if self.match(TokenType.BETWEEN):
                low = self.parse_operand()
                self.expect(TokenType.AND, "expected AND in BETWEEN clause")
                high = self.parse_operand()
                return AndNode(ConditionNode(left, ">=", low), ConditionNode(left, "<=", high))
            if self.match(TokenType.IN):
                self.expect(TokenType.LPAREN, "expected '(' after IN")
                items = [self.parse_operand()]
                while self.match(TokenType.COMMA):
                    items.append(self.parse_operand())
                self.expect(TokenType.RPAREN, "expected ')' after IN list")
                cond = ConditionNode(left, "=", items[0])
                for item in items[1:]:
                    cond = OrNode(cond, ConditionNode(left, "=", item))
                return cond
            op = self.advance()
            if op.type not in _OPS:
                raise ParseError("expected comparison operator", op)
            return ConditionNode(left, _OPS[op.type], self.parse_operand())
        finally:
            self.depth -= 1

    def parse_operand(self) -> str | int:
        self._log("parse_operand", depth=self.depth)
        self.depth += 1
        try:
            token = self.advance()
            if token.type == TokenType.IDENTIFIER:
                self.current -= 1
                return self.parse_name("expected identifier")
            if token.type == TokenType.NUMBER:
                return int(token.value)
            if token.type == TokenType.STRING:
                return StringLiteral(token.value)
            raise ParseError("expected identifier, number, or string literal", token)
        finally:
            self.depth -= 1

    def peek(self) -> Token:
        return self.tokens[self.current]

    def advance(self) -> Token:
        token = self.peek()
        if token.type != TokenType.EOF:
            self.current += 1
        return token

    def match(self, kind: TokenType) -> bool:
        if self.peek().type == kind:
            self.current += 1
            return True
        return False

    def expect(self, kind: TokenType, message: str) -> Token:
        if self.peek().type != kind:
            raise ParseError(message, self.peek())
        return self.advance()
