"""
Strategy: delete or weaken assertions in the UNSAT core.

Three approaches tried in order: delete an assertion entirely,
replace it with True (vacuously satisfied), or replace a boolean
subterm with True/False. Last resort — scorer ranks these lowest.
"""

from z3 import BoolVal, is_bool, Solver, sat

from smt_repair.ast_utils import collect_subexpressions, replace_node_by_id


def strategy_delete_subformula(assertions, core_indices):
    results = []
    results += _delete_assertions(assertions, core_indices)
    results += _weaken_assertions(assertions, core_indices)
    results += _replace_bool_subterms(assertions, core_indices)
    return results


def _delete_assertions(assertions, core_indices):
    results = []
    for idx in core_indices:
        remaining = [a for i, a in enumerate(assertions) if i != idx]
        if _sat_check(remaining):
            results.append({
                "strategy":    "delete_subformula",
                "description": f"Delete assertion #{idx + 1}: {assertions[idx]}",
                "detail": {
                    "action":          "delete_assertion",
                    "assertion_index": idx,
                    "deleted":         str(assertions[idx]),
                },
                "assertions": remaining,
            })
    return results


# "weaken to True" is basically admitting defeat on that assertion.
# it always produces SAT but it's not a useful repair — that's why
# the scorer penalises it heavily. kept it because it's a valid last resort
# and sometimes the delete strategy misses things _weaken catches.
def _weaken_assertions(assertions, core_indices):
    results = []
    for idx in core_indices:
        repaired = list(assertions)
        repaired[idx] = BoolVal(True)
        if _sat_check(repaired):
            results.append({
                "strategy":    "delete_subformula",
                "description": f"Weaken assertion #{idx + 1} to True (original: {assertions[idx]})",
                "detail": {
                    "action":          "weaken_to_true",
                    "assertion_index": idx,
                    "original":        str(assertions[idx]),
                },
                "assertions": repaired,
            })
    return results


def _replace_bool_subterms(assertions, core_indices):
    results = []
    seen = set()

    for idx in core_indices:
        for sub in collect_subexpressions(assertions[idx]):
            if not is_bool(sub):
                continue
            if sub.get_id() == assertions[idx].get_id():
                continue
            if not sub.children():
                continue

            node_id = sub.get_id()

            for replacement, rep_name in [(BoolVal(True), "True"), (BoolVal(False), "False")]:
                key = (idx, node_id, rep_name)
                if key in seen:
                    continue
                seen.add(key)

                new_a = replace_node_by_id(assertions[idx], node_id, replacement)
                repaired = list(assertions)
                repaired[idx] = new_a

                if _sat_check(repaired):
                    results.append({
                        "strategy":    "delete_subformula",
                        "description": f"assertion #{idx + 1}: replace '{sub}' → {rep_name}",
                        "detail": {
                            "action":           "replace_subterm",
                            "assertion_index":  idx,
                            "original_subterm": str(sub),
                            "replacement":      rep_name,
                        },
                        "assertions": repaired,
                    })

    return results


def _sat_check(assertions):
    if not assertions:
        return True
    solver = Solver()
    for a in assertions:
        solver.add(a)
    return solver.check() == sat
