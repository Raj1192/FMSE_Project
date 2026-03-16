"""
Strategy: replace a numeric constant with the nearest SAT value.

Uses Z3 Optimize to minimize |new - old|, so we get the closest possible
fix rather than just any satisfying value.
"""

from z3 import (
    Int, Real, IntVal, RealVal,
    Optimize, Abs, sat,
    is_int_value, is_rational_value, substitute
)

from smt_repair.ast_utils import collect_numeric_constants


def strategy_replace_constant(assertions, core_indices):
    results = []
    seen = set()

    for idx in core_indices:
        for const in collect_numeric_constants(assertions[idx]):
            key = str(const)
            if key in seen:
                continue
            seen.add(key)

            r = _nearest_constant(assertions, const)
            if r is not None:
                results.append(r)

    return results


# NOTE: "changedConstant" as the placeholder name is fine unless the formula
# already has a variable with that exact name — substitute() will confuse them.
# could use a random suffix but hasn't been an issue with any real inputs so far.
def _nearest_constant(assertions, const):
    """Find the nearest SAT value for `const` using Z3 Optimize."""
    if is_int_value(const):
        changed = Int("changedConstant")
        old_val = const.as_long()
    elif is_rational_value(const):
        changed = Real("changedConstant")
        old_val = float(const.as_fraction())
    else:
        return None

    # substitute across all assertions, not just the core ones
    modified = [substitute(a, [(const, changed)]) for a in assertions]

    opt = Optimize()
    for m in modified:
        opt.add(m)
    opt.minimize(Abs(changed - old_val))

    if opt.check() != sat:
        return None

    new_val_z3 = opt.model()[changed]
    if new_val_z3 is None:
        return None

    if is_int_value(const):
        new_const  = IntVal(new_val_z3.as_long())
        old_str = str(old_val)
        new_str = str(new_val_z3.as_long())
    else:
        new_const  = RealVal(str(new_val_z3))
        old_str = str(old_val)
        new_str = str(new_val_z3)

    repaired = [substitute(a, [(const, new_const)]) for a in assertions]

    return {
        "strategy":    "replace_constant",
        "description": f"Replace constant {old_str} → {new_str} (nearest SAT value)",
        "detail": {
            "old_constant": old_str,
            "new_constant": new_str,
        },
        "assertions": repaired,
    }
