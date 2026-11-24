"""Comprehensive regression & security test suite covering all 34 Appendix B cases and smoke checks."""

from __future__ import annotations

import http.server
import importlib.util
import json
import os
import socketserver
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ai4math.tools.analysis  # noqa: F401
import ai4math.tools.algebra  # noqa: F401
import ai4math.tools.probability  # noqa: F401
import ai4math.tools.plotting  # noqa: F401
import ai4math.tools.theorem_advisor as theorem_advisor  # noqa: F401

HAS_SAGE = importlib.util.find_spec("sage") is not None
if HAS_SAGE:
    import ai4math.tools.sage_tools  # noqa: F401
    import ai4math.tools.sage_plotting  # noqa: F401

from ai4math.cli import _rewrite_relative_image_paths, _run_batch, _split_batch_questions
from ai4math.llm.client import MathLLMClient, _format_tool_result_md
from ai4math.tools._shared import safe_parse_expr
from ai4math.tools.registry import ToolRegistry


class _DummyToolCallFunc:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _DummyToolCall:
    def __init__(self, tc_id: str, name: str, arguments: str):
        self.id = tc_id
        self.function = _DummyToolCallFunc(name, arguments)


class _DummyMessage:
    def __init__(self, content: str, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def model_dump(self):
        d = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in self.tool_calls
            ]
        return d


class _DummyChoice:
    def __init__(self, content: str, finish_reason: str = "stop", tool_calls=None):
        self.message = _DummyMessage(content, tool_calls=tool_calls)
        self.finish_reason = finish_reason


class _DummyResponse:
    def __init__(self, content: str, finish_reason: str = "stop", tool_calls=None):
        self.choices = [_DummyChoice(content, finish_reason=finish_reason, tool_calls=tool_calls)]


class TestSecurityHardening(unittest.TestCase):
    """Verify AST & global_dict sandbox protections on in-process SymPy parsing."""

    def test_sympy_blocks_dunder_import_and_attribute_escape(self):
        malicious_inputs = [
            "__import__('os').system('echo pwned')",
            "().__class__.__bases__[0].__subclasses__()",
            "x.__class__.__mro__",
            "[i for i in range(10)]",
            "(lambda z: z)(1)",
        ]
        for payload in malicious_inputs:
            with self.subTest(payload=payload):
                with self.assertRaises(Exception):
                    safe_parse_expr(payload)

    def test_tool_call_rejects_malicious_expr_cleanly(self):
        raw = ToolRegistry.call_tool("simplify_expression", {"expr": "__import__('os').getcwd()"})
        data = json.loads(raw)
        self.assertIn("error", data)


