"""
Combine multiple single-assertion repairs into a joint fix.

Some formulas have more than one bug at once — fixing assertion #3 still
leaves the formula UNSAT because assertion #6 is also wrong. This module
handles that case in two ways:
  - pairwise combination of existing base repairs (fast)
  - iterative multi-core repair (handles harder cases)

# TODO: might be worth limiting max_rounds more aggressively on large formulas,
# the iterative path can get slow when there are many partial repairs in play.
"""

from z3 import (
    BoolRef, Int, Real, IntVal, RealVal, Bool,
    Optimize, Solver, Abs, sat, unsat,
    is_int_value, is_rational_value,
    substitute,
)
from itertools import combinations

from smt_repair.unsat_core import get_unsat_core
from smt_repair.ast_utils import (
    collect_numeric_constants,
    collect_operator_nodes,
    replace_operator_by_id,
)

def strategy_combine_repairs(
    base_repairs,
    original_assertions,
    max_base: int = 30,
    max_rounds: int = 4,
):
    results = []
    seen = set()

    pair_results = _combine_base_repairs(
        base_repairs, original_assertions, max_base, seen
    )
    results.extend(pair_results)

    iterative_results = _iterative_multicore_repair(
        original_assertions, max_rounds, seen
    )
    results.extend(iterative_results)

    return results

def _combine_base_repairs(base_repairs, original, max_base, seen):
    results = []
    candidates = base_repairs[:max_base]

    touched = [_get_touched_index(r, original) for r in candidates]

    for i, j in combinations(range(len(candidates)), 2):
        ti, tj = touched[i], touched[j]
        if ti is None or tj is None or ti == tj:
            continue  # same assertion index = would overwrite each other

        merged = _apply_two_repairs(
            candidates[i], candidates[j], ti, tj, original
        )
        if merged is None:
            continue

        key = tuple(str(a) for a in merged)
        if key in seen:
            continue
        seen.add(key)

        if not _is_sat(merged):
            continue

        results.append({
            "strategy": "combined_repair",
            "description": (
                f"Combined 2 repairs: "
                f"[{candidates[i]['description']}] + "
                f"[{candidates[j]['description']}]"
            ),
            "detail": {
                "num_combined": 2,
                "base_strategies": [candidates[i]["strategy"], candidates[j]["strategy"]],
                "individual_repairs": [
                    candidates[i]["description"],
                    candidates[j]["description"],
                ],
            },
            "assertions": merged,
        })

    return results

def _apply_two_repairs(r1, r2, idx1, idx2, original):
    merged = list(original)
    if idx1 < len(r1["assertions"]):
        merged[idx1] = r1["assertions"][idx1]
    else:
        return None
    if idx2 < len(r2["assertions"]):
        merged[idx2] = r2["assertions"][idx2]
    else:
        return None
    return merged

# originally tried BFS here (expanding all partial repairs at each level)
# but it blew up on formulas with 4+ core assertions — too many branches.
# switched to DFS with a frontier cap, much more manageable.
#
# the BFS version looked roughly like:
#   queue = deque([(original, [])])
#   while queue:
#       current, log = queue.popleft()
#       for partial in _generate_partial_repairs(current, core_idxs):
#           queue.append((partial["assertions"], log + [partial]))
# ...you can see why it got slow.
def _iterative_multicore_repair(original, max_rounds, seen):
    results = []

    initial_state = (list(original), [])  # (current_assertions, repair_log)
    frontier = [initial_state]

    for _ in range(max_rounds):
        next_frontier = []

        for current, repair_log in frontier:
            if len(repair_log) == 0:
                continue  # skip the initial state itself

            key = tuple(str(a) for a in current)
            if key in seen:
                continue

            if _is_sat(current):
                seen.add(key)
                if len(repair_log) >= 2:  # only report multi-repairs
                    results.append({
                        "strategy": "combined_repair",
                        "description": f"Multi-fault repair ({len(repair_log)} fixes): " + " | ".join(r["description"] for r in repair_log),
                        "detail": {
                            "num_combined": len(repair_log),
                            "base_strategies": [r["strategy"] for r in repair_log],
                            "individual_repairs": [r["description"] for r in repair_log],
                        },
                        "assertions": current,
                    })
                continue

            # Still UNSAT — find next core and generate partial repairs
            _, core_idxs = get_unsat_core(current)
            if not core_idxs:
                continue

            for partial in _generate_partial_repairs(current, core_idxs):
                next_frontier.append(
                    (partial["assertions"],
                     repair_log + [partial])
                )

        # Also seed next round from the original (first round)
        if not frontier or (len(frontier) == 1 and not frontier[0][1]):
            _, core_idxs = get_unsat_core(original)
            if core_idxs:
                for partial in _generate_partial_repairs(original, core_idxs):
                    next_frontier.append(([*original], [partial]))
                    # immediately apply the partial repair
                    applied = list(original)
                    idx = partial.get("assertion_index")
                    if idx is not None and idx < len(applied):
                        applied[idx] = partial["assertions"][idx]
                    next_frontier[-1] = (applied, [partial])

        # print(f"round {_}: frontier={len(next_frontier)}, found={len(results)}")
        frontier = next_frontier[:20]  # cap branching factor

    return results

