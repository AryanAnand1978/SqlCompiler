# SQL Query Compiler and Optimizer

A small, rule-based logical SQL optimizer for teaching and demonstration. It turns a restricted SQL query into an immutable AST, applies safe rewrites, then emits a costed logical execution plan.

## Run interactively

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

The browser app accepts a query, displays the AST before and after optimization, lists fired rules, shows a costed plan, and returns results from the supplied `users` and `orders` demo tables.

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

The v1 grammar supports `SELECT` (a column list or `*`), `FROM`, table aliases, `JOIN`/`INNER JOIN ... ON`, `WHERE` comparisons joined by `AND`/`OR`, and `ORDER BY ... ASC|DESC`; a trailing semicolon is optional. Keywords are case-insensitive. Supported comparison operators are `=`, `!=`, `<`, `>`, `<=`, and `>=`.

Example:

```sql
SELECT name FROM users WHERE age > 18 AND 1 = 1 ORDER BY name ASC;
```

## Architecture

`Lexer` produces tokens, `Parser` builds the canonical `Scan → Filter → Project → Sort` AST, `optimize` repeatedly applies rules, and `generate_plan` creates `SeqScan`, `Filter`, `Project`, and `Sort` plan nodes. `print_tree` renders either tree for inspection.

Current v1 rules fold literal comparisons, remove duplicate `AND` predicates, annotate scans with columns needed by projection/filter/sort, and document predicate pushdown as a no-op until joins exist. Scan cost is proportional to rows × columns read, so the UI exposes the benefit of projection pushdown as a before/after percentage. Plan estimates use the row counts of the included `users` and `orders` demo tables; unknown tables default to 1,000 rows.

## Deferred work

Joins, subqueries, grouping, aggregates, and `LIMIT` are intentionally outside v1.
