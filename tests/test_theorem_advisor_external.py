import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai4math.tools import theorem_advisor


class TestTheoremAdvisorExternal(unittest.TestCase):
    def setUp(self):
        theorem_advisor._reset_theorem_cache()

    def tearDown(self):
        theorem_advisor._reset_theorem_cache()

    def test_builtin_theorems_load(self):
        with patch.dict(os.environ, {}, clear=False):
            theorem_advisor._reset_theorem_cache()
            theorems = theorem_advisor._load_theorems()
        self.assertTrue(any(thm.get("id") == "weil_zeta_curve" for thm in theorems))

    def test_external_path_merge_and_dedup(self):
        payload = {
            "theorems": [
                {
                    "id": "weil_zeta_curve",
                    "name": "Weil zeta function for curves",
                    "keywords": ["override"],
                    "signals": [],
                },
                {
                    "id": "new_external_theorem",
                    "name": "External theorem",
                    "keywords": ["external theorem", "special marker"],
                    "signals": ["special marker"],
                    "reduces": "外部知识命中",
                    "invariant_hints": ["external invariant"],
                    "verification_hints": ["external verification"],
                },
            ]
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(payload, f, ensure_ascii=False)
            temp_path = f.name
        self.addCleanup(lambda: os.path.exists(temp_path) and os.remove(temp_path))

        with patch.dict(os.environ, {
            "AI4MATH_THEOREM_SOURCE": "merge",
            "AI4MATH_THEOREM_EXTERNAL_PATH": temp_path,
            "AI4MATH_THEOREM_EXTERNAL_URL": "",
        }, clear=False):
            theorem_advisor._reset_theorem_cache()
            theorems = theorem_advisor._load_theorems()
            ids = [thm.get("id") for thm in theorems]
            self.assertIn("new_external_theorem", ids)
            self.assertEqual(ids.count("weil_zeta_curve"), 1)

    def test_external_path_fallback_to_builtin_when_invalid(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            temp_path = f.name
        self.addCleanup(lambda: os.path.exists(temp_path) and os.remove(temp_path))

        with patch.dict(os.environ, {
            "AI4MATH_THEOREM_SOURCE": "external",
            "AI4MATH_THEOREM_EXTERNAL_PATH": temp_path,
            "AI4MATH_THEOREM_EXTERNAL_URL": "",
        }, clear=False):
            theorem_advisor._reset_theorem_cache()
            theorems = theorem_advisor._load_theorems()
        self.assertTrue(any(thm.get("id") == "weil_zeta_curve" for thm in theorems))

    def test_matching_uses_external_theorem(self):
        payload = {
            "theorems": [
                {
                    "id": "external_marker",
                    "name": "External marker theorem",
                    "name_zh": "外部标记定理",
                    "keywords": ["special marker"],
                    "signals": ["special marker"],
                    "reduces": "通过外部库减少搜索空间",
                    "prerequisites": ["marker invariant"],
                    "invariant_hints": ["external marker invariant"],
                    "verification_hints": ["external marker verification"],
                    "sage_hint": "use sage_eval",
                    "domains": ["custom_domain"],
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(payload, f, ensure_ascii=False)
            temp_path = f.name
        self.addCleanup(lambda: os.path.exists(temp_path) and os.remove(temp_path))

        with patch.dict(os.environ, {
            "AI4MATH_THEOREM_SOURCE": "merge",
            "AI4MATH_THEOREM_EXTERNAL_PATH": temp_path,
            "AI4MATH_THEOREM_EXTERNAL_URL": "",
        }, clear=False):
            theorem_advisor._reset_theorem_cache()
            analysis = theorem_advisor.analyze_problem("请处理带有 special marker 的问题")

        self.assertTrue(any(item.get("theorem") == "External marker theorem" for item in analysis["suggested_theorems"]))
        self.assertIn("custom_domain", analysis["detected_domains"])
        self.assertIn("external marker invariant", analysis["suggested_invariants"])
        self.assertIn("external marker verification", analysis["verification_checks"])

    def test_builtin_curve_analysis_exports_structured_workflow(self):
        analysis = theorem_advisor.analyze_problem(
            r"How many nonzero points are there on [x^3y+y^3z+z^3x=0] over $\\mathbb{F}_{5^{18}}$ up to scaling?"
        )

        self.assertEqual(analysis["scale"], "infeasible_brute_force")
        self.assertFalse(analysis["allow_bruteforce"])
        self.assertIn("field characteristic p = 5", analysis["suggested_invariants"])
        self.assertIn("extension degree n = 18", analysis["suggested_invariants"])
        self.assertTrue(any("genus" in item.lower() for item in analysis["suggested_invariants"]))
        self.assertTrue(any("Hasse-Weil bound" in item for item in analysis["verification_checks"]))
        self.assertEqual(analysis["workflow"]["phases"], ["theorem", "invariants", "verification"])
        self.assertTrue(analysis["workflow"]["theory_first"])

    def test_multi_file_discovery_loads_all_domains(self):
        """Builtin loader discovers all domain JSON files and deduplicates."""
        theorem_advisor._reset_theorem_cache()
        theorems = theorem_advisor._load_builtin_theorems()
        ids = {thm.get("id") for thm in theorems}
        self.assertIn("weil_zeta_curve", ids)
        self.assertIn("quadratic_reciprocity", ids)
        self.assertIn("burnside_lemma", ids)
        self.assertIn("sylow_theorems", ids)
        self.assertIn("artin_reciprocity", ids)
        self.assertIn("hasse_bound_ec", ids)
        self.assertGreaterEqual(len(theorems), 24)

    def test_domain_file_format_with_domain_key(self):
        """Domain files with {"domain": ..., "theorems": [...]} are loaded correctly."""
        payload = {
            "domain": "test_domain",
            "theorems": [
                {
                    "id": "test_domain_thm",
                    "name": "Test domain theorem",
                    "keywords": ["test domain kw"],
                    "signals": [],
                    "domains": ["test_domain"],
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(payload, f, ensure_ascii=False)
            temp_path = f.name
        self.addCleanup(lambda: os.path.exists(temp_path) and os.remove(temp_path))

        with patch.dict(os.environ, {
            "AI4MATH_THEOREM_SOURCE": "merge",
            "AI4MATH_THEOREM_EXTERNAL_PATH": temp_path,
            "AI4MATH_THEOREM_EXTERNAL_URL": "",
        }, clear=False):
            theorem_advisor._reset_theorem_cache()
            theorems = theorem_advisor._load_theorems()
        self.assertTrue(any(thm.get("id") == "test_domain_thm" for thm in theorems))

    def test_structural_complexity_detected_for_long_problem(self):
        text = (
            "Define F and G. Let ell_1 be the smallest prime such that several constraints hold. "
            "Given that the class number is prime, the residue is primitive, and the Mordell-Weil group is specified, "
            "define alpha by a limit. Then compute the minimal polynomial, splitting field, and final Omega. "
        ) * 4
        analysis = theorem_advisor.analyze_problem(text)
        self.assertTrue(analysis["structural_complexity"]["is_complex"])
        self.assertGreaterEqual(analysis["structural_complexity"]["constraint_count"], 3)

    def test_structural_complexity_false_for_short_problem(self):
        analysis = theorem_advisor.analyze_problem("化简 x^2 + 2x + 1")
        self.assertFalse(analysis["structural_complexity"]["is_complex"])

    def test_soft_constraints_exported_with_confidence(self):
        payload = {
            "theorems": [
                {
                    "id": "soft_high",
                    "name": "High confidence theorem",
                    "keywords": ["marker"],
                    "signals": ["special marker"],
                    "domains": ["custom_domain"],
                    "preferred_recipe": ["use exact arithmetic", "work in CyclotomicField(k)"],
                    "avoid_patterns": ["do not use floating point"],
                    "confidence": "high"
                },
                {
                    "id": "soft_low",
                    "name": "Low confidence theorem",
                    "keywords": ["marker"],
                    "signals": [],
                    "domains": ["custom_domain"],
                    "preferred_recipe": ["optional recipe"],
                    "avoid_patterns": ["optional avoid"],
                    "confidence": "low"
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            json.dump(payload, f, ensure_ascii=False)
            temp_path = f.name
        self.addCleanup(lambda: os.path.exists(temp_path) and os.remove(temp_path))

        with patch.dict(os.environ, {
            "AI4MATH_THEOREM_SOURCE": "external",
            "AI4MATH_THEOREM_EXTERNAL_PATH": temp_path,
            "AI4MATH_THEOREM_EXTERNAL_URL": "",
        }, clear=False):
            theorem_advisor._reset_theorem_cache()
            analysis = theorem_advisor.analyze_problem("please handle special marker carefully")

        self.assertIn("soft_constraints", analysis)
        self.assertTrue(any(item.get("theorem") == "High confidence theorem" for item in analysis["soft_constraints"]))
        high = next(item for item in analysis["soft_constraints"] if item["theorem"] == "High confidence theorem")
        low = next(item for item in analysis["soft_constraints"] if item["theorem"] == "Low confidence theorem")
        self.assertEqual(high["confidence"], "high")
        self.assertGreater(high["score"], low["score"])
        self.assertIn("use exact arithmetic", high["preferred_recipe"])
        self.assertIn("do not use floating point", high["avoid_patterns"])


    def test_weil_curve_soft_constraints_present(self):
        """Weil/Klein theorem entries produce soft constraints with preferred_recipe."""
        analysis = theorem_advisor.analyze_problem(
            r"Count projective points on x^3y+y^3z+z^3x=0 over $\\mathbb{F}_{5^{18}}$"
        )
        self.assertTrue(len(analysis["soft_constraints"]) > 0)
        recipes = [
            sc for sc in analysis["soft_constraints"] if sc.get("preferred_recipe")
        ]
        self.assertTrue(len(recipes) > 0, "expected at least one soft constraint with preferred_recipe")
        top = max(recipes, key=lambda sc: sc.get("score", 0))
        self.assertEqual(top["confidence"], "high")


if __name__ == "__main__":
    unittest.main()