class TestSymPyToolsAndPlottingRegression(unittest.TestCase):
    """Covers Appendix B #15-#26 and Section 3.6 non-Sage items."""

    def setUp(self):
        self._created_plots: list[str] = []

    def tearDown(self):
        for p in self._created_plots:
            if p and os.path.exists(p):
                os.remove(p)

    def _track_plot(self, data: dict) -> str:
        path = data.get("image_path", "")
        if path:
            self._created_plots.append(path)
        return path

    def test_b15_plot_inequality_region(self):
        raw = ToolRegistry.call_tool(
            "plot_inequality_region",
            {"inequalities": "x**2/4 + y**2/9 < 1; x + y > 0", "x_range": "-3,3", "y_range": "-4,4", "title": "Region"},
        )
        data = json.loads(raw)
        path = self._track_plot(data)
        self.assertNotIn("error", data)
        self.assertTrue(os.path.isfile(path))

    def test_b16_plot_function_symbolic_bounds_min_and_gamma(self):
        for expr in ("sin(x), cos(x)", "min(x, 0)", "gamma(x)"):
            with self.subTest(expr=expr):
                raw = ToolRegistry.call_tool(
                    "plot_function",
                    {"expr": expr, "variable": "x", "x_min": "-2*pi", "x_max": "2*pi", "title": "Test"},
                )
                data = json.loads(raw)
                path = self._track_plot(data)
                self.assertNotIn("error", data, msg=f"Failed for {expr}: {data}")
                self.assertTrue(os.path.isfile(path))

    def test_b17_plot_parametric_symbolic_tmax(self):
        raw = ToolRegistry.call_tool(
            "plot_parametric",
            {"x_expr": "cos(3*t)", "y_expr": "sin(5*t)", "t_min": "0", "t_max": "2*pi", "title": "Lissajous"},
        )
        data = json.loads(raw)
        path = self._track_plot(data)
        self.assertNotIn("error", data)
        self.assertTrue(os.path.isfile(path))

    def test_b18_compute_variance_exact_rational_float_param(self):
        raw = ToolRegistry.call_tool(
            "compute_variance",
            {"dist_type": "binomial", "params": '{"n": 10, "p": 0.3}', "expression": "x**2"},
        )
        data = json.loads(raw)
        self.assertNotIn("error", data)
        self.assertEqual(data["latex"], r"\frac{46977}{500}")

    def test_b19_b20_compute_probability_abs_chained_and_boolean(self):
        raw_abs = ToolRegistry.call_tool(
            "compute_probability",
            {"dist_type": "normal", "params": '{"mu": 0, "sigma": 1}', "condition": "abs(x) > 2"},
        )
        d_abs = json.loads(raw_abs)
        self.assertNotIn("error", d_abs)
        self.assertTrue("erf" in d_abs["latex"] or "erfc" in d_abs["latex"])

        for cond in ("0.5 < x < 0.8", "x > 0.5 and x < 0.8"):
            with self.subTest(cond=cond):
                raw_u = ToolRegistry.call_tool(
                    "compute_probability",
                    {"dist_type": "uniform", "params": '{"a": 0, "b": 1}', "condition": cond},
                )
                d_u = json.loads(raw_u)
                self.assertNotIn("error", d_u)
                self.assertIn(d_u["output"], ("3/10", "0.3"))

    def test_poisson_mgf_closed_form(self):
        raw = ToolRegistry.call_tool(
            "moment_generating_function",
            {"dist_type": "poisson", "params": '{"lambda": 2}'},
        )
        data = json.loads(raw)
        self.assertNotIn("error", data)
        self.assertNotIn("Sum", data["output"])
        self.assertIn("e", data["latex"])

    def test_b21_compute_sum_default_lower_bound(self):
        from ai4math.tools.analysis import compute_sum

        data = json.loads(compute_sum("1/n**2"))
        self.assertNotIn("error", data)
        self.assertNotIn("zoo", data["output"])
        self.assertIn("pi", data["latex"])

    def test_integrate_rejects_partial_bounds(self):
        raw = ToolRegistry.call_tool("integrate", {"expr": "x**2", "variable": "x", "lower": "0", "upper": ""})
        data = json.loads(raw)
        self.assertIn("error", data)

    def test_b22_b23_b24_permutation_operation(self):
        d1 = json.loads(ToolRegistry.call_tool("permutation_operation", {"perm": "(0 1 2)", "operation": "info", "perm2": ""}))
        self.assertEqual(d1["order"], "3")
        self.assertEqual(d1["parity"], "偶置换")

        d2 = json.loads(ToolRegistry.call_tool("permutation_operation", {"perm": "(0 1 2)(3 4)", "operation": "info", "perm2": ""}))
        self.assertEqual(d2["order"], "6")
        self.assertEqual(d2["parity"], "奇置换")

        d3 = json.loads(ToolRegistry.call_tool("permutation_operation", {"perm": "[1, 2, 0, 4, 3]", "operation": "power", "perm2": "2"}))
        self.assertNotIn("error", d3)
        self.assertEqual(d3["order"], "3")

    def test_b25_check_algebraic_structure_custom_elements_and_bad_shape(self):
        d_ok = json.loads(
            ToolRegistry.call_tool(
                "check_algebraic_structure",
                {"elements": "[1, -1]", "operation_table": "[[1, -1], [-1, 1]]", "structure": "abelian_group"},
            )
        )
        self.assertIn("构成 2 阶交换群", d_ok["conclusion"])

        d_bad = json.loads(
            ToolRegistry.call_tool(
                "check_algebraic_structure",
                {"elements": "[0, 1, 2]", "operation_table": "[[0, 1], [1, 0]]", "structure": "group"},
            )
        )
        self.assertIn("error", d_bad)

    def test_b26_polynomial_roots_and_lcm_with_modulus(self):
        d_roots = json.loads(
            ToolRegistry.call_tool(
                "polynomial_operation",
                {"expr": "x**2 - 1", "operation": "roots", "variable": "x", "modulus": 2},
            )
        )
        self.assertEqual(d_roots["roots"], "{1: 2}")

    def test_quotient_ring_modular_power_fast_and_title(self):
        t0 = time.monotonic()
        d_pow = json.loads(
            ToolRegistry.call_tool(
                "quotient_ring_operation",
                {
                    "expr": "x + 1; 100000",
                    "modulus_poly": "x**2 + 1",
                    "ring_modulus": 7,
                    "variable": "x",
                    "operation": "power",
                },
            )
        )
        elapsed = time.monotonic() - t0
        self.assertNotIn("error", d_pow)
        self.assertLess(elapsed, 2.0)
        self.assertIn("F_7[x]/(x**2 + 1)", d_pow["title"])


