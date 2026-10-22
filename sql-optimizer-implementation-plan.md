# Implementation Plan: SQL Query Compiler and Optimizer

**Project Title:** SQL Query Compiler and Optimizer: A Rule-Based Query Processing Engine with AST-Driven Optimization

**Stack:** Python 3.10+, Streamlit (UI)

**Goal:** Build a mini SQL engine that parses a SQL query into an AST, applies rule-based optimizations to the AST, generates an execution plan, and visually shows the before/after transformation in a Streamlit web app.

---

## 1. Project Structure

```
sqlopt/
├── app.py                # Streamlit UI entrypoint
├── lexer.py               # Tokenizer
├── tokens.py               # Token type definitions
├── ast_nodes.py            # AST node class hierarchy
├── parser.py               # Recursive descent parser (tokens -> AST)
├── optimizer/
│   ├── __init__.py
│   ├── engine.py           # Rule engine / fixed-point driver
│   ├── rules.py            # Individual optimization rules
├── planner.py               # AST -> logical execution plan
├── executor.py              # (optional) executes plan against sample in-memory tables
├── utils/
│   ├── tree_printer.py       # Recursive indented tree printer + optional Graphviz export
├── sample_data/
│   └── tables.py            # Small hardcoded tables (users, orders, etc.) for demo execution
├── tests/
│   ├── test_lexer.py
│   ├── test_parser.py
│   ├── test_optimizer.py
│   └── test_planner.py
├── requirements.txt
└── README.md
```

---

## 2. Grammar Scope (v1 — must-have)

Support this subset of SQL, expressed as an EBNF-style grammar:

```
query        := "SELECT" column_list "FROM" table_name [where_clause] [order_clause] ";"
column_list  := "*" | column ("," column)*
column       := IDENTIFIER
table_name   := IDENTIFIER
where_clause := "WHERE" condition
condition    := comparison (("AND" | "OR") comparison)*
comparison   := operand comp_op operand
operand      := IDENTIFIER | NUMBER | STRING
comp_op      := "=" | "!=" | "<" | ">" | "<=" | ">="
order_clause := "ORDER" "BY" column ["ASC" | "DESC"]
```

**v2 — stretch goals (only after v1 fully works):**
- `JOIN` support (`INNER JOIN table ON condition`)
- Nested subqueries in `WHERE`
- `GROUP BY` / `HAVING` / aggregate functions (`COUNT`, `SUM`, `AVG`)
- `LIMIT`

Do not attempt v2 features until v1 lexer → parser → optimizer → planner → UI pipeline works end-to-end on simple queries.

---

## 3. Module-by-Module Spec

### 3.1 `tokens.py`
Define a `TokenType` enum: `SELECT, FROM, WHERE, AND, OR, ORDER, BY, ASC, DESC, IDENTIFIER, NUMBER, STRING, COMMA, STAR, EQ, NEQ, LT, GT, LTE, GTE, SEMICOLON, EOF`.
Define a `Token` dataclass: `{type: TokenType, value: str, position: int}`.

### 3.2 `lexer.py`
- Class `Lexer(source: str)` with method `tokenize() -> list[Token]`.
- Scan character by character; handle whitespace skipping, keywords (case-insensitive), identifiers, numeric literals, quoted string literals, operators (including two-char operators like `<=`, `>=`, `!=`).
- Raise a custom `LexError` with position info on invalid characters.

### 3.3 `ast_nodes.py`
Define node classes (use `dataclasses`, all inherit from a common `ASTNode` base):
- `ScanNode(table: str)`
- `FilterNode(condition: ConditionNode, child: ASTNode)`
- `ProjectNode(columns: list[str], child: ASTNode)`
- `SortNode(column: str, direction: str, child: ASTNode)`
- `ConditionNode(left: str|int|str, op: str, right: str|int|str)`
- `AndNode(left: ConditionNode, right: ConditionNode)`
- `OrNode(left: ConditionNode, right: ConditionNode)`
- (v2) `JoinNode(left: ASTNode, right: ASTNode, condition: ConditionNode, join_type: str)`

Each node should implement `__repr__` for debugging and be immutable-friendly (rules create new nodes rather than mutating in place, to keep before/after trees independently inspectable).

### 3.4 `parser.py`
- Class `Parser(tokens: list[Token])` with method `parse() -> ASTNode`.
- Recursive descent, one method per grammar rule (`parse_query`, `parse_column_list`, `parse_where_clause`, `parse_condition`, `parse_comparison`, `parse_order_clause`).
- The parser should build the **initial logical tree** in this canonical shape (innermost to outermost):
  `Scan → Filter (if WHERE present) → Project → Sort (if ORDER BY present)`
- Raise a custom `ParseError` with a helpful message and the offending token.

### 3.5 `optimizer/rules.py`
Each rule is a function `rule_name(node: ASTNode) -> tuple[ASTNode, bool]` returning `(possibly_new_tree, was_applied)`. Implement, in this priority order:

1. **`constant_folding`** — simplify trivially true/false conditions (e.g. `1=1` → drop the condition entirely; if the whole WHERE becomes trivially true, remove the `FilterNode`).
2. **`predicate_pushdown`** — if a `FilterNode` sits above a node it can be pushed below (relevant once JOINs exist in v2; in v1 this mainly matters for ordering Filter directly above Scan, which the parser already does — document this as a no-op in v1, active in v2).
3. **`projection_pushdown`** — ensure only columns referenced downstream are retained; in v1 this mostly means marking which columns the `ScanNode` conceptually needs (used for reporting/plan display even without real storage).
4. **`redundant_filter_elimination`** — merge/drop duplicate or subsumed conditions (e.g. `age>18 AND age>18` → `age>18`).
5. (v2) **`join_reordering`** — reorder join children to put the smaller/more selective side first, using a simple heuristic (e.g. table row-count estimates from `sample_data`).

