"""
Strategy: mutate arithmetic/comparison operators in the UNSAT core.

Tries semantically similar alternatives for each operator — e.g. < → <=, = → >=.
Only operators with a meaningful relationship are considered (no random swaps).
"""

from z3 import (
    BoolRef, ExprRef,
    is_add, is_sub, is_mul,
    is_lt, is_le, is_gt, is_ge,
    Solver, sat
)

from smt_repair.ast_utils import (
    collect_operator_nodes,
    replace_operator_by_id,
    is_eq_op,
)


def _arith_alternatives(op_type, children):
    """Arithmetic operator alternatives. Skipping / due to int division weirdness."""
    table = {
        "add": [("-", lambda x, y: x - y), ("*", lambda x, y: x * y)],
        "sub": [("+", lambda x, y: x + y), ("*", lambda x, y: x * y)],
        "mul": [("+", lambda x, y: x + y), ("-", lambda x, y: x - y)],
    }
    return table.get(op_type, [])


def _compare_alternatives(op_type, children):
    """Comparison alternatives, ordered closest-first."""
    table = {
        "lt": [("<=", lambda x, y: x <= y), ("=",  lambda x, y: x == y),
               (">=", lambda x, y: x >= y), (">",  lambda x, y: x > y)],
        "le": [("<",  lambda x, y: x < y),  ("=",  lambda x, y: x == y),
               (">=", lambda x, y: x >= y), (">",  lambda x, y: x > y)],
        "gt": [(">=", lambda x, y: x >= y), ("=",  lambda x, y: x == y),
               ("<=", lambda x, y: x <= y), ("<",  lambda x, y: x < y)],
        "ge": [(">",  lambda x, y: x > y),  ("=",  lambda x, y: x == y),
               ("<=", lambda x, y: x <= y), ("<",  lambda x, y: x < y)],
        "eq": [("<=", lambda x, y: x <= y), (">=", lambda x, y: x >= y)],
    }
    return table.get(op_type, [])


def _get_alternatives(op_type, children):
    return _arith_alternatives(op_type, children) + _compare_alternatives(op_type, children)


def strategy_replace_operator(assertions, core_indices):
    results = []
    visited = set()

    for idx in core_indices:
        for node, op_type in collect_operator_nodes(assertions[idx]):
            node_id = node.get_id()
            if node_id in visited:
                continue
            visited.add(node_id)

            children = node.children()
            if len(children) < 2:
                continue

            # skip Bool-typed operands — comparison ops don't apply to Bool
            # found this the hard way: Z3 throws a weird internal error, not a
            # clean Python exception, so the try/except in _apply_bv_op doesn't catch it
            from z3 import is_bool
            if any(is_bool(c) for c in children[:2]):
                continue

            for alt_name, alt_fn in _get_alternatives(op_type, children):
                r = _apply_op_mutation(assertions, idx, node_id, alt_name, alt_fn, op_type)
                if r is not None:
                    results.append(r)

    return results


def _apply_op_mutation(assertions, assertion_idx, node_id, alt_name, alt_fn, original_op):
    """Apply one operator mutation and return the repair if it yields SAT."""
    new_assertion = replace_operator_by_id(assertions[assertion_idx], node_id, alt_fn)

    repaired = list(assertions)
    repaired[assertion_idx] = new_assertion

    s = Solver()
    for a in repaired:
        s.add(a)
    if s.check() != sat:
        return None

    return {
        "strategy":    "replace_operator",
        "description": f"assertion #{assertion_idx + 1}: '{original_op}' → '{alt_name}'",
        "detail": {
            "assertion_index":    assertion_idx,
            "original_op":        original_op,
            "new_op":             alt_name,
            "original_assertion": str(assertions[assertion_idx]),
            "new_assertion":      str(new_assertion),
        },
        "assertions": repaired,
    }
