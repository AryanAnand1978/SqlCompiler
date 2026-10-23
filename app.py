import streamlit as st

from sqlopt.executor import ExecutionError, execute
from sqlopt.lexer import LexError, Lexer
from sqlopt.optimizer.engine import optimize_steps
from sqlopt.optimizer.rule_metadata import RULE_INFO
from sqlopt.parser import ParseError, Parser
from sqlopt.planner import estimate_cost, generate_plan
from sqlopt.sample_data.tables import TABLES
from sqlopt.utils.relalg_printer import to_relalg_string
from sqlopt.utils.sql_printer import ast_to_sql
from sqlopt.utils.tree_printer import print_tree, print_tree_highlighted

EXAMPLES = {
    # 1. Joins & Multi-Table Relations
    "Join: Predicate Pushdown through Join": "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE u.age > 25 AND o.amount > 1000;",
    "Join: Redundant Self-Join Elimination (Join Pruning)": "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id JOIN users u2 ON u.id = u2.id WHERE o.status = 'shipped';",
    "Join: Employees & Departments (Filtered + Sorted)": "SELECT e.name, d.dept_name, e.salary FROM employees e JOIN departments d ON e.dept_id = d.id WHERE e.salary > 60000 ORDER BY e.salary DESC;",
    "Join: All Rules Fired (Join + Tautology + Duplicates + Projection)": "SELECT e.name, d.dept_name, e.salary FROM employees e JOIN departments d ON e.dept_id = d.id WHERE e.salary > 50000 AND 1 = 1 AND e.salary > 50000 ORDER BY e.salary DESC;",
    "Join: Users & Orders (Status filter + Tautology)": "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id WHERE u.age > 18 AND o.status = 'shipped' AND 1 = 1 AND u.age > 18;",

    # 2. Edge Cases in Boolean Predicates & Constant Folding
    "Edge Case: Syntactic Sugar (BETWEEN Predicate)": "SELECT name, age FROM users WHERE age BETWEEN 18 AND 30 ORDER BY age ASC;",
    "Edge Case: Syntactic Sugar (IN List Predicate)": "SELECT name, category, price FROM products WHERE category IN ('Books', 'Furniture') ORDER BY price ASC;",
    "Edge Case: Duplicate Elimination (SELECT DISTINCT)": "SELECT DISTINCT city FROM users WHERE active = 1 AND active = 1;",
    "Edge Case: Contradiction / Dead Predicate (1 = 0)": "SELECT name, price FROM products WHERE price > 1000 AND 1 = 0;",
    "Edge Case: Tautology Elimination (1 = 1)": "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND 1 = 1;",
    "Edge Case: Duplicate Filter Deduplication (c ∧ c = c)": "SELECT name, age FROM users WHERE age > 18 AND age > 18;",
    "Edge Case: Self-Comparison (name = name)": "SELECT name, age FROM users WHERE age > 18 AND age > 18 AND 1 = 1 AND name = name;",
    "Edge Case: Disjunction / OR Predicates": "SELECT name, category, price FROM products WHERE category = 'Books' OR category = 'Furniture' ORDER BY price ASC;",

    # 3. Projection Pushdown & I/O Reduction Edge Cases
    "Edge Case: Massive Projection Pushdown (1 of 5 columns)": "SELECT name FROM products;",
    "Edge Case: Wildcard (SELECT *) — Proves Pushdown is Safely Skipped": "SELECT * FROM products WHERE stock > 0;",
    "Edge Case: Filtered Column Not in SELECT List": "SELECT name FROM products WHERE price > 5000;",

    # 4. Sorting, Limit & Pagination
    "Limit: Top 3 Highest Paid Employees": "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 3;",
    "Limit: Paged Results (LIMIT 2 OFFSET 2)": "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 2 OFFSET 2;",
    "Sort: Products by Price Descending": "SELECT name, category, price FROM products WHERE stock > 0 ORDER BY price DESC;",
    "Sort: Shipped Orders by Amount": "SELECT id, user_id, amount FROM orders WHERE status = 'shipped' ORDER BY amount DESC;",
    "Filter: Adult Active Users": "SELECT name, city, age FROM users WHERE active = 1 AND age >= 18 ORDER BY age ASC;",
}