def _generate_partial_repairs(assertions, core_indices):
    # fixes that change one assertion, even if whole formula is still UNSAT
    partials = []
    visited = set()

    for idx in core_indices:
        # Try constant replacement for this assertion
        for const in collect_numeric_constants(assertions[idx]):
            key = (idx, str(const))
            if key in visited:
                continue
            visited.add(key)

            partial = _partial_replace_constant(assertions, idx, const)
            if partial:
                partials.append(partial)

        # Try operator mutation for this assertion
        for node, op_type in collect_operator_nodes(assertions[idx]):
            node_id = node.get_id()
            key = (idx, node_id)
            if key in visited:
                continue
            visited.add(key)

            for partial in _partial_replace_operator(assertions, idx, node_id, op_type):
                partials.append(partial)

    return partials[:10]  # 10 felt right from testing; higher values slow things down a lot

def _partial_replace_constant(assertions, assertion_idx, const):
    if is_int_value(const):
        changed = Int("__prc__")
        old_val = const.as_long()
    elif is_rational_value(const):
        changed = Real("__prc__")
        old_val = float(const.as_fraction())
    else:
        return None

    # Substitute only in the target assertion
    new_target = substitute(assertions[assertion_idx], [(const, changed)])

    opt = Optimize()
    opt.add(new_target)
    opt.minimize(Abs(changed - old_val))

    if opt.check() != sat:
        return None

    m = opt.model()
    val = m[changed]
    if val is None:
        return None

    if is_int_value(const):
        new_const = IntVal(val.as_long())
        new_val_str = str(val.as_long())
    else:
        new_const = RealVal(str(val))
        new_val_str = str(val)

    repaired = list(assertions)
    repaired[assertion_idx] = substitute(
        assertions[assertion_idx], [(const, new_const)]
    )

    return {
        "strategy": "partial_replace_constant",
        "description": f"assertion #{assertion_idx+1}: const {old_val} → {new_val_str}",
        "assertion_index": assertion_idx,
        "assertions": repaired,
    }

def _partial_replace_operator(assertions, assertion_idx, node_id, op_type):
    from smt_repair.strategies.replace_operator import _get_alternatives

    node_expr = None
    from smt_repair.ast_utils import collect_subexpressions
    for sub in collect_subexpressions(assertions[assertion_idx]):
        if sub.get_id() == node_id:
            node_expr = sub
            break

    if node_expr is None:
        return []

    children = node_expr.children()
    if len(children) < 2:
        return []

    results = []
    for alt_name, alt_fn in _get_alternatives(op_type, children):
        try:
            new_assertion = replace_operator_by_id(
                assertions[assertion_idx], node_id, alt_fn
            )
        except Exception:
            continue

        repaired = list(assertions)
        repaired[assertion_idx] = new_assertion

        results.append({
            "strategy": "partial_replace_operator",
            "description": (
                f"assertion #{assertion_idx+1}: op {op_type} → {alt_name}"
            ),
            "assertion_index": assertion_idx,
            "assertions": repaired,
        })

    return results[:3]  # limit alternatives per node

def _get_touched_index(repair, original):
    repaired = repair["assertions"]
    if len(repaired) != len(original):
        return None
    changed = [
        i for i, (o, r) in enumerate(zip(original, repaired))
        if str(o) != str(r)
    ]
    return changed[0] if len(changed) == 1 else None

def _is_sat(assertions):
    if not assertions:
        return True
    s = Solver()
    for a in assertions:
        s.add(a)
    return s.check() == sat
