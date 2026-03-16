# Three ways to get assertions into the repair engine:
#   1. FormulaBuilder  - build directly with Z3 Python objects
#   2. SMT2StringBuilder - build an SMT-LIB2 string at runtime
#   3. interactive_input() - CLI prompt for quick testing

from z3 import (
    Int, Real, Bool, BitVec,
    parse_smt2_string,
)


class FormulaBuilder:
    """Build Z3 assertions programmatically. Supports int/real/bool/bitvec vars."""

    def __init__(self):
        self._assertions = []
        self._vars = {}

    def int_var(self, name):
        v = Int(name)
        self._vars[name] = v
        return v

    def real_var(self, name):
        v = Real(name)
        self._vars[name] = v
        return v

    def bool_var(self, name):
        v = Bool(name)
        self._vars[name] = v
        return v

    def bitvec_var(self, name, width=32):
        v = BitVec(name, width)
        self._vars[name] = v
        return v

    def add(self, assertion):
        self._assertions.append(assertion)
        return self

    def build(self):
        return list(self._assertions)

    def reset(self):
        self._assertions.clear()
        self._vars.clear()
        return self

    def __repr__(self):
        lines = [f"FormulaBuilder ({len(self._assertions)} assertions):"]
        for i, a in enumerate(self._assertions):
            lines.append(f"  [{i+1}] {a}")
        return "\n".join(lines)


class SMT2StringBuilder:
    """Build an SMT-LIB2 string piece by piece and parse it at the end."""

    def __init__(self):
        self._lines = []

    def declare_int(self, name):
        self._lines.append(f"(declare-const {name} Int)")
        return self

    def declare_real(self, name):
        self._lines.append(f"(declare-const {name} Real)")
        return self

    def declare_bool(self, name):
        self._lines.append(f"(declare-const {name} Bool)")
        return self

    def declare_bitvec(self, name, width=8):
        self._lines.append(f"(declare-const {name} (_ BitVec {width}))")
        return self

    def assert_eq(self, var, value):
        if isinstance(value, bool):
            val_str = "true" if value else "false"
        else:
            val_str = str(value)
        self._lines.append(f"(assert (= {var} {val_str}))")
        return self

    def assert_expr(self, smt2_expr):
        self._lines.append(f"(assert {smt2_expr})")
        return self

    def build(self):
        return list(parse_smt2_string("\n".join(self._lines)))

    def get_string(self):
        return "\n".join(self._lines)

    def reset(self):
        self._lines.clear()
        return self


def _natural_to_smt2(expr):
    """Convert simple infix math (x + y = 10) to SMT-LIB2 prefix. Passes through if already SMT-LIB2."""
    expr = expr.strip()

    if expr.startswith("("):
        return expr

    # handle != before anything else so it doesn't get split on =
    expr = expr.replace("!=", "@@NEQ@@")

    cmp_ops = [
        ("<=", "<="), (">=", ">="),
        ("@@NEQ@@", "distinct"),
        ("<", "<"), (">", ">"), ("=", "="),
    ]

    found_cmp = None
    found_smt = None
    for op, smt_op in cmp_ops:
        if op in expr:
            found_cmp = op
            found_smt = smt_op
            break

    if found_cmp is None:
        return expr

    lhs, _, rhs = expr.partition(found_cmp)
    lhs_smt = _infix_to_prefix(lhs.strip())
    rhs_smt = _infix_to_prefix(rhs.strip())
    return f"({found_smt} {lhs_smt} {rhs_smt})"


# this parser is pretty basic — it handles the common cases but will
# break on things like unary minus in the middle of an expression.
# good enough for the interactive mode use case.
def _infix_to_prefix(expr):
    """Infix → prefix for +, -, * (left-associative, respects parens)."""
    expr = expr.strip()

    # strip matched outer parens
    if expr.startswith("(") and expr.endswith(")"):
        depth = 0
        for i, c in enumerate(expr):
            if c == "(": depth += 1
            if c == ")": depth -= 1
            if depth == 0 and i < len(expr) - 1:
                break
        else:
            expr = expr[1:-1].strip()

    for op in ["+", "-"]:
        parts = _split_on_op(expr, op)
        if len(parts) > 1:
            converted = [_infix_to_prefix(p) for p in parts]
            acc = converted[0]
            for part in converted[1:]:
                acc = f"({op} {acc} {part})"
            return acc

    parts = _split_on_op(expr, "*")
    if len(parts) > 1:
        converted = [_infix_to_prefix(p) for p in parts]
        acc = converted[0]
        for part in converted[1:]:
            acc = f"(* {acc} {part})"
        return acc

    return expr


def _split_on_op(expr, op):
    """Split on op, but only at paren depth 0."""
    parts = []
    depth = 0
    current = ""
    for c in expr:
        if c == "(":
            depth += 1
            current += c
        elif c == ")":
            depth -= 1
            current += c
        elif c == op and depth == 0:
            if op == "-" and not current.strip():
                current += c  # unary minus, keep going
            else:
                parts.append(current.strip())
                current = ""
        else:
            current += c
    if current.strip():
        parts.append(current.strip())
    return parts if len(parts) > 1 else [expr]


def interactive_input():
    """Interactive CLI — declare variables and type constraints, returns assertions."""
    print("\nSMT Formula Builder")
    print("-" * 40)
    print("Declare variables first, then enter constraints.")
    print("Type 'done' at any prompt to move on.\n")

    builder = SMT2StringBuilder()
    var_names = []

    print("Variables (type: int / real / bool / bitvec8)")
    print("  e.g.  x int   or   flag bool\n")

    while True:
        entry = input("  var> ").strip()
        if not entry or entry.lower() == "done":
            break
        parts = entry.split()
        if len(parts) != 2:
            print("  bad format — try:  x int")
            continue
        name, vtype = parts[0], parts[1].lower()
        if vtype == "int":
            builder.declare_int(name)
        elif vtype == "real":
            builder.declare_real(name)
        elif vtype == "bool":
            builder.declare_bool(name)
        elif vtype in ("bitvec8", "bv8"):
            builder.declare_bitvec(name, 8)
        else:
            print(f"  unknown type '{vtype}'")
            continue
        var_names.append(name)
        print(f"  ok: {name} ({vtype})")

    if not var_names:
        print("No variables declared.")
        return []

    print(f"\nConstraints  (vars: {', '.join(var_names)})")
    print("  plain math:   x + y = 10  /  x > 0  /  x * y = 100")
    print("  or SMT-LIB2:  (= (+ x y) 10)\n")

    n_added = 0

    while True:
        expr = input("  constraint> ").strip()
        if not expr or expr.lower() == "done":
            break

        # auto-convert plain math to SMT-LIB2 if needed
        converted = _natural_to_smt2(expr)
        if converted != expr:
            print(f"  -> {converted}")

        # quick parse check before committing
        probe = SMT2StringBuilder()
        probe._lines = list(builder._lines)
        probe.assert_expr(converted)
        try:
            probe.build()
            builder.assert_expr(converted)
            n_added += 1
            print(f"  added ({n_added})")
        except Exception as e:
            err = str(e).replace("b'", "").replace("\\n'", "").strip()
            print(f"  parse error: {err}")

    if n_added == 0:
        print("No constraints entered.")
        return []

    try:
        assertions = builder.build()
        print(f"\nBuilt formula: {len(assertions)} assertion(s).")
        return assertions
    except Exception as e:
        print(f"Error: {e}")
        return []
