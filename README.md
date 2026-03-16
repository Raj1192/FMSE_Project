# SMT Formula Repair Tool

A command-line tool that takes broken (UNSAT) SMT-LIB2 formulas and tries to
fix them automatically. It finds the conflicting subset of assertions and
proposes small changes to make the formula satisfiable again.

Built on top of Z3. Started as a project to understand UNSAT core extraction
better — ended up growing into something more complete than I originally planned.

---

## Strategies

| Strategy | What it does |
|---|---|
| `replace_constant` | Swaps a numeric constant for the nearest value that makes the formula SAT |
| `replace_operator` | Tries mutating arithmetic/comparison operators (+, -, <, >=, etc.) |
| `delete_subformula` | Removes or weakens assertions |
| `replace_boolean` | Mutates boolean connectives (and/or/not/xor) |
| `replace_bitvector` | Handles BitVector constants and operators |
| `combine_repairs` | Tries combining single-fix repairs for multi-bug formulas |

The scoring system ranks repairs from most to least conservative — constant
tweaks rank higher than operator changes, which rank higher than deletions.
Tiebreaks prefer later assertions and smaller percentage changes.

---

## Setup

```bash
pip install -r requirements.txt   # just needs z3-solver
```

Python 3.9+ should be fine. Developed on 3.11.

---

## Usage

```bash
# run all strategies on a file
python main.py --input examples/budget.smt2

# only show the best repair
python main.py --input examples/budget.smt2 --best

# show quality scores next to each result
python main.py --input examples/simple.smt2 --scores

# target a specific strategy
python main.py --input examples/boolean_access.smt2 --strategy replace_boolean

# interactive mode — no file needed
python main.py --interactive

# inline formula
python main.py --formula "(declare-const x Int)(assert (= x 5))(assert (= x 6))"

# other flags
python main.py --input FILE --max-repairs 10 --verbose --no-color
```

---

## How it works

1. **Find the UNSAT core** — uses Z3's `assert_and_track` to get the minimal
   conflicting subset. Only those assertions get touched.

2. **Mutate** — each strategy makes small targeted changes and re-checks SAT.

3. **Combine** — the combine strategy stacks partial fixes for formulas with
   more than one bug.

4. **Score and rank** — roughly: constant fix > operator flip > boolean mutation > deletion

---

## Project layout

```
smt_repair_tool/
├── main.py
├── requirements.txt
├── examples/
│   ├── simple.smt2
│   ├── budget.smt2
│   ├── comparison.smt2
│   ├── rainbow.smt2
│   ├── boolean_access.smt2
│   ├── bitvector_register.smt2
│   └── multi_fault.smt2
└── smt_repair/
    ├── repair.py           # orchestrator
    ├── unsat_core.py       # UNSAT core extraction via assert_and_track
    ├── ast_utils.py        # AST traversal helpers
    ├── scorer.py           # repair ranking
    ├── dynamic_input.py    # interactive + programmatic input modes
    └── strategies/
        ├── replace_constant.py
        ├── replace_operator.py
        ├── delete_subformula.py
        ├── replace_boolean.py
        ├── replace_bitvector.py
        └── combine_repairs.py
```

---

## Example results

| File | Bug | Best fix |
|---|---|---|
| simple.smt2 | x=5 and x=6 | change 6→5 |
| budget.smt2 | savings off by 500 | 500→1000 |
| comparison.smt2 | x>10 and x<5 | flip > to < |
| boolean_access.smt2 | AND too strict | and→or |
| bitvector_register.smt2 | 42 > 200 impossible | adjust BV constant |
| multi_fault.smt2 | two bugs | combined fix |

---

## References

- Z3 Python API: https://z3prover.github.io/api/html/namespacez3py.html
- SMT-LIB standard: https://smtlib.cs.uiowa.edu/
- de Moura & Bjørner, Z3: An Efficient SMT Solver (TACAS 2008)
