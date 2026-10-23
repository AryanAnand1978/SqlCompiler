# SQL Query Compiler and Optimizer

A small, rule-based logical SQL optimizer for teaching and demonstration. It turns a restricted SQL query into an immutable AST, applies safe rewrites, then emits a costed logical execution plan.

## Run interactively

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

The browser app accepts a query, displays the AST before and after optimization, lists fired rules, shows a costed plan, and returns results from the supplied `users`, `orders`, `products`, `departments`, and `employees` demo tables.

You can also use a terminal command:

```powershell
python -m sqlopt "SELECT name, age FROM users WHERE age > 18 ORDER BY age DESC;"
```

Or omit the SQL argument to enter an interactive terminal prompt. Use `quit` or `exit` to leave it.

## Tests

```powershell
python -m pytest tests -q -p no:cacheprovider
```

## Supported SQL

The grammar supports:
- `SELECT` with optional `DISTINCT`, column projections, or `*`
- `FROM` with optional table aliases (`users u`)
- Multi-table `JOIN` / `INNER JOIN ... ON` (supports multiple chained joins)
- `WHERE` predicates with:
  - Binary comparisons: `=`, `!=`, `<`, `>`, `<=`, `>=`
  - Logical conjunctions: `AND`, `OR`
  - Syntactic sugar: `x BETWEEN a AND b` (desugared to `x >= a AND x <= b`)
  - Set membership: `x IN (val1, val2, ...)` (desugared to disjunction tree)
- `ORDER BY ... ASC|DESC`
- `LIMIT <int> [OFFSET <int>]` pagination
- Trailing semicolon is optional; keywords are case-insensitive.

Example:

```sql
SELECT e.name, d.dept_name, e.salary 
FROM employees e 
JOIN departments d ON e.dept_id = d.id 
WHERE e.salary BETWEEN 50000 AND 90000 
  AND d.dept_name IN ('Engineering', 'Product')
ORDER BY e.salary DESC 
LIMIT 5 OFFSET 0;
```

## Compiler Architecture & Optimization Pipeline

1. **Lexer (`sqlopt/lexer.py`)**: Tokenizes input SQL into classified tokens (`SELECT`, `JOIN`, `BETWEEN`, `IN`, `LIMIT`, etc.).
2. **Parser (`sqlopt/parser.py`)**: Recursive-descent parser producing a canonical relational AST (`Scan → [Join] → Filter → Project → Sort → [Distinct] → [Limit]`). Performs early desugaring for `BETWEEN` and `IN`.
3. **Optimizer Engine (`sqlopt/optimizer/`)**: Applies rule rewrites to a fixed point:
   - **Constant Folding**: Eliminates tautologies (`1 = 1`, `col = col`) and folds literals (`1 = 0` to contradiction).
   - **Redundant Filter Elimination**: Deduplicates repeated predicates (`A AND A` $\to$ `A`).
   - **Predicate Pushdown**: Pushes filter conditions down past joins into scan inputs so rows are filtered *before* costly nested-loop joins.
   - **Redundant Join Elimination**: Prunes unnecessary self-joins on primary keys when the duplicate join table provides no new columns.
   - **Projection Pushdown**: Annotates scan nodes with only the columns needed by downstream filter, join, sort, and select operators, drastically cutting disk/memory I/O.
4. **Planner & Cost Estimator (`sqlopt/planner.py`)**: Generates physical-like execution plan nodes (`SeqScan`, `NestedLoopJoin`, `Filter`, `Project`, `Sort`, `Distinct`, `Limit`) and calculates estimated cost based on table cardinalities and column widths.
5. **In-Memory Executor (`sqlopt/executor.py`)**: Executes the optimized plan directly against the demo catalog tables (`users`, `orders`, `products`, `departments`, `employees`).

## Deferred Work

Subqueries and aggregate grouping (`GROUP BY`, `COUNT`, `SUM`, `AVG`) are planned for future iterations.

