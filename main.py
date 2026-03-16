#!/usr/bin/env python3
"""
SMT Formula Repair Tool — CLI
"""

import argparse
import sys
import textwrap

from smt_repair.repair import SMTRepair


RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
RED    = "\033[31m"
GREY   = "\033[90m"
PURPLE = "\033[35m"

def _c(text, code, nc):
    return text if nc else f"{code}{text}{RESET}"


def _banner(nc):
    print(_c("SMT Formula Repair Tool\n", BOLD, nc))


def _print_repair(i, repair, nc, show_score=False):
    print(_c(f"── Repair #{i}  [{repair.strategy}]", BOLD, nc))
    print(_c("  desc : ", GREY, nc) + repair.description)

    if show_score:
        print(_c("  score: ", GREY, nc) + _c(repair.score_explanation, PURPLE, nc))

    if repair.detail:
        for k, v in repair.detail.items():
            print(_c(f"  {k}: ", GREY, nc) + str(v))

    print(_c("\nRepaired formula:", YELLOW, nc))
    for line in repair.smt2_output.splitlines():
        print("  " + _c(line, GREEN, nc))
    print()


def build_parser():
    parser = argparse.ArgumentParser(
        prog="smt_repair",
        description="Repair UNSAT SMT-LIB2 formulas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          python main.py --input examples/budget.smt2
          python main.py --input examples/boolean_access.smt2 --strategy replace_boolean
          python main.py --interactive
          python main.py --input examples/simple.smt2 --best
        """),
    )

    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--input",       "-i", metavar="FILE")
    src.add_argument("--formula",     "-f", metavar="SMT2")
    src.add_argument("--interactive", "-I", action="store_true",
                     help="Build formula interactively (no file needed)")

    parser.add_argument("--strategy", "-s",
        choices=["replace_constant", "replace_operator", "delete_subformula",
                 "replace_boolean", "replace_bitvector", "combine_repairs", "all"],
        default="all")
    parser.add_argument("--max-repairs", "-m", type=int, default=5, metavar="N")
    parser.add_argument("--best",     action="store_true",
                        help="Show only the single best repair")
    parser.add_argument("--scores",   action="store_true",
                        help="Show quality score for each repair")
    parser.add_argument("--verbose",  "-v", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    nc = args.no_color

    _banner(nc)

    engine = SMTRepair(verbose=args.verbose)
    max_r = 1 if args.best else args.max_repairs

    try:
        if args.interactive:
            print(_c("interactive mode\n", CYAN, nc))
            from smt_repair.dynamic_input import interactive_input
            assertions = interactive_input()
            if not assertions:
                print(_c("no formula entered.", RED, nc))
                sys.exit(1)
            repairs = engine.repair_assertions(
                assertions, strategy=args.strategy,
                max_repairs=max_r, combine=True)

        elif args.input:
            print(_c(f"file: {args.input}", GREY, nc))
            repairs = engine.repair_file(
                args.input, strategy=args.strategy,
                max_repairs=max_r, combine=True)

        else:
            print(_c("inline formula", GREY, nc))
            repairs = engine.repair_string(
                args.formula, strategy=args.strategy,
                max_repairs=max_r, combine=True)

    except FileNotFoundError as e:
        print(_c(f"\nfile not found: {e}", RED, nc))
        sys.exit(1)
    except Exception as e:
        print(_c(f"\nerror: {e}", RED, nc))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    print()

    if not repairs:
        print(_c("no repairs found.", RED, nc))
        sys.exit(2)

    if args.best:
        print(_c("best repair:\n", GREEN, nc))
    else:
        print(_c(f"{len(repairs)} repair(s) found\n", GREEN, nc))

    for i, r in enumerate(repairs, 1):
        _print_repair(i, r, nc, show_score=args.scores or args.verbose)

    print(_c("-" * 40, GREY, nc))
    print(_c(f"strategy: {args.strategy}", GREY, nc))
    print(_c(f"shown:    {len(repairs)}", GREY, nc))


if __name__ == "__main__":
    main()