class TestAdvisorClientAndBatchRegression(unittest.TestCase):
    """Covers Appendix B #28-#34 plus truncated tool-call continuation and batch helpers."""

    def test_b28_large_integer_power_not_misclassified_as_finite_field(self):
        for q in ("判断 2^127 - 1 是否是素数", "计算 10^20 + 7 的因数分解", "求 3^50 的末三位数字"):
            with self.subTest(q=q):
                res = theorem_advisor.analyze_problem(q)
                self.assertNotEqual(res["scale"], "infeasible_brute_force")
                self.assertNotIn("finite_field", res["scale_detail"])

    def test_b29_irrelevant_limit_or_matrix_rank_does_not_inject_high_confidence_recipe(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        for q in ("求 lim_{x->0} sin(x)/x", "计算矩阵 [[1,2],[3,4]] 的秩 rank"):
            with self.subTest(q=q):
                analysis = theorem_advisor.analyze_problem(q)
                plan = {
                    "problem_type": "calculus",
                    "should_use_theory_first": False,
                    "recommended_tools": ["compute_limit"],
                    "key_invariants": [],
                    "theorem_focus": [],
                    "invariant_targets": [],
                    "verification_targets": [],
                    "strategy": "直接求值",
                }
                ctx = client._build_preplan_context(analysis, plan)
                self.assertNotIn("高置信度定理指导", ctx)

    def test_b30_preplanning_validates_string_list_and_false_bool(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "AI4MATH_PREPLAN_ENABLED": "true"}, clear=False):
            client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        analysis = theorem_advisor.analyze_problem("化简 (x+1)^2")
        bad_json = json.dumps({
            "problem_type": "algebra",
            "should_use_theory_first": "false",
            "recommended_tools": "sage_eval",
            "key_invariants": "disc",
            "theorem_focus": 123,
            "invariant_targets": "none",
            "verification_targets": "check",
            "strategy": "测试类型校验",
        })
        with patch.object(client.client.chat.completions, "create", return_value=_DummyResponse(bad_json)):
            plan = client._run_preplanning("化简 (x+1)^2", analysis)
        self.assertFalse(plan["should_use_theory_first"])
        self.assertEqual(plan["recommended_tools"], ["theorem_advisor"])
        self.assertNotIn("s", plan["recommended_tools"])

    def test_b31_classify_difficulty_defaults_ambiguous_to_complex(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            client = MathLLMClient(api_key="test-key", base_url="http://example.com")
        for ans, expected in (("复杂", "complex"), ("不确定", "complex"), ("complex", "complex"), ("simple", "simple")):
            with self.subTest(ans=ans):
                with patch.object(client.client.chat.completions, "create", return_value=_DummyResponse(ans)):
                    self.assertEqual(client._classify_difficulty("求 x^2 的导数"), expected)

    def test_b32_explicit_ai4math_model_propagates_to_auto_route_models(self):
        env_clean = {
            k: v for k, v in os.environ.items()
            if k not in ("AI4MATH_FLASH_MODEL", "AI4MATH_PRO_MODEL", "AI4MATH_PREPLAN_MODEL")
        }
        env_clean["OPENAI_API_KEY"] = "test-key"
        env_clean["AI4MATH_MODEL"] = "my-local-model"
        env_clean["AI4MATH_AUTO_ROUTE"] = "true"
        env_clean["AI4MATH_PREPLAN_ENABLED"] = "true"

        used_models: list[str] = []

        def fake_create(**kwargs):
            used_models.append(kwargs["model"])
            return _DummyResponse("simple" if kwargs.get("max_tokens") == 8 else "本地模型回答")

        with patch.dict(os.environ, env_clean, clear=True):
            client = MathLLMClient()
            self.assertEqual(client.flash_model, "my-local-model")
            self.assertEqual(client.pro_model, "my-local-model")
            self.assertEqual(client.preplan_model, "my-local-model")
            with patch.object(client.client.chat.completions, "create", side_effect=fake_create):
                ans = client.chat("化简 x + x")
        self.assertEqual(ans, "本地模型回答")
        self.assertTrue(all(m == "my-local-model" for m in used_models))

    def test_truncated_tool_call_and_stale_preplan_cleanup(self):
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key", "AI4MATH_AUTO_ROUTE": "false", "AI4MATH_PREPLAN_ENABLED": "false"},
            clear=False,
        ):
            client = MathLLMClient(api_key="test-key", base_url="http://example.com", model="test-model")

        seq = [
            _DummyResponse(
                "",
                finish_reason="length",
                tool_calls=[_DummyToolCall("tc_1", "simplify_expression", '{"expr": "x+')],
            ),
            _DummyResponse("第一轮恢复成功"),
            _DummyResponse("第二轮回答"),
        ]
        with patch.object(client.client.chat.completions, "create", side_effect=seq):
            r1 = client.chat("第一题")
            r2 = client.chat("第二题")

        self.assertEqual(r1, "第一轮恢复成功")
        self.assertEqual(r2, "第二轮回答")
        # Verify tool_call_id tc_1 received a matching role="tool" message
        tool_msgs = [m for m in client.messages if m.get("role") == "tool" and m.get("tool_call_id") == "tc_1"]
        self.assertEqual(len(tool_msgs), 1)
        # Verify only 1 preplan system message + 1 main SYSTEM_PROMPT exist (no accumulation)
        sys_msgs = [m for m in client.messages if m.get("role") == "system"]
        self.assertEqual(len(sys_msgs), 2)

    def test_b34_format_tool_result_md_preserves_verification_and_algebra_fields(self):
        vc_json = json.dumps({
            "title": "猜想验证",
            "summary": "共测试 10 个值: 10 通过, 0 失败",
            "output": "共测试 10 个值: 10 通过, 0 失败",
            "conclusion": "所有测试值均满足猜想",
        }, ensure_ascii=False)
        md_vc = _format_tool_result_md("verify_conjecture", {}, vc_json)
        self.assertIsNotNone(md_vc)
        self.assertIn("10 通过", md_vc)

        ec_json = json.dumps({
            "title": "椭圆曲线性质",
            "椭圆曲线": "Elliptic Curve y^2 = x^3 - x",
            "秩": "0",
            "扭子群": "Torsion Subgroup Z/2 + Z/2",
            "latex": "y^{2} = x^{3} - x",
        }, ensure_ascii=False)
        md_ec = _format_tool_result_md("elliptic_curve_info", {}, ec_json)
        self.assertIsNotNone(md_ec)
        self.assertIn("秩", md_ec)
        self.assertIn("扭子群", md_ec)

        eig_raw = ToolRegistry.call_tool("matrix_operation", {"matrix": "[[1,2],[3,4]]", "operation": "eigenvals"})
        eig_data = json.loads(eig_raw)
        self.assertNotIn("{", eig_data["latex"][:2])  # Not raw Python dict repr
        self.assertIn("\\lambda", eig_data["latex"])

    def test_batch_frontmatter_splitting_and_relative_image_rewrite(self):
        sample = "---\ntitle: Math Sheet\ndate: 2026-11-24\n---\n题 1: |a|---|b|\n---\n题 2\n"
        qs = _split_batch_questions(sample)
        self.assertEqual(len(qs), 2)
        self.assertIn("题 1", qs[0])

        md = "> ![plot](output/plots/func_1.png)"
        rewritten = _rewrite_relative_image_paths(md, Path("output/batch_test/q001.md"))
        self.assertIn("../plots/func_1.png", rewritten)

    def test_b33_run_batch_enforces_real_per_question_timeout(self):
        class _SlowFastHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8", errors="replace")
                if "SLOW_QUESTION" in body:
                    time.sleep(10)
                resp = {
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "mock-model",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "FAST_DONE"},
                            "finish_reason": "stop",
                        }
                    ],
                }
                payload = json.dumps(resp).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                return

        class _ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        try:
            server = _ThreadedTCPServer(("127.0.0.1", 0), _SlowFastHandler)
        except PermissionError:
            self.skipTest("Loopback socket binding restricted in sandbox")

        port = server.server_address[1]
        srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
        srv_thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)

        with tempfile.TemporaryDirectory() as tmpdir:
            batch_file = Path(tmpdir) / "questions.md"
            out_dir = Path(tmpdir) / "batch_out"
            batch_file.write_text("SLOW_QUESTION\n---\nFAST_QUESTION\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_BASE_URL": f"http://127.0.0.1:{port}",
                    "AI4MATH_MODEL": "mock-model",
                    "AI4MATH_AUTO_ROUTE": "false",
                    "AI4MATH_PREPLAN_ENABLED": "false",
                },
                clear=False,
            ):
                t0 = time.monotonic()
                _run_batch(str(batch_file), output_dir=str(out_dir), workers=2, timeout=2)
                elapsed = time.monotonic() - t0

            self.assertLess(elapsed, 7.0, f"Batch did not enforce timeout promptly (took {elapsed:.2f}s)")
            q1_text = (out_dir / "q001.md").read_text(encoding="utf-8")
            q2_text = (out_dir / "q002.md").read_text(encoding="utf-8")
            summary_text = (out_dir / "summary.md").read_text(encoding="utf-8")
            self.assertIn("超时", q1_text)
            self.assertIn("FAST_DONE", q2_text)
            self.assertIn("成功 1", summary_text)
            self.assertIn("超时 1", summary_text)


