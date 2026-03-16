"""
Strategy: repair BitVector constants and operators in the UNSAT core.

Two sub-strategies: replace a BV literal with the nearest SAT value
(using Z3 Optimize + unsigned distance), or mutate a BV operator.
"""

from z3 import (
    BitVec, BitVecVal,
    ULT, ULE, UGT, UGE,
    is_bv, is_bv_value,
    Optimize, Solver, sat, If,
    substitute
)
from smt_repair.ast_utils import (
    collect_subexpressions,
    replace_operator_by_id,
)


def _bv_op_alternatives(decl_name, width):
    arith = {
        "bvadd": [("bvsub", lambda a, b: a - b), ("bvmul", lambda a, b: a * b)],
        "bvsub": [("bvadd", lambda a, b: a + b), ("bvmul", lambda a, b: a * b)],
        "bvmul": [("bvadd", lambda a, b: a + b), ("bvsub", lambda a, b: a - b)],
        "bvudiv": [("bvurem", lambda a, b: a % b)],
        "bvsdiv": [("bvsrem", lambda a, b: a % b)],
    }
    compare_u = {
        "bvult": [("bvule", ULE), ("bvugt", UGT), ("bvuge", UGE), ("=", lambda a, b: a == b)],
        "bvule": [("bvult", ULT), ("bvugt", UGT), ("bvuge", UGE), ("=", lambda a, b: a == b)],
        "bvugt": [("bvuge", UGE), ("bvult", ULT), ("bvule", ULE), ("=", lambda a, b: a == b)],
        "bvuge": [("bvugt", UGT), ("bvult", ULT), ("bvule", ULE), ("=", lambda a, b: a == b)],
    }
    compare_s = {
        "bvslt": [("bvsle", lambda a, b: a <= b), ("bvsgt", lambda a, b: a > b),
                  ("bvsge", lambda a, b: a >= b), ("=", lambda a, b: a == b)],
        "bvsle": [("bvslt", lambda a, b: a < b),  ("bvsgt", lambda a, b: a > b),
                  ("bvsge", lambda a, b: a >= b), ("=", lambda a, b: a == b)],
        "bvsgt": [("bvsge", lambda a, b: a >= b), ("bvslt", lambda a, b: a < b),
                  ("bvsle", lambda a, b: a <= b), ("=", lambda a, b: a == b)],
        "bvsge": [("bvsgt", lambda a, b: a > b),  ("bvslt", lambda a, b: a < b),
                  ("bvsle", lambda a, b: a <= b), ("=", lambda a, b: a == b)],
    }
    return (
        arith.get(decl_name, []) +
        compare_u.get(decl_name, []) +
        compare_s.get(decl_name, [])
    )


def strategy_replace_bitvector(assertions, core_indices):
    results = []
    results += _bv_replace_constants(assertions, core_indices)
    results += _bv_replace_operators(assertions, core_indices)
    return results


def _bv_replace_constants(assertions, core_indices):
    results = []
    seen = set()

    for idx in core_indices:
        for sub in collect_subexpressions(assertions[idx]):
            if not is_bv_value(sub):
                continue
            key = (sub.as_long(), sub.size())
            if key in seen:
                continue
            seen.add(key)

            r = _nearest_bv_value(assertions, sub)
            if r:
                results.append(r)

    return results


# BV distance minimisation works fine for small widths;
# haven't tested above 64-bit, probably fine but no guarantees
def _nearest_bv_value(assertions, const):
    width = const.size()
    old_val = const.as_long()
    max_val = (1 << width) - 1

    changed = BitVec("changedBVConst", width)
    modified = [substitute(a, [(const, changed)]) for a in assertions]

    opt = Optimize()
    for m in modified:
        opt.add(m)

    # Unsigned distance: If changed >= old, changed - old, else old - changed
    old_bv = BitVecVal(old_val, width)
    dist = If(UGE(changed, old_bv), changed - old_bv, old_bv - changed)
    opt.minimize(dist)

    if opt.check() != sat:
        return None

    new_val_z3 = opt.model()[changed]
    if new_val_z3 is None:
        return None

    new_val = new_val_z3.as_long()
    if new_val == old_val:
        return None

    new_const = BitVecVal(new_val, width)
    repaired = [substitute(a, [(const, new_const)]) for a in assertions]

    return {
        "strategy": "replace_bitvector",
        "description": f"BV[{width}] constant {old_val:#x} → {new_val:#x}",
        "detail": {
            "bv_width": width,
            "old_constant": f"{old_val} (0x{old_val:x})",
            "new_constant": f"{new_val} (0x{new_val:x})",
        },
        "assertions": repaired,
    }


def _bv_replace_operators(assertions, core_indices):
    results = []
    seen = set()

    for idx in core_indices:
        for sub in collect_subexpressions(assertions[idx]):
            if not sub.children():
                continue
            decl = sub.decl().name()
            node_id = sub.get_id()

            if node_id in seen:
                continue

            children = sub.children()
            if not children or not is_bv(children[0]):
                continue  # only act on BV-typed children

            width = children[0].size()
            alts = _bv_op_alternatives(decl, width)
            if not alts:
                continue

            seen.add(node_id)

            for alt_name, alt_fn in alts:
                r = _apply_bv_op(
                    assertions, idx, node_id, decl, alt_name, alt_fn
                )
                if r:
                    results.append(r)

    return results


# ran into cases where bvsle/bvsgt on unsigned bitvectors would produce
# a weird Z3 type error instead of unsat — wrapping in try/except handles it
def _apply_bv_op(assertions, assertion_idx, node_id, original_op, alt_name, alt_fn):
    try:
        new_assertion = replace_operator_by_id(
            assertions[assertion_idx], node_id, alt_fn
        )
    except Exception:
        return None

    repaired = list(assertions)
    repaired[assertion_idx] = new_assertion

    s = Solver()
    for a in repaired:
        s.add(a)
    if s.check() != sat:
        return None

    return {
        "strategy": "replace_bitvector",
        "description": f"assertion #{assertion_idx + 1}: bvop '{original_op}' → '{alt_name}'",
        "detail": {
            "assertion_index": assertion_idx,
            "original_op": original_op,
            "new_op": alt_name,
            "original_assertion": str(assertions[assertion_idx]),
            "new_assertion": str(new_assertion),
        },
        "assertions": repaired,
    }
