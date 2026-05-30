"""Theorem advisor: estimate computational scale and suggest applicable theorems."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from importlib import resources
from typing import Any

from ai4math.tools.registry import math_tool

_THEOREMS_CACHE: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}


def _reset_theorem_cache() -> None:
    _THEOREMS_CACHE.clear()


def _load_json_payload(payload: str) -> list[dict[str, Any]]:
    data = json.loads(payload)
    if isinstance(data, dict):
        entries = data.get("theorems", [])
    elif isinstance(data, list):
        entries = data
    else:
        entries = []
    return [entry for entry in entries if isinstance(entry, dict) and (entry.get("id") or entry.get("name"))]


def _load_builtin_theorems() -> list[dict[str, Any]]:
    theorems_dir = resources.files("ai4math").joinpath("tools", "theorems")
    all_theorems: list[dict[str, Any]] = []
    for item in theorems_dir.iterdir():
        if not item.name.endswith(".json"):
            continue
        try:
            payload = item.read_text(encoding="utf-8")
            all_theorems.extend(_load_json_payload(payload))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return _dedupe_theorems(all_theorems)


def _load_external_theorems(path: str, url: str, timeout: int) -> list[dict[str, Any]]:
    if path:
        with open(path, encoding="utf-8") as f:
            return _load_json_payload(f.read())
    if url:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            charset = response.headers.get_content_charset("utf-8")
            return _load_json_payload(response.read().decode(charset))
    return []


def _dedupe_theorems(theorems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for theorem in theorems:
        key = str(theorem.get("id") or theorem.get("name") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(theorem)
    return deduped


def _load_theorems() -> list[dict[str, Any]]:
    source_mode = os.getenv("AI4MATH_THEOREM_SOURCE", "merge").strip().lower() or "merge"
    if source_mode not in {"builtin", "external", "merge"}:
        source_mode = "merge"
    external_path = os.getenv("AI4MATH_THEOREM_EXTERNAL_PATH", "").strip()
    external_url = os.getenv("AI4MATH_THEOREM_EXTERNAL_URL", "").strip()
    timeout = int(os.getenv("AI4MATH_THEOREM_EXTERNAL_TIMEOUT", "5"))
    cache_key = (source_mode, external_path, external_url, timeout)
    cached = _THEOREMS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    builtin = _load_builtin_theorems()
    external: list[dict[str, Any]] = []
    if source_mode in {"external", "merge"} and (external_path or external_url):
        try:
            external = _load_external_theorems(external_path, external_url, timeout)
        except (OSError, json.JSONDecodeError, urllib.error.URLError, ValueError):
            external = []

    if source_mode == "builtin":
        theorems = builtin
    elif source_mode == "external":
        theorems = external or builtin
    else:
        theorems = _dedupe_theorems([*builtin, *external]) or builtin

    _THEOREMS_CACHE[cache_key] = theorems
    return theorems


_FINITE_FIELD_RE = re.compile(
    r"(?:GF|\\mathbb\{F\}|F|\\mathbb\s*F)\s*[_{\(]\s*(\d+)\s*[\^}\)]\s*\{?\s*(\d+)\s*\}?"
    r"|(?:GF|F)\s*\(\s*(\d+)\s*\^\s*(\d+)\s*\)"
    r"|(?:GF|F)\s*\(\s*(\d+)\s*\)"
    r"|\\mathbb\{F\}_\{(\d+)\^(\d+)\}"
    r"|F_\{(\d+)\^(\d+)\}"
    r"|F_(\d+)"
)
_BRACED_FINITE_FIELD_RE = re.compile(r"(?:F|\\mathbb\{F\})_\{(\d+)\^\{?(\d+)\}?\}")

_POLY_DEGREE_RE = re.compile(r"[xyz]\^(\d+)")
_LARGE_INT_RE = re.compile(r"(\d+)\s*[\^]\s*(\d+)")


def _extract_finite_field(text: str) -> tuple[int, int] | None:
    braced = _BRACED_FINITE_FIELD_RE.search(text)
    if braced:
        return int(braced.group(1)), int(braced.group(2))
    for m in _FINITE_FIELD_RE.finditer(text):
        groups = m.groups()
        for i in range(0, len(groups) - 1, 2):
            if groups[i] and groups[i + 1]:
                return int(groups[i]), int(groups[i + 1])
        if groups[-1]:
            return int(groups[-1]), 1
    for m in _LARGE_INT_RE.finditer(text):
        base, exp = int(m.group(1)), int(m.group(2))
        if 2 <= base <= 100 and exp >= 2:
            return base, exp
    return None


def _estimate_scale(text: str) -> dict[str, Any]:
    info: dict[str, Any] = {}
    ff = _extract_finite_field(text)
    if ff:
        p, n = ff
        q = p ** n
        info["finite_field"] = f"F_{{{p}^{{{n}}}}}"
        info["field_characteristic"] = p
        info["field_extension_degree"] = n
        info["field_size"] = q
        info["field_size_sci"] = f"{q:.2e}"
        if q > 10**9:
            info["scale"] = "infeasible_brute_force"
            info["reason"] = f"|F_{{{p}^{{{n}}}}}| = {q:.2e}，逐点枚举不可行"
        elif q > 10**6:
            info["scale"] = "heavy"
            info["reason"] = f"|F_{{{p}^{{{n}}}}}| = {q:.2e}，直接枚举代价高"
        elif q > 10**3:
            info["scale"] = "moderate"
        else:
            info["scale"] = "trivial"
        return info

    degrees = [int(d) for d in _POLY_DEGREE_RE.findall(text)]
    if degrees:
        max_deg = max(degrees)
        info["max_polynomial_degree"] = max_deg
        if max_deg > 20:
            info["scale"] = "heavy"
            info["reason"] = f"多项式次数 {max_deg}，符号计算可能很慢"
            return info

    info["scale"] = "moderate"
    return info


def _match_theorems(text: str) -> list[dict[str, Any]]:
    theorems = _load_theorems()
    lowered = text.lower()
    scored: list[tuple[float, dict[str, Any]]] = []

    for thm in theorems:
        score = 0.0
        for kw in thm.get("keywords", []):
            if kw.lower() in lowered:
                score += 1.0
        for sig in thm.get("signals", []):
            try:
                if re.search(sig, text, re.IGNORECASE):
                    score += 2.0
            except re.error:
                pass
        if score > 0:
            scored.append((score, thm))

    scored.sort(key=lambda item: -item[0])
    matched: list[dict[str, Any]] = []
    for score, thm in scored[:6]:
        enriched = dict(thm)
        enriched["_match_score"] = score
        matched.append(enriched)
    return matched


def _normalize_confidence(prior: Any, score: float) -> str:
    if isinstance(prior, str) and prior.strip():
        return prior.strip().lower()
    if isinstance(prior, (int, float)):
        if prior >= 0.85:
            return "high"
        if prior >= 0.5:
            return "medium"
        return "low"
    if score >= 4.0:
        return "high"
    if score >= 2.0:
        return "medium"
    return "low"


def _append_unique_strings(target: list[str], values: list[Any]) -> None:
    seen = set(target)
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        target.append(cleaned)
        seen.add(cleaned)


def _suggest_invariants(scale_info: dict[str, Any], matched: list[dict[str, Any]]) -> list[str]:
    invariants: list[str] = []
    if "field_characteristic" in scale_info:
        p = scale_info["field_characteristic"]
        n = scale_info.get("field_extension_degree")
        q = scale_info.get("field_size")
        invariants.append(f"field characteristic p = {p}")
        if n is not None:
            invariants.append(f"extension degree n = {n}")
        if q is not None:
            invariants.append(f"field size q = {q}")
    if "max_polynomial_degree" in scale_info:
        invariants.append(f"max polynomial degree = {scale_info['max_polynomial_degree']}")

    for thm in matched:
        _append_unique_strings(invariants, thm.get("invariant_hints", []))
        _append_unique_strings(invariants, thm.get("prerequisites", []))
    return invariants


def _suggest_verification_checks(matched: list[dict[str, Any]]) -> list[str]:
    checks: list[str] = []
    for thm in matched:
        _append_unique_strings(checks, thm.get("verification_hints", []))
    return checks


_CONSTRAINT_RE = re.compile(
    r"满足|使得|such\s+that|given\s+that|subject\s+to|条件|let\b|define\b|denote\b|suppose\b|assume\b|where\b",
    re.IGNORECASE,
)
_MULTISTEP_RE = re.compile(
    r"进一步|然后|再[求算计]|subsequently|furthermore|compute\b|find\b|determine\b|with\s+this|then\s+compute",
    re.IGNORECASE,
)

_CONSTRUCTIVE_MODULAR_SIGNAL_PATTERNS = (
    r"construct|构造",
    r"harmonic\s+weak\s+maass|weak\s+maass|maass\s+form|调和弱\s*maass",
    r"holomorphic\s+part|holomorphic",
    r"cm\s+point|heegner|复乘点",
    r"hecke\s+translate|hecke",
    r"trace(?:d)?\s+to\s*(?:q|\\mathbb\{q\})|trace",
    r"catalan(?:'s)?\s+constant|catalan|L\(\s*2\s*,\s*chi",
)


def _requires_theory_first_construction(text: str, matched: list[dict[str, Any]]) -> bool:
    signal_count = sum(
        1 for pattern in _CONSTRUCTIVE_MODULAR_SIGNAL_PATTERNS
        if re.search(pattern, text, re.IGNORECASE)
    )
    has_modular_match = any("modular_forms" in thm.get("domains", []) for thm in matched)
    return signal_count >= 3 or (signal_count >= 2 and has_modular_match)


def _assess_structural_complexity(text: str, domain_count: int, matched: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    reasons: list[str] = []
    length = len(text)
    sentences = re.split(r"[。；;.\n]+", text)
    sentence_count = sum(1 for s in sentences if s.strip())
    constraint_count = len(_CONSTRAINT_RE.findall(text))
    multistep_count = len(_MULTISTEP_RE.findall(text))

    if length > 500 or sentence_count > 6:
        reasons.append(f"long problem (length={length}, sentences={sentence_count})")
    if domain_count >= 3:
        reasons.append(f"multi-domain ({domain_count} domains)")
    if constraint_count >= 3:
        reasons.append(f"many constraints ({constraint_count})")
    if multistep_count >= 2:
        reasons.append(f"multi-step ({multistep_count} steps)")
    if _requires_theory_first_construction(text, matched or []):
        reasons.append("constructive modular-form research task")

    return {
        "is_complex": len(reasons) >= 2,
        "reasons": reasons,
        "domain_count": domain_count,
        "constraint_count": constraint_count,
        "length": length,
    }


def analyze_problem(problem: str, detected_objects: str = "") -> dict[str, Any]:
    combined = (problem + " " + detected_objects).strip()
    scale_info = _estimate_scale(combined)
    matched = _match_theorems(combined)

    suggestions = []
    soft_constraints = []
    domains: list[str] = []
    for thm in matched:
        domains.extend(domain for domain in thm.get("domains", []) if isinstance(domain, str))
        score = float(thm.get("_match_score", 0.0))
        confidence = _normalize_confidence(thm.get("confidence"), score)
        preferred_recipe = thm.get("preferred_recipe", [])
        avoid_patterns = thm.get("avoid_patterns", [])
        suggestions.append({
            "theorem": thm["name"],
            "theorem_zh": thm.get("name_zh", ""),
            "why": thm.get("reduces", ""),
            "prerequisites": thm.get("prerequisites", []),
            "invariant_hints": thm.get("invariant_hints", []),
            "verification_hints": thm.get("verification_hints", []),
            "preferred_recipe": preferred_recipe,
            "avoid_patterns": avoid_patterns,
            "confidence": confidence,
            "score": score,
            "sage_hint": thm.get("sage_hint", ""),
        })
        if preferred_recipe or avoid_patterns:
            soft_constraints.append({
                "theorem": thm["name"],
                "confidence": confidence,
                "score": score,
                "preferred_recipe": preferred_recipe,
                "avoid_patterns": avoid_patterns,
                "sage_hint": thm.get("sage_hint", ""),
            })


    scale = scale_info.get("scale", "unknown")
    theory_first = scale in {"heavy", "infeasible_brute_force"} or _requires_theory_first_construction(combined, matched)
    allow_bruteforce = scale in {"trivial", "moderate"} and not theory_first
    suggested_invariants = _suggest_invariants(scale_info, matched)
    verification_checks = _suggest_verification_checks(matched)
    workflow = {
        "phases": ["theorem", "invariants", "verification"],
        "theory_first": theory_first,
    }

    approach_parts = []
    if theory_first:
        if scale in {"heavy", "infeasible_brute_force"}:
            approach_parts.append("直接计算不可行，必须先用理论降维")
        else:
            approach_parts.append("这是构造/研究型模形式问题，应先给出理论构造与关键不变量，再做少量验证")
    elif scale == "moderate":
        approach_parts.append("可以计算，但应先检查是否能用定理或结构化简")
    else:
        approach_parts.append("可以先做直接计算")
    if suggestions:
        top = suggestions[0]
        approach_parts.append(f"推荐先用 {top['theorem']}：{top['why']}")
        if suggested_invariants:
            approach_parts.append(f"优先求不变量：{', '.join(suggested_invariants[:5])}")
        if verification_checks:
            approach_parts.append(f"结果前检查：{', '.join(verification_checks[:3])}")
        elif top["prerequisites"]:
            approach_parts.append(f"需要先计算：{', '.join(top['prerequisites'])}")
        if top["sage_hint"]:
            approach_parts.append(f"SageMath 提示：{top['sage_hint']}")

    unique_domains = sorted(set(domains))
    structural_complexity = _assess_structural_complexity(combined, len(unique_domains), matched=matched)

    return {
        "title": "定理顾问",
        "scale": scale,
        "scale_detail": {k: str(v) for k, v in scale_info.items() if k != "scale"},
        "suggested_theorems": suggestions,
        "suggested_invariants": suggested_invariants,
        "verification_checks": verification_checks,
        "workflow": workflow,
        "structural_complexity": structural_complexity,
        "soft_constraints": soft_constraints,
        "recommended_approach": " → ".join(approach_parts),
        "detected_domains": unique_domains,
        "allow_bruteforce": allow_bruteforce,
        "_display_instruction": "根据定理顾问的建议选择计算路线。如果 scale 为 heavy 或 infeasible_brute_force，必须先用理论方法降维，不要直接暴力计算",
    }


@math_tool(category="theorem_advisor", description="分析数学问题的计算规模，从定理库匹配可用定理，给出理论引导的计算路线。应在复杂计算前优先调用")
def theorem_advisor(problem: str, detected_objects: str = "") -> str:
    """分析数学问题并给出理论引导建议。

    Args:
        problem: 数学问题的完整描述（自然语言，可含 LaTeX）
        detected_objects: 可选，已识别的数学对象（如 'curve, finite_field, genus_3'），用逗号分隔
    """
    return json.dumps(analyze_problem(problem, detected_objects), ensure_ascii=False, default=str)
