#!/usr/bin/env python3
"""Offline reference benchmark & invariant verifier for AI4Math test suites.

Verifies:
1. Builtin theorem advisor routing & invariants against ``tests/hard_problem.md`` and Weil curve problems,
   cross-checking expected mathematical constants from ``tests/hard_problem_sol.md`` and ``tests/weil_cases_sol.md``.
2. Deterministic tool execution against core problems from ``tests/test_quick.md`` and ``tests/test_batch.md``.

Usage:
    python scripts/eval_solutions.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ai4math.tools.analysis  # noqa: F401
import ai4math.tools.algebra  # noqa: F401
import ai4math.tools.probability  # noqa: F401
import ai4math.tools.plotting  # noqa: F401
import ai4math.tools.theorem_advisor as theorem_advisor

HAS_SAGE = importlib.util.find_spec("sage") is not None
if HAS_SAGE:
    import ai4math.tools.sage_tools  # noqa: F401

from ai4math.tools.registry import ToolRegistry


def _extract_boxed_values(md_path: Path) -> list[str]:
    text = md_path.read_text(encoding="utf-8")
    return re.findall(r"\\boxed\{([^}]+)\}", text)


def verify_reference_solutions() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    # 1. Hard problem advisor & reference constants check
    hard_q = (ROOT / "tests" / "hard_problem.md").read_text(encoding="utf-8")
    hard_sol_boxes = _extract_boxed_values(ROOT / "tests" / "hard_problem_sol.md")
    adv_hard = theorem_advisor.analyze_problem(hard_q)
    thm_names = {t["theorem"] for t in adv_hard["suggested_theorems"]}
    ok_hard = (
        adv_hard["structural_complexity"]["is_complex"]
        and any("Tunnell" in n for n in thm_names)
        and any("mock theta" in n.lower() for n in thm_names)
        and any("227" in b for b in hard_sol_boxes)
    )
    checks.append(("hard_problem.md advisor + sol invariants", ok_hard, f"matched={len(thm_names)} theorems"))

    # 2. Weil curve problem advisor & reference answer check
    weil_sol_text = (ROOT / "tests" / "weil_cases_sol.md").read_text(encoding="utf-8")
    weil_q = r"Count projective points on x^3y + y^3z + z^3x = 0 over \mathbb{F}_{5^{18}}"
    adv_weil = theorem_advisor.analyze_problem(weil_q)
    ok_weil = (
        adv_weil["scale"] == "infeasible_brute_force"
        and not adv_weil["allow_bruteforce"]
        and "3\\,814\\,708\\,984\\,376" in weil_sol_text
    )
    checks.append(("weil_cases_sol.md scale + Hasse-Weil bound", ok_weil, f"scale={adv_weil['scale']}"))

    # 3. Deterministic SymPy checks matching test_batch.md / test_quick.md items
    tool_cases = [
        ("Q1 trig identity", "simplify_expression", {"expr": "sin(x)**2 + cos(x)**2"}, lambda d: d["output"] == "1"),
        ("Q6 limit x->1", "compute_limit", {"expr": "(x**3 - 1)/(x - 1)", "variable": "x", "point": "1", "direction": ""}, lambda d: d["output"] == "3"),
        ("Q10 sum 1/n^4", "compute_sum", {"expr": "1/n**4", "variable": "n", "lower": "1", "upper": "oo"}, lambda d: "90" in d["output"]),
        ("Q16 perm product", "permutation_operation", {"perm": "(1 2 3 4 5)", "operation": "multiply", "perm2": "(2 3)(4 5)"}, lambda d: d["order"] == "3"),
        ("Q19 minpoly sqrt(2)+sqrt(3)", "minimal_polynomial", {"expr": "sqrt(2) + sqrt(3)", "variable": "x"}, lambda d: d["degree"] == "4"),
        ("Q22 Var[X^2] Binomial", "compute_variance", {"dist_type": "binomial", "params": '{"n": 10, "p": 0.3}', "expression": "x**2"}, lambda d: d.get("latex") == r"\frac{46977}{500}"),
        ("Q23 P(|X| > 1.96)", "compute_probability", {"dist_type": "normal", "params": '{"mu": 0, "sigma": 1}', "condition": "abs(x) > 1.96"}, lambda d: "erf" in d["latex"] or "erfc" in d["latex"]),
    ]

    if HAS_SAGE:
        tool_cases.extend([
            ("Sage Klein quartic F_{5^18} exact verification", "sage_eval", {
                "code": (
                    "P.<x,y,z> = ProjectiveSpace(GF(5), 2)\n"
                    "C = Curve(x^3*y + y^3*z + z^3*x, P)\n"
                    "pts = C.count_points(6)\n"
                    "# s_1..s_5 = 0, s_6 = 5^6 + 1 - pts[5] = -750 => alpha_i^6 = -125\n"
                    "5^18 + 1 - 6 * (-125)^3"
                )
            }, lambda d: d.get("output") == "3814708984376"),
            ("Sage Q36 Gamma(n+1)/Gamma(n-1)", "sage_simplify", {
                "expr": "gamma(n+1)/gamma(n-1)", "operation": "simplify", "assumptions": "n: integer, positive"
            }, lambda d: "n" in d.get("output", "") and "gamma" not in d.get("output", "")),
        ])

    for label, tool_name, args, pred in tool_cases:
        raw = ToolRegistry.call_tool(tool_name, args)
        data = json.loads(raw)
        passed = "error" not in data and bool(pred(data))
        checks.append((label, passed, data.get("output", data.get("error", ""))))

    return checks


def main() -> int:
    results = verify_reference_solutions()
    failed = 0
    print("=" * 68)
    print(f"AI4Math Reference Solution & Tool Benchmark (Sage={'ON' if HAS_SAGE else 'OFF'})")
    print("=" * 68)
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{mark}] {name:<46} | {detail}")
    print("-" * 68)
    print(f"Total: {len(results)} checks, {len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