st.set_page_config(page_title="SQL Optimizer", page_icon="⚡", layout="wide")
st.title("SQL Query Compiler and Optimizer")
st.caption("A compiler-pipeline demonstration showing Lexing, Recursive-Descent Parsing, and Step-Through Relational Algebra Optimization.")

# Example loader
selected = st.selectbox("Load an example query", list(EXAMPLES), key="example")
if st.button("Use selected example"):
    st.session_state.sql = EXAMPLES[selected]
    st.session_state.has_run = False

sql = st.text_area("SQL query", value=st.session_state.get("sql", EXAMPLES[selected]), height=110, key="sql")

with st.expander("📖 Grammar (EBNF), Supported Syntax, and Demo Catalog"):
    st.markdown("### Grammar (EBNF)")
    st.code(
        """query        := "SELECT" ["DISTINCT"] column_list "FROM" table_name [alias] [join_clause]* [where_clause] [order_clause] [limit_clause] ";"
column_list  := "*" | column ("," column)*
column       := IDENTIFIER ["." IDENTIFIER]
table_name   := IDENTIFIER
alias        := IDENTIFIER
join_clause  := ["INNER"] "JOIN" table_name [alias] "ON" condition
where_clause := "WHERE" condition
condition    := comparison (("AND" | "OR") comparison)*
comparison   := operand comp_op operand | operand "BETWEEN" operand "AND" operand | operand "IN" "(" operand ("," operand)* ")"
operand      := IDENTIFIER ["." IDENTIFIER] | NUMBER | STRING
comp_op      := "=" | "!=" | "<" | ">" | "<=" | ">="
order_clause := "ORDER" "BY" column ["ASC" | "DESC"]
limit_clause := "LIMIT" NUMBER ["OFFSET" NUMBER]""",
        language="text",
    )
    st.markdown("### Supported Syntax Summary")
    st.code("SELECT [DISTINCT] column[, ...] | * FROM table [alias] [INNER] JOIN table [alias] ON condition [WHERE condition] [ORDER BY column ASC|DESC] [LIMIT n [OFFSET m]];", language="sql")
    st.markdown("### Demo Database Catalog")
    st.write("The database catalog includes **5 tables** with varying schemas and record sizes:")
    catalog_rows = [
        {
            "Table": name,
            "Rows": len(rows),
            "Columns": ", ".join(rows[0].keys()),
        }
        for name, rows in TABLES.items()
    ]
    st.dataframe(catalog_rows, hide_index=True, use_container_width=True)

# Run Controls
btn_c1, btn_c2 = st.columns([1, 1])
run_optimizer = btn_c1.button("⚡ Run Optimizer (Step-Through Mode)", type="primary", use_container_width=True)
run_all = btn_c2.button("⏩ Run All (Skip to End)", use_container_width=True)


def execute_pipeline(query_text: str):
    tokens = Lexer(query_text).tokenize()
    parser = Parser(tokens)
    ast, trace = parser.parse_with_trace()
    steps = optimize_steps(ast)
    return tokens, trace, ast, steps


if run_optimizer or run_all:
    try:
        tokens, trace, original_ast, opt_steps = execute_pipeline(sql)
        st.session_state.tokens = tokens
        st.session_state.trace = trace
        st.session_state.original_ast = original_ast
        st.session_state.opt_steps = opt_steps
        st.session_state.current_step = (len(opt_steps) - 1) if run_all and opt_steps else 0
        st.session_state.has_run = True
        st.session_state.error = None
    except (LexError, ParseError, ExecutionError) as exc:
        st.session_state.error = str(exc)
        st.session_state.has_run = False

if st.session_state.get("error"):
    st.error(st.session_state.error)

