"""
SMT Repair Orchestrator

Loads assertions, runs one or more repair strategies, combines and
deduplicates results, then returns them ranked by quality score.
"""

from dataclasses import dataclass

from z3 import BoolRef, parse_smt2_string, parse_smt2_file

from smt_repair.unsat_core import get_unsat_core, check_sat
from smt_repair.strategies.replace_constant  import strategy_replace_constant
from smt_repair.strategies.replace_operator  import strategy_replace_operator
from smt_repair.strategies.delete_subformula import strategy_delete_subformula
from smt_repair.strategies.replace_boolean   import strategy_replace_boolean
from smt_repair.strategies.replace_bitvector import strategy_replace_bitvector
from smt_repair.strategies.combine_repairs   import strategy_combine_repairs
from smt_repair.scorer import rank_repairs, score_repair, explain_score


@dataclass
class RepairResult:
    strategy: str
    description: str
    detail: dict
    assertions: list
    score: float = 0.0
    score_explanation: str = ""

    @property
    def smt2_output(self):
        lines = [f"(assert {a})" for a in self.assertions]
        return "\n".join(lines)


class SMTRepair:
    BASE_STRATEGIES = ("replace_constant", "replace_operator", "delete_subformula")
    TYPE_STRATEGIES = ("replace_boolean", "replace_bitvector")
    ALL_STRATEGIES  = BASE_STRATEGIES + TYPE_STRATEGIES

    def __init__(self, verbose=False):
        self.verbose = verbose

    def repair_file(self, path, strategy="all", max_repairs=5, combine=True):
        self._log(f"Reading SMT2 file: {path}")
        assertions = list(parse_smt2_file(path))
        return self._repair(assertions, strategy, max_repairs, combine)

    def repair_string(self, smt2_text, strategy="all", max_repairs=5, combine=True):
        self._log("Parsing inline SMT2 formula...")
        assertions = list(parse_smt2_string(smt2_text))
        return self._repair(assertions, strategy, max_repairs, combine)

    def repair_assertions(self, assertions, strategy="all", max_repairs=5, combine=True):
        """Repair a formula passed in directly as Z3 objects (no file needed)."""
        self._log(f"Received {len(assertions)} dynamic assertion(s).")
        return self._repair(assertions, strategy, max_repairs, combine)

    def _repair(self, assertions, strategy, max_repairs, combine):
        self._log(f"Loaded {len(assertions)} assertion(s).")

        # note: check_sat can return "unknown" on quantified formulas, we bail out
        status = check_sat(assertions)
        if status == "sat":
            self._log("Formula is already SAT -- no repair needed.")
            return []
        if status == "unknown":
            self._log("Solver returned UNKNOWN -- cannot proceed.")
            return []

        self._log("Formula is UNSAT. Computing UNSAT core...")
        _, core_indices = get_unsat_core(assertions)
        if not core_indices:
            self._log("Empty UNSAT core -- cannot localise the error.")
            return []

        self._log(f"UNSAT core: assertions {[f'#{i+1}' for i in core_indices]}")

        if strategy == "all" or strategy == "combine_repairs":
            strategies_to_run = list(self.ALL_STRATEGIES)
        else:
            strategies_to_run = [strategy]

        raw_repairs = []

        for strat in strategies_to_run:
            self._log(f"Running strategy: {strat} ...")
            found = self._run_strategy(strat, assertions, core_indices)
            self._log(f"  -> {len(found)} candidate(s) found.")
            raw_repairs.extend(found)

        # combine partial fixes for multi-bug formulas
        if combine and strategy in ("all", "combine_repairs"):
            self._log("Running strategy: combine_repairs ...")
            combined = strategy_combine_repairs(raw_repairs, assertions)
            self._log(f"  -> {len(combined)} combined repair(s) found.")
            raw_repairs.extend(combined)

        raw_repairs = self._deduplicate(raw_repairs)

        # rank best-first
        self._log("Ranking repairs by quality score...")
        raw_repairs = rank_repairs(raw_repairs, assertions)

        results = []
        for r in raw_repairs[:max_repairs]:
            sc  = score_repair(r, assertions)
            exp = explain_score(r, assertions)
            if self.verbose:
                self._log(f"  {exp}")
            results.append(RepairResult(
                strategy=r["strategy"],
                description=r["description"],
                detail=r.get("detail", {}),
                assertions=r["assertions"],
                score=sc,
                score_explanation=exp,
            ))

        self._log(f"Done. {len(results)} repair(s) returned (limit={max_repairs})")
        return results

    def _run_strategy(self, strategy, assertions, core_indices):
        if strategy == "replace_constant":
            return strategy_replace_constant(assertions, core_indices)
        elif strategy == "replace_operator":
            return strategy_replace_operator(assertions, core_indices)
        elif strategy == "delete_subformula":
            return strategy_delete_subformula(assertions, core_indices)
        elif strategy == "replace_boolean":
            return strategy_replace_boolean(assertions, core_indices)
        elif strategy == "replace_bitvector":
            return strategy_replace_bitvector(assertions, core_indices)
        else:
            raise ValueError(f"Unknown strategy: {strategy!r}")

    # NOTE: dedup by str(assertion) misses semantic equivalents like
    # (x + 1 = 5) vs (1 + x = 5) — hasn't caused visible duplicates in testing
    def _deduplicate(self, repairs):
        seen = set()
        out = []
        for r in repairs:
            key = tuple(str(a) for a in r["assertions"])
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out

    def _log(self, msg):
        if self.verbose:
            print(f"[smt-repair] {msg}")
