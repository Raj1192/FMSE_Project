# Repair scoring and ranking.
#
# Basic idea: prefer repairs that change as little as possible.
# Constant fixes are cheapest, deletions are last resort.
# When scores tie, prefer later assertions (more likely to be the derived
# value / result) and smaller % changes.


# Lower penalty = better. Deletion is most destructive so gets the worst score.
# TODO: might be worth making these weights configurable via CLI
STRATEGY_PENALTY = {
    "replace_constant":  -10,
    "replace_bitvector": -15,
    "replace_boolean":   -20,
    "replace_operator":  -30,
    "combined_repair":   -40,
    "delete_subformula": -50,
}


def score_repair(repair, original):
    """Score a repair candidate. Higher = better."""
    score = 0.0
    strategy = repair.get("strategy", "delete_subformula")
    repaired = repair["assertions"]

    # base penalty by strategy type
    score += STRATEGY_PENALTY.get(strategy, -50)

    # penalise number of changed assertions
    if len(repaired) == len(original):
        n_changed = sum(1 for o, r in zip(original, repaired) if str(o) != str(r))
        score -= n_changed * 5
    else:
        score -= abs(len(original) - len(repaired)) * 10

    # for constant repairs, penalise large deviations
    if strategy in ("replace_constant", "replace_bitvector"):
        dev = _constant_deviation(repair)
        if dev is not None:
            score -= dev * 0.01

    # sub-penalties inside delete_subformula
    detail = repair.get("detail", {})
    action = detail.get("action", "")
    if action == "delete_assertion":
        score -= 20
    elif action == "weaken_to_true":
        score -= 10
    elif action == "replace_subterm":
        score -= 5

    # combined repairs get a small bonus since they fix more
    if strategy == "combined_repair":
        score += 15

    # tiebreakers for constant repairs
    if strategy in ("replace_constant", "replace_bitvector") and len(repaired) == len(original):
        changed_idx = _changed_index(original, repaired)

        if changed_idx is not None:
            # prefer later assertion index — derived values are more likely the bug
            position_bonus = (changed_idx / max(len(original) - 1, 1)) * 0.1
            score += position_bonus

            # prefer constants that appear in fewer assertions (more isolated)
            # the 0.05 / appearances bonus is a bit arbitrary tbh,
            # but it correctly ranks the budget.smt2 case so keeping it
            old_val = detail.get("old_constant", "")
            if old_val:
                try:
                    appearances = sum(1 for a in original if old_val.split()[0] in str(a))
                    score += 0.05 / max(appearances, 1)
                except Exception:
                    pass

            # prefer smaller percentage change
            try:
                old_f = float(detail.get("old_constant", "0").split()[0])
                new_f = float(detail.get("new_constant", "0").split()[0])
                if old_f != 0:
                    pct = abs(new_f - old_f) / abs(old_f)
                    score += max(0, 0.03 * (1 - pct))
            except Exception:
                pass

    return score


def _changed_index(original, repaired):
    changed = [i for i, (o, r) in enumerate(zip(original, repaired)) if str(o) != str(r)]
    return changed[0] if len(changed) == 1 else None


def rank_repairs(repairs, original):
    scored = [(r, score_repair(r, original)) for r in repairs]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in scored]


def _constant_deviation(repair):
    detail = repair.get("detail", {})
    try:
        old = float(detail.get("old_constant", "").split()[0])
        new = float(detail.get("new_constant", "").split()[0])
        return abs(new - old)
    except Exception:
        return None


def explain_score(repair, original):
    score = score_repair(repair, original)
    strategy = repair.get("strategy", "?")
    repaired = repair["assertions"]

    if len(repaired) == len(original):
        n = sum(1 for o, r in zip(original, repaired) if str(o) != str(r))
    else:
        n = abs(len(original) - len(repaired))

    dev = _constant_deviation(repair)
    dev_str = f", dev={dev:.0f}" if dev is not None else ""

    idx = _changed_index(original, repaired) if len(repaired) == len(original) else None
    idx_str = f", a#{idx+1}" if idx is not None else ""

    return f"score={score:.2f} [{strategy}, changed={n}{dev_str}{idx_str}]"