if st.session_state.get("has_run"):
    tokens = st.session_state.tokens
    trace = st.session_state.trace
    original = st.session_state.original_ast
    steps = st.session_state.opt_steps

    st.markdown("---")
    st.subheader("Compiler Pipeline Inspection")

    # 1. Tokens Table
    with st.expander("1. Lexer Output (Tokens)", expanded=False):
        token_rows = [
            {"#": i + 1, "Type": tok.type.name, "Value": tok.value, "Position": tok.position}
            for i, tok in enumerate(tokens)
        ]
        st.dataframe(token_rows, use_container_width=True, hide_index=True)

    # 2. Parse Trace
    with st.expander("2. Parser Call Sequence (Grammar Trace)", expanded=False):
        st.caption("Call hierarchy of recursive-descent grammar rules and matching tokens:")
        st.code("\n".join(trace), language="text")

    # 3. AST Optimization (Step-Through Mode)
    st.markdown("### 3. Query Optimization")

    if not steps:
        st.info("✅ Fixed point reached immediately — no optimization rules apply (query AST is already minimal and canonical).")
        col_orig, col_opt = st.columns(2)
        with col_orig:
            st.subheader("Original")
            st.markdown("**SQL Query**")
            st.code(ast_to_sql(original), language="sql")
            st.markdown("**AST**")
            st.code(print_tree(original))
            st.markdown("**Relational Algebra**")
            st.code(to_relalg_string(original), language="text")
        with col_opt:
            st.subheader("Optimized")
            st.markdown("**SQL Query**")
            st.code(ast_to_sql(original), language="sql")
            st.markdown("**AST**")
            st.code(print_tree(original))
            st.markdown("**Relational Algebra**")
            st.code(to_relalg_string(original), language="text")
        final_ast = original
    else:
        current_step = st.session_state.get("current_step", 0)
        # Bounds check
        current_step = max(0, min(len(steps) - 1, current_step))
        st.session_state.current_step = current_step

        # Step navigation bar
        nav_c1, nav_c2, nav_c3, nav_c4 = st.columns([1, 2, 1, 1])
        if nav_c1.button("◀ Previous", disabled=(current_step <= 0), use_container_width=True, key="btn_prev"):
            st.session_state.current_step = max(0, current_step - 1)
            st.rerun()

        nav_c2.markdown(
            f"<div style='text-align:center; padding-top:6px; font-size:1.15rem; font-weight:700;'>Step {current_step + 1} of {len(steps)}</div>",
            unsafe_allow_html=True,
        )

        if nav_c3.button("Next rule ▶", disabled=(current_step >= len(steps) - 1), use_container_width=True, key="btn_next"):
            st.session_state.current_step = min(len(steps) - 1, current_step + 1)
            st.rerun()

        if nav_c4.button("⏭ Jump to End", disabled=(current_step >= len(steps) - 1), use_container_width=True, key="btn_jump"):
            st.session_state.current_step = len(steps) - 1
            st.rerun()

        step = steps[current_step]
        rule_meta = RULE_INFO.get(step.rule_name, {})
        display_name = rule_meta.get("display_name", step.rule_name)
        identity = step.identity or rule_meta.get("identity", "—")

        # Prominent rule justification & formal identity
        st.info(f"**Applied Rule: {display_name}** (`{step.rule_name}`)\n\n**Algebraic Identity:** {identity}")

        # Metrics for live cost & row estimates
        before_rows = estimate_cost(step.before)
        after_rows = estimate_cost(step.after)
        before_plan = generate_plan(step.before)
        after_plan = generate_plan(step.after)

        m1, m2, m3 = st.columns(3)
        m1.metric("Estimated Output Rows", value=after_rows, delta=after_rows - before_rows if after_rows != before_rows else 0)
        m2.metric("Plan Cost Units", value=f"{after_plan.estimated_cost:.2f}", delta=f"{after_plan.estimated_cost - before_plan.estimated_cost:.2f}" if after_plan.estimated_cost != before_plan.estimated_cost else 0)
        m3.metric("Fixed-Point Loop", value=f"Iteration {step.iteration}")

        # Before & After: SQL Query, AST, and Relational Algebra
        before_col, after_col = st.columns(2)
        with before_col:
            st.subheader(f"Before Rule (Step {current_step + 1})")
            st.markdown("**SQL Query**")
            st.code(step.before_sql, language="sql")
            st.markdown("**AST**")
            st.code(print_tree_highlighted(step.before, step.changed_node_id))
            st.markdown("**Relational Algebra**")
            st.code(step.before_ra, language="text")

        with after_col:
            st.subheader(f"After Rule (Step {current_step + 1})")
            st.markdown("**SQL Query**")
            st.code(step.after_sql, language="sql")
            st.markdown("**AST**")
            st.code(print_tree_highlighted(step.after, step.changed_node_id))
            st.markdown("**Relational Algebra**")
            st.code(step.after_ra, language="text")

        if current_step == len(steps) - 1:
            total_iterations = steps[-1].iteration
            st.success(f"✅ Fixed point reached — no further rules apply after {total_iterations} iterations.")

        final_ast = steps[-1].after

    # 4. Final Comparison (Original vs Optimized)
    st.markdown("---")
    st.subheader("Transformation Summary (Original vs Optimized)")
    sum_orig, sum_opt = st.columns(2)
    with sum_orig:
        st.markdown("### Original")
        st.markdown("**Original SQL**")
        st.code(ast_to_sql(original), language="sql")
        st.markdown("**Original AST**")
        st.code(print_tree(original))
        st.markdown("**Original Relational Algebra**")
        st.code(to_relalg_string(original), language="text")

    with sum_opt:
        st.markdown("### Optimized")
        st.markdown("**Optimized SQL**")
        st.code(ast_to_sql(final_ast), language="sql")
        st.markdown("**Optimized AST**")
        st.code(print_tree(final_ast))
        st.markdown("**Optimized Relational Algebra**")
        st.code(to_relalg_string(final_ast), language="text")

    # 5. Rules Applied Summary Table
    st.markdown("---")
    st.subheader("Rules Applied Summary")
    if steps:
        rule_counts = {}
        for s in steps:
            rule_counts[s.rule_name] = rule_counts.get(s.rule_name, 0) + 1

        summary_rows = []
        for r_name, count in rule_counts.items():
            r_meta = RULE_INFO.get(r_name, {})
            summary_rows.append({
                "Rule": r_meta.get("display_name", r_name),
                "Internal Name": r_name,
                "Algebraic Identity": r_meta.get("identity", "—"),
                "Times Fired": f"{count}x",
            })
        st.dataframe(summary_rows, hide_index=True, use_container_width=True)
    else:
        st.write("No optimization rules were needed.")

    # 6. Cost Comparison & Execution Plan
    original_plan = generate_plan(original)
    optimized_plan = generate_plan(final_ast)
    savings = original_plan.estimated_cost - optimized_plan.estimated_cost
    savings_percent = (savings / original_plan.estimated_cost * 100) if original_plan.estimated_cost else 0

    col_cost1, col_cost2, col_cost3 = st.columns(3)
    col_cost1.metric("Original Plan Cost", f"{original_plan.estimated_cost:.2f}")
    col_cost2.metric("Optimized Plan Cost", f"{optimized_plan.estimated_cost:.2f}", f"{-savings:.2f}")
    col_cost3.metric("Estimated Cost Reduction", f"{savings_percent:.1f}%", f"{savings:.2f} units")

    # Execution Plan & Query Results
    try:
        results = execute(final_ast)
        st.subheader("Physical Execution Plan")
        st.code(print_tree(optimized_plan))

        st.subheader("Query Results")
        st.caption(f"Rows returned: {len(results)}")
        st.dataframe(results, hide_index=True, use_container_width=True)
    except ExecutionError as exc:
        st.error(f"Execution Error: {exc}")
