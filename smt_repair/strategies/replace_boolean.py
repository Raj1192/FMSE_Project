"""
Strategy: mutate boolean connectives (and/or/not/xor) in the UNSAT core.

Covers connective swaps (and→or, or→and, etc.), not-removal,
literal flips (True↔False), and variable negation.
"""

from z3 import (
    BoolRef, ExprRef,
    BoolVal, And, Or, Not, Xor, Implies,
    is_and, is_or, is_not, is_true, is_false, is_bool, is_const,
    Solver, sat
)

from smt_repair.ast_utils import (
    collect_subexpressions,
    replace_node_by_id,
    replace_operator_by_id,
)


_BOOL_MUTATIONS = {
    "and": [
        ("or",  lambda *args: Or(*args)),
        # xor only takes 2 args in Z3, fallback to Or for larger conjunctions
        ("xor", lambda *args: Xor(args[0], args[1]) if len(args) == 2 else Or(*args)),
    ],
    "or": [
        ("and", lambda *args: And(*args)),
        ("xor", lambda *args: Xor(args[0], args[1]) if len(args) == 2 else And(*args)),
    ],
    "xor": [
        ("and", lambda *args: And(*args)),
        ("or",  lambda *args: Or(*args)),
    ],
    "=>": [
        ("and", lambda *args: And(*args)),
        ("or",  lambda *args: Or(*args)),
    ],
    # not-removal: Not(p) → p
    # handles the "accidentally negated a condition" bug
    "not": [
        ("remove-not", lambda *args: args[0]),
    ],
}


def strategy_replace_boolean(assertions, core_indices):
    results = []
    seen = set()

    for idx in core_indices:
        for sub in collect_subexpressions(assertions[idx]):
            if not is_bool(sub):
                continue

            node_id  = sub.get_id()
            op_name  = sub.decl().name() if sub.children() else None

            # connective mutations (and→or, not removal, etc.)
            if op_name and op_name in _BOOL_MUTATIONS:
                if node_id in seen:
                    continue
                seen.add(node_id)

                for alt_name, alt_fn in _BOOL_MUTATIONS[op_name]:
                    r = _mutate_connective(assertions, idx, node_id, op_name, alt_name, alt_fn, sub)
                    if r:
                        results.append(r)

            # flip True/False literals
            elif is_true(sub) or is_false(sub):
                key = (idx, node_id, "flip")
                if key in seen:
                    continue
                seen.add(key)  # type: ignore[arg-type]
                r = _flip_literal(assertions, idx, node_id, sub)
                if r:
                    results.append(r)

            # negate a plain bool variable
            elif is_bool(sub) and not sub.children() and node_id not in seen:
                seen.add(node_id)
                r = _negate_var(assertions, idx, node_id, sub)
                if r:
                    results.append(r)

    return results


def _mutate_connective(assertions, assertion_idx, node_id, original_op, alt_name, alt_fn, original_node):
    new_a = replace_operator_by_id(assertions[assertion_idx], node_id, alt_fn)
    repaired = list(assertions)
    repaired[assertion_idx] = new_a

    if not _quick_sat(repaired):
        return None

    return {
        "strategy":    "replace_boolean",
        "description": f"assertion #{assertion_idx + 1}: '{original_op}' → '{alt_name}'",
        "detail": {
            "assertion_index": assertion_idx,
            "original_op":     original_op,
            "new_op":          alt_name,
            "original_subterm":str(original_node),
            "new_assertion":   str(new_a),
        },
        "assertions": repaired,
    }


def _flip_literal(assertions, assertion_idx, node_id, literal):
    """Flip True → False or False → True."""
    replacement = BoolVal(False) if is_true(literal) else BoolVal(True)
    old_name = "True" if is_true(literal) else "False"
    new_name = "False" if is_true(literal) else "True"

    new_a = replace_node_by_id(assertions[assertion_idx], node_id, replacement)
    repaired = list(assertions)
    repaired[assertion_idx] = new_a

    if not _quick_sat(repaired):
        return None

    return {
        "strategy":    "replace_boolean",
        "description": f"assertion #{assertion_idx + 1}: flip literal {old_name} → {new_name}",
        "detail": {
            "assertion_index":  assertion_idx,
            "original_literal": old_name,
            "new_literal":      new_name,
        },
        "assertions": repaired,
    }


def _negate_var(assertions, assertion_idx, node_id, var):
    """Replace boolean variable p with Not(p)."""
    new_a = replace_node_by_id(assertions[assertion_idx], node_id, Not(var))
    repaired = list(assertions)
    repaired[assertion_idx] = new_a

    if not _quick_sat(repaired):
        return None

    return {
        "strategy":    "replace_boolean",
        "description": f"assertion #{assertion_idx + 1}: negate var '{var}'",
        "detail": {
            "assertion_index": assertion_idx,
            "original_var":    str(var),
            "new_subterm":     f"Not({var})",
        },
        "assertions": repaired,
    }


def _quick_sat(assertions):
    # slightly different from _sat_check in delete_subformula — same idea
    if not assertions:
        return True
    s = Solver()
    s.add(*assertions)
    return s.check() == sat
