"""
UNSAT core extraction using Z3's assert_and_track.

We only repair assertions that are actually in the UNSAT core — no point
touching anything outside the minimal conflicting set.
"""
# spent a while figuring out assert_and_track — it barely shows up in the Z3 docs.
# tried the subset-checking approach first (exponential, obviously bad),
# then found assert_and_track in a stack overflow answer about proof generation.

from z3 import Bool, Solver, unsat


def get_unsat_core(assertions):
    """
    Returns (is_unsat, core_indices).
    core_indices is the list of 0-based assertion indices in the minimal
    conflicting subset, empty if the formula is SAT.
    """
    if not assertions:
        return False, []

    s = Solver()

    trackers = []
    for i, assertion in enumerate(assertions):
        label = Bool(f"__track_{i}__")
        trackers.append((i, label))
        s.assert_and_track(assertion, label)

    result = s.check()

    if result != unsat:
        return False, []

    core_labels = {str(label) for label in s.unsat_core()}

    # str() comparison because Z3 Bool == doesn't work reliably across solver instances
    core_indices = [
        i for i, label in trackers
        if str(label) in core_labels
    ]

    return True, core_indices


def check_sat(assertions):
    """Quick SAT/UNSAT/unknown check without core tracking."""
    if not assertions:
        return 'sat'
    s = Solver()
    for a in assertions:
        s.add(a)
    return str(s.check())