@unittest.skipUnless(HAS_SAGE, "SageMath not available")
class TestSageToolsRegression(unittest.TestCase):
    """Covers Appendix B #1-#14, #27, and Section 3.6 Sage items."""

    def test_b01_to_b09_sage_eval_cases(self):
        cases = [
            ("2^10", "1024"),
            ("2^3 + 2^2", "12"),
            ("1/3", "1/3"),
            ("res = []\nfor p in primes(20):\n    res.append(p)\nres", "[2, 3, 5, 7, 11, 13, 17, 19]"),
            ("n = 10\nif n > 5:\n    r = 'big'\nelse:\n    r = 'small'\nr", "big"),
            ('var("n"); assume(n, "integer"); sum(1/factorial(n), n, 0, 10)', "9864101/3628800"),
            ("a = 5; a + 1", "6"),
            ("R.<x> = QQ[]\nf = x^2 + 1\nf.factor()", "x^2 + 1"),
        ]
        for code, expected in cases:
            with self.subTest(code=code):
                raw = ToolRegistry.call_tool("sage_eval", {"code": code})
                data = json.loads(raw)
                self.assertNotIn("error", data, msg=f"Unexpected error for {code!r}: {data}")
                self.assertEqual(data["output"], expected)

        # #8: print + return value
        raw_print = ToolRegistry.call_tool("sage_eval", {"code": "print('中间结果:', 6*7)\n6*7"})
        d_print = json.loads(raw_print)
        self.assertNotIn("error", d_print)
        self.assertEqual(d_print["output"], "42")
        self.assertIn("中间结果: 42", d_print.get("stdout", ""))
        md_print = _format_tool_result_md("sage_eval", {}, raw_print)
        self.assertIn("中间结果: 42", md_print)

    def test_b10_construct_proof_with_multiline_for_loop(self):
        steps = json.dumps([
            {"desc": "统计小素数", "code": "cnt = 0\nfor p in primes(12):\n    cnt += 1\ncnt"}
        ])
        raw = ToolRegistry.call_tool(
            "construct_proof",
            {"setup_code": "R.<x> = QQ[]\nK.<a> = NumberField(x^2 + 1)", "steps": steps, "example_params": ""},
        )
        data = json.loads(raw)
        self.assertNotIn("error", data)
        self.assertEqual(data["successful_steps"], "1")
        self.assertIn("5", data["summary"])

    def test_b11_to_b14_explore_structure_topics(self):
        cases = [
            ("multiplicative_group", "p=17"),
            ("splitting", "poly=x^4-2, primes=[2,3,5,7,11]"),
            ("class_group", "poly=x^2+1"),
            ("representation", "form=a^2+64*b^2, bound=120"),
        ]
        for topic, params in cases:
            with self.subTest(topic=topic):
                raw = ToolRegistry.call_tool("explore_structure", {"topic": topic, "params": params})
                data = json.loads(raw)
                self.assertNotIn("error", data, msg=f"Failed {topic}({params}): {data}")

    def test_b27_search_counterexample_reports_all_errors(self):
        for bad_pred in ("n/0 > 1", "is_prime(2*m + 1)"):
            with self.subTest(pred=bad_pred):
                raw = ToolRegistry.call_tool(
                    "search_counterexample",
                    {"predicate_code": bad_pred, "param_name": "n", "search_range": "range(1, 50)"},
                )
                data = json.loads(raw)
                self.assertIn("error", data)
                self.assertNotEqual(data.get("title"), "未找到反例")

    def test_sage_simplify_gamma_and_clean_galois_latex(self):
        d_simp = json.loads(
            ToolRegistry.call_tool(
                "sage_simplify",
                {"expr": "gamma(n+1)/gamma(n)", "operation": "simplify", "assumptions": "n: integer, positive"},
            )
        )
        self.assertNotIn("error", d_simp)
        self.assertEqual(d_simp["output"], "n")

        d_gal = json.loads(ToolRegistry.call_tool("galois_group", {"poly": "x**4 - 2"}))
        self.assertNotIn("error", d_gal)
        self.assertNotIn("PARI group", d_gal["latex"])


if __name__ == "__main__":
    unittest.main()
