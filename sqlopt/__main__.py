import argparse
import json

from .executor import ExecutionError, execute
from .lexer import LexError, Lexer
from .optimizer.engine import optimize
from .parser import ParseError, Parser
from .planner import generate_plan
from .utils.tree_printer import print_tree


def run_query(sql: str) -> None:
    ast = Parser(Lexer(sql).tokenize()).parse()
    optimized, rules = optimize(ast)
    print("\nOriginal AST\n" + print_tree(ast))
    print("\nRules applied: " + (", ".join(rules) if rules else "none"))
    print("\nOptimized AST\n" + print_tree(optimized))
    print("\nExecution plan\n" + print_tree(generate_plan(optimized)))
    print("\nQuery results\n" + json.dumps(execute(optimized), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a SQL optimizer demo query.")
    parser.add_argument("query", nargs="*", help="SQL query to run; omit for interactive mode")
    args = parser.parse_args()
    if args.query:
        try: run_query(" ".join(args.query))
        except (LexError, ParseError, ExecutionError) as exc: parser.error(str(exc))
        return
    print("SQL Optimizer interactive mode. Type a v1 SELECT query, or 'quit'.")
    while True:
        try: sql = input("sql> ").strip()
        except (EOFError, KeyboardInterrupt): print(); break
        if sql.lower() in {"quit", "exit"}: break
        if sql:
            try: run_query(sql)
            except (LexError, ParseError, ExecutionError) as exc: print(f"Error: {exc}")


if __name__ == "__main__":
    main()