Each rule must be independently unit-testable: given a hand-built input AST, assert the exact output AST.

### 3.6 `optimizer/engine.py`
- Function `optimize(ast: ASTNode) -> tuple[ASTNode, list[str]]`.
- Runs all rules in a loop (fixed-point iteration): keep applying the rule list until a full pass produces no changes, or a max-iteration safety cap (e.g. 20) is hit.
- Return the optimized tree plus an ordered list of rule names that fired (for UI display), including how many times each fired.

### 3.7 `planner.py`
- Function `generate_plan(ast: ASTNode) -> PlanNode` that converts the optimized AST into an "execution plan" representation — for v1 this can be structurally the same tree but relabeled with plan-operator names (`SeqScan`, `Filter`, `Project`, `Sort`) plus estimated cost annotations (e.g. row-count estimates from `sample_data`, so you can show a plausible "cost before vs after" number).
- This is what sells the "query optimizer" framing — even a naive cost model (rows scanned = table size, rows after filter = heuristic percentage) is enough for a compelling demo metric.

### 3.8 `utils/tree_printer.py`
- Function `print_tree(node: ASTNode, indent: int = 0) -> str` — recursive indented text representation, reused for original AST, optimized AST, and plan.
- Optional: function `to_dot(node: ASTNode) -> str` producing Graphviz DOT syntax, and a way to render it to PNG/SVG (Streamlit can render Graphviz directly via `st.graphviz_chart`).

### 3.9 `sample_data/tables.py`
- 2-3 small hardcoded tables as lists of dicts (e.g. `users`, `orders`) with ~10-20 rows each, plus a `TABLE_ROW_COUNTS` dict used by the planner's cost estimates.

### 3.10 `executor.py` (optional but recommended for demo strength)
- Function `execute(plan: PlanNode, tables: dict) -> list[dict]` that actually runs the plan against `sample_data` tables (in-memory filter/project/sort using plain Python). This lets you show **real query results**, not just trees — strong addition for grading/demo, and proves optimized/unoptimized plans return identical results.

### 3.11 `app.py` (Streamlit UI)
Layout:
1. Title + short project description at top.
2. `st.text_area` for SQL input, with 2-3 example queries as buttons/dropdown to autofill (so the professor can quickly try it without typing).
3. `st.button("Run")` triggers: lex → parse → optimize → plan → (optionally) execute.
4. Two-column layout: **Original AST** (left) vs **Optimized AST** (right), each via `st.code(print_tree(...))`.
5. Below: **Rules Applied** as a `st.write` list or `st.table` (rule name, times fired).
6. Below: **Execution Plan** with estimated cost before vs after (`st.metric` deltas look good here — e.g. "Estimated rows scanned: 10,000 → 42").
7. Optional: **Query Result** table (`st.dataframe`) if `executor.py` is wired in.
8. Wrap lex/parse errors in try/except and show `st.error(...)` with a friendly message instead of crashing.

---

## 4. Build Order (do in this sequence, verify each step before moving on)

1. `tokens.py` + `ast_nodes.py` — pure data structures, no logic yet.
2. `lexer.py` + `tests/test_lexer.py` — verify tokenization on 5-6 sample queries.
3. `parser.py` + `tests/test_parser.py` — verify AST shape on the same sample queries.
4. `utils/tree_printer.py` — get readable output early; use it to sanity-check parser output by eye.
5. `optimizer/rules.py` (start with just `constant_folding`) + `tests/test_optimizer.py`.
6. `optimizer/engine.py` — wire the fixed-point loop, test with `constant_folding` alone first.
7. Add remaining v1 rules one at a time, testing each in isolation before combining.
8. `sample_data/tables.py` + `planner.py` — add cost estimates.
9. (optional) `executor.py` — real execution against sample data.
10. `app.py` — wire everything into Streamlit last, once the CLI/test-driven pipeline works standalone (test via a plain `if __name__ == "__main__":` script before touching Streamlit).
11. Only after v1 is fully working end-to-end: attempt v2 stretch goals (JOIN, subqueries, GROUP BY).

---

## 5. Example Queries to Support (use these as your test/demo set)

```sql
SELECT * FROM users;

SELECT name, age FROM users WHERE age > 18;

SELECT name FROM users WHERE age > 18 AND 1=1;

SELECT id, name FROM orders WHERE status = 'shipped' ORDER BY id DESC;

SELECT name FROM users WHERE age > 18 AND age > 18;
```

These exercise: base scan, filter+project, constant folding, ordering, and redundant filter elimination respectively.

---

## 6. Deliverables Checklist

- [ ] Working lexer, parser, optimizer, planner (all unit tested)
- [ ] Streamlit app showing original AST, optimized AST, rules applied, and estimated cost before/after
- [ ] (Recommended) real query execution against sample in-memory tables, proving optimized == unoptimized results
- [ ] `README.md` explaining architecture, how to run (`streamlit run app.py`), and grammar supported
- [ ] Short written report/slides covering: motivation, architecture diagram, each optimization rule with a before/after example, and screenshots of the UI

---

## 7. Notes for the Coding Agent

- Favor immutable AST rewriting in rules (build new nodes) over in-place mutation — this keeps "original vs optimized" comparison trivial and avoids subtle aliasing bugs.
- Keep every module importable and testable outside of Streamlit; Streamlit should only ever call into these modules, never contain business logic itself.
- Write unit tests alongside each module as it's built, not at the end.
- Prioritize v1 grammar being rock-solid over rushing into v2 features — the grading rubric will likely weight correctness and clarity of the core pipeline over feature breadth.
