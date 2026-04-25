import copy
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ai4math.tools.analysis  # noqa: F401
import ai4math.tools.algebra  # noqa: F401
import ai4math.tools.plotting  # noqa: F401
import ai4math.tools.probability  # noqa: F401
import ai4math.tools.theorem_advisor  # noqa: F401

from ai4math.llm.client import MathLLMClient


class DummyMessage:
    def __init__(self, content: str, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self):
        return {"role": "assistant", "content": self.content}


class DummyChoice:
    def __init__(self, content: str, finish_reason: str = "stop", tool_calls=None):
        self.message = DummyMessage(content, tool_calls=tool_calls)
        self.finish_reason = finish_reason


class DummyResponse:
    def __init__(self, content: str, finish_reason: str = "stop", tool_calls=None):
        self.choices = [DummyChoice(content, finish_reason=finish_reason, tool_calls=tool_calls)]


class TestPreplanning(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "AI4MATH_MODEL": "main-model",
            "AI4MATH_FLASH_MODEL": "flash-model",
            "AI4MATH_PRO_MODEL": "pro-model",
            "AI4MATH_PREPLAN_MODEL": "planner-model",
            "AI4MATH_AUTO_ROUTE": "true",
            "AI4MATH_PREPLAN_ENABLED": "true",
        }, clear=False)
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    def test_preplanning_uses_planner_model_even_when_main_routes_flash(self):
        calls = []

        def fake_create(**kwargs):
            snapshot = dict(kwargs)
            snapshot["messages"] = copy.deepcopy(kwargs.get("messages", []))
            calls.append(snapshot)
            if kwargs["model"] == "planner-model":
                return DummyResponse(json.dumps({
                    "problem_type": "analysis",
                    "should_use_theory_first": False,
                    "recommended_tools": ["simplify_expression"],
                    "key_invariants": ["symmetry"],
                    "theorem_focus": ["binomial theorem"],
                    "invariant_targets": ["symmetry"],
                    "verification_targets": ["expand and compare coefficients"],
                    "strategy": "先做代数化简",
                }, ensure_ascii=False))
            if kwargs["model"] == "flash-model":
                return DummyResponse("最终答案")
            raise AssertionError(f"unexpected model {kwargs['model']}")

        client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        with patch.object(client, "_classify_difficulty", return_value="simple"):
            with patch.object(client.client.chat.completions, "create", side_effect=fake_create):
                result = client.chat("计算 (x+1)^2 的展开式")

        self.assertEqual(result, "最终答案")
        self.assertEqual(calls[0]["model"], "planner-model")
        self.assertEqual(calls[1]["model"], "flash-model")
        preplan_context = calls[1]["messages"][-1]
        self.assertEqual(preplan_context["role"], "system")
        self.assertIn("预规划结果", preplan_context["content"])
        self.assertIn("simplify_expression", preplan_context["content"])
        self.assertIn("theorem_focus", preplan_context["content"])
        self.assertIn("verification_targets", preplan_context["content"])

    def test_heavy_scale_forces_theory_first_constraint(self):
        calls = []

        def fake_create(**kwargs):
            snapshot = dict(kwargs)
            snapshot["messages"] = copy.deepcopy(kwargs.get("messages", []))
            calls.append(snapshot)
            if kwargs["model"] == "planner-model":
                return DummyResponse(json.dumps({
                    "problem_type": "finite_field_curve",
                    "should_use_theory_first": False,
                    "recommended_tools": ["theorem_advisor", "sage_eval"],
                    "key_invariants": ["genus", "frobenius polynomial"],
                    "theorem_focus": ["Weil zeta function for curves"],
                    "invariant_targets": ["genus", "Frobenius characteristic polynomial"],
                    "verification_targets": ["Hasse-Weil bound", "small-field consistency"],
                    "strategy": "检查点数路线",
                }, ensure_ascii=False))
            if kwargs["model"] == "pro-model":
                return DummyResponse("复杂题答案")
            raise AssertionError(f"unexpected model {kwargs['model']}")

        client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        with patch.object(client.client.chat.completions, "create", side_effect=fake_create):
            result = client.chat("求曲线 C/F_{5^{18}} 的点数")

        self.assertEqual(result, "复杂题答案")
        self.assertEqual(calls[0]["model"], "planner-model")
        self.assertEqual(calls[1]["model"], "pro-model")
        preplan_context = calls[1]["messages"][-1]["content"]
        self.assertIn("禁止暴力枚举", preplan_context)
        self.assertIn("theorem_advisor", preplan_context)
        self.assertIn("workflow_order: theorem -> invariants -> verification", preplan_context)
        self.assertIn("verification_targets", preplan_context)
        self.assertIn("Hasse-Weil bound", preplan_context)

    def test_preplanning_failure_falls_back_to_default_plan(self):
        calls = []

        def fake_create(**kwargs):
            snapshot = dict(kwargs)
            snapshot["messages"] = copy.deepcopy(kwargs.get("messages", []))
            calls.append(snapshot)
            if kwargs["model"] == "planner-model":
                raise RuntimeError("planner failed")
            if kwargs["model"] == "flash-model":
                return DummyResponse("回退后答案")
            raise AssertionError(f"unexpected model {kwargs['model']}")

        client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        with patch.object(client, "_classify_difficulty", return_value="simple"):
            with patch.object(client.client.chat.completions, "create", side_effect=fake_create):
                result = client.chat("化简 x^2+2x+1")

        self.assertEqual(result, "回退后答案")
        self.assertEqual(calls[0]["model"], "planner-model")
        self.assertEqual(calls[1]["model"], "flash-model")
        preplan_context = calls[1]["messages"][-1]["content"]
        self.assertIn("theorem_advisor", preplan_context)
        self.assertIn("verification_targets", preplan_context)
        self.assertIn("workflow_order", preplan_context)
        self.assertNotIn("tool_call_id", preplan_context)

    def test_long_problem_triggers_decomposition_and_complex_routing(self):
        calls = []
        long_problem = (
            "Define F(z) and G(z) on the upper-half plane. Let ell_1 be the smallest prime such that "
            "it satisfies several arithmetic constraints, including class number, primitive root, "
            "Mordell-Weil group, and then define alpha by a limit involving F and G. "
            "Given that P_alpha is the minimal polynomial and K_alpha is the splitting field, "
            "compute Omega. Such that each step depends on the previous constants, determine the final value. "
            * 5
        )

        def fake_create(**kwargs):
            snapshot = dict(kwargs)
            snapshot["messages"] = copy.deepcopy(kwargs.get("messages", []))
            calls.append(snapshot)
            if kwargs["model"] == "planner-model" and "长题分解" in kwargs["messages"][0]["content"]:
                return DummyResponse(json.dumps({
                    "objects": ["F(z)", "G(z)", "ell_1", "ell_2", "alpha"],
                    "subproblems": [
                        {"id": "sp1", "statement": "Find ell_1 and ell_2", "depends_on": [], "domain": "number_theory"},
                        {"id": "sp2", "statement": "Compute alpha", "depends_on": ["sp1"], "domain": "modular_forms"},
                    ],
                    "final_target": "Compute Omega",
                    "dependency_order": ["sp1", "sp2"],
                }, ensure_ascii=False))
            if kwargs["model"] == "planner-model":
                return DummyResponse(json.dumps({
                    "problem_type": "long_chain",
                    "should_use_theory_first": True,
                    "recommended_tools": ["theorem_advisor", "sage_eval"],
                    "key_invariants": ["ell_1", "ell_2", "alpha"],
                    "theorem_focus": ["class number formula"],
                    "invariant_targets": ["ell_1", "ell_2", "minimal polynomial of alpha"],
                    "verification_targets": ["dependency order respected"],
                    "strategy": "按子问题顺序推进",
                }, ensure_ascii=False))
            if kwargs["model"] == "pro-model":
                return DummyResponse("长题答案")
            raise AssertionError(f"unexpected model {kwargs['model']}")

        client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        with patch.object(client.client.chat.completions, "create", side_effect=fake_create):
            result = client.chat(long_problem)

        self.assertEqual(result, "长题答案")
        self.assertEqual(calls[0]["model"], "planner-model")
        self.assertGreaterEqual(calls[0]["max_tokens"], 1024)
        self.assertEqual(calls[1]["model"], "planner-model")
        self.assertGreaterEqual(calls[1]["max_tokens"], 1200)
        self.assertEqual(calls[2]["model"], "pro-model")
        preplan_context = calls[2]["messages"][-1]["content"]
        self.assertIn("子问题分解", preplan_context)
        self.assertIn("求解顺序: sp1 -> sp2", preplan_context)
        self.assertIn("执行规则", preplan_context)

    def test_decomposition_failure_falls_back_to_normal_flow(self):
        calls = []
        long_problem = ("Define A. Given that many conditions hold, determine the result. " * 12)

        def fake_create(**kwargs):
            snapshot = dict(kwargs)
            snapshot["messages"] = copy.deepcopy(kwargs.get("messages", []))
            calls.append(snapshot)
            if kwargs["model"] == "planner-model" and "长题分解" in kwargs["messages"][0]["content"]:
                raise RuntimeError("decomposition failed")
            if kwargs["model"] == "planner-model":
                return DummyResponse(json.dumps({
                    "problem_type": "fallback",
                    "should_use_theory_first": True,
                    "recommended_tools": ["theorem_advisor"],
                    "key_invariants": ["constant"],
                    "theorem_focus": ["some theorem"],
                    "invariant_targets": ["constant"],
                    "verification_targets": ["consistency"],
                    "strategy": "正常预规划",
                }, ensure_ascii=False))
            if kwargs["model"] == "pro-model":
                return DummyResponse("fallback answer")
            raise AssertionError(f"unexpected model {kwargs['model']}")

        client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        with patch.object(client.client.chat.completions, "create", side_effect=fake_create):
            result = client.chat(long_problem)

        self.assertEqual(result, "fallback answer")
        self.assertEqual(calls[0]["model"], "planner-model")
        self.assertEqual(calls[1]["model"], "planner-model")
        self.assertEqual(calls[2]["model"], "pro-model")
        preplan_context = calls[2]["messages"][-1]["content"]
        self.assertNotIn("子问题分解", preplan_context)

    def test_high_confidence_soft_guidance_injected(self):
        client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        analysis = {
            "scale": "moderate",
            "suggested_theorems": [{"theorem": "High confidence theorem"}],
            "suggested_invariants": ["zeta"],
            "verification_checks": ["algebraicity"],
            "workflow": {"phases": ["theorem", "invariants", "verification"]},
            "recommended_approach": "use exact arithmetic",
            "soft_constraints": [{
                "theorem": "High confidence theorem",
                "confidence": "high",
                "score": 5.0,
                "preferred_recipe": ["use exact arithmetic", "work in CyclotomicField(k)"],
                "avoid_patterns": ["do not use floating point"],
            }],
        }
        plan = {
            "problem_type": "modular_forms",
            "should_use_theory_first": False,
            "recommended_tools": ["theorem_advisor", "sage_eval"],
            "key_invariants": ["zeta"],
            "theorem_focus": ["High confidence theorem"],
            "invariant_targets": ["zeta"],
            "verification_targets": ["algebraicity"],
            "strategy": "use exact arithmetic",
        }
        context = client._build_preplan_context(analysis, plan)
        self.assertIn("高置信度定理指导", context)
        self.assertIn("High confidence theorem", context)
        self.assertIn("preferred_recipe:", context)
        self.assertIn("use exact arithmetic", context)
        self.assertIn("avoid_patterns:", context)
        self.assertIn("do not use floating point", context)

    def test_low_confidence_soft_guidance_not_injected(self):
        client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        analysis = {
            "scale": "moderate",
            "suggested_theorems": [{"theorem": "Low confidence theorem"}],
            "suggested_invariants": ["q"],
            "verification_checks": ["consistency"],
            "workflow": {"phases": ["theorem", "invariants", "verification"]},
            "recommended_approach": "keep flexible",
            "soft_constraints": [{
                "theorem": "Low confidence theorem",
                "confidence": "low",
                "score": 1.0,
                "preferred_recipe": ["optional recipe"],
                "avoid_patterns": ["optional avoid"],
            }],
        }
        plan = {
            "problem_type": "general",
            "should_use_theory_first": False,
            "recommended_tools": ["theorem_advisor"],
            "key_invariants": ["q"],
            "theorem_focus": ["Low confidence theorem"],
            "invariant_targets": ["q"],
            "verification_targets": ["consistency"],
            "strategy": "keep flexible",
        }
        context = client._build_preplan_context(analysis, plan)
        self.assertNotIn("高置信度定理指导", context)
        self.assertNotIn("preferred_recipe", context)
        self.assertNotIn("avoid_patterns", context)


    def test_weil_curve_gets_high_confidence_recipe(self):
        """Weil curve problem triggers high-confidence soft guidance injection."""
        from ai4math.tools.theorem_advisor import analyze_problem

        analysis = analyze_problem(
            r"Count projective points on x^3y+y^3z+z^3x=0 over $\\mathbb{F}_{5^{18}}$"
        )
        self.assertTrue(len(analysis["soft_constraints"]) > 0)

        client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        plan = {
            "problem_type": "finite_field_curve",
            "should_use_theory_first": True,
            "recommended_tools": ["theorem_advisor", "sage_eval"],
            "key_invariants": ["genus", "Frobenius polynomial"],
            "theorem_focus": ["Weil zeta function for curves"],
            "invariant_targets": ["genus", "Frobenius characteristic polynomial"],
            "verification_targets": ["Hasse-Weil bound"],
            "strategy": "Weil zeta function",
        }
        context = client._build_preplan_context(analysis, plan)
        self.assertIn("高置信度定理指导", context)
        self.assertIn("preferred_recipe", context)
        self.assertIn("avoid_patterns", context)
        self.assertIn("count_points", context)


if __name__ == "__main__":
    unittest.main()
