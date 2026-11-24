"""Tests for Sage subprocess isolation and credential/cache hardening in ToolRegistry."""

import importlib.util
import json
import os
import stat
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ai4math.tools.analysis  # noqa: F401
import ai4math.tools.algebra  # noqa: F401
import ai4math.tools.probability  # noqa: F401
import ai4math.tools.plotting  # noqa: F401

HAS_SAGE = importlib.util.find_spec("sage") is not None
if HAS_SAGE:
    import ai4math.tools.sage_tools  # noqa: F401
    import ai4math.tools.sage_plotting  # noqa: F401

from ai4math.tools.registry import ToolRegistry
from ai4math.tools.sage_subprocess import _child_env, _ensure_private_dot_sage


class TestNonSageRegression(unittest.TestCase):
    def test_simplify_in_process(self):
        r = ToolRegistry.call_tool("simplify_expression", {"expr": "sin(x)**2 + cos(x)**2"})
        data = json.loads(r)
        self.assertNotIn("error", data)
        self.assertEqual(data["output"], "1")

    def test_child_env_strips_secrets_and_secures_dot_sage(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-secret-key-123",
                "OPENAI_BASE_URL": "https://api.example.com",
                "CUSTOM_API_KEY": "custom-secret",
                "DOT_SAGE": "/proc/nonexistent_readonly_sage_dir",
            },
            clear=False,
        ):
            env = _child_env()
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("OPENAI_BASE_URL", env)
            self.assertNotIn("CUSTOM_API_KEY", env)
            dot_sage = env.get("DOT_SAGE", "")
            self.assertTrue(os.path.isdir(dot_sage))
            st_mode = stat.S_IMODE(os.lstat(dot_sage).st_mode)
            self.assertEqual(st_mode, 0o700)

    def test_private_dot_sage_per_uid(self):
        path = _ensure_private_dot_sage()
        self.assertTrue(os.path.isdir(path))
        self.assertEqual(stat.S_IMODE(os.lstat(path).st_mode), 0o700)


@unittest.skipUnless(HAS_SAGE, "SageMath not available")
class TestSageSubprocess(unittest.TestCase):
    def test_number_theory_factor(self):
        r = ToolRegistry.call_tool("number_theory_operation", {"n": "91", "operation": "factor"})
        data = json.loads(r)
        self.assertNotIn("error", data)
        self.assertIn("7", data.get("factorization", ""))

    def test_sage_eval_simple(self):
        r = ToolRegistry.call_tool("sage_eval", {"code": "2**100"})
        data = json.loads(r)
        self.assertNotIn("error", data)
        self.assertIn("1267650600228229401496703205376", data.get("output", ""))

    def test_sage_eval_cannot_read_parent_api_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-super-secret-do-not-leak"}, clear=False):
            r = ToolRegistry.call_tool(
                "sage_eval",
                {"code": "import os\nos.environ.get('OPENAI_API_KEY', 'STRIPPED')"},
            )
        data = json.loads(r)
        self.assertEqual(data.get("output"), "STRIPPED")
        self.assertNotIn("sk-super-secret-do-not-leak", r)

    def test_timeout_kills_hung_sage(self):
        r = ToolRegistry.call_tool(
            "sage_eval",
            {"code": "import time\ntime.sleep(9999)\nresult = 1"},
            timeout=3,
        )
        data = json.loads(r)
        self.assertIn("error", data)
        self.assertIn("超时", data["error"])

    def test_recovery_after_timeout(self):
        ToolRegistry.call_tool(
            "sage_eval",
            {"code": "import time\ntime.sleep(9999)\nresult = 1"},
            timeout=2,
        )
        r = ToolRegistry.call_tool("number_theory_operation", {"n": "15", "operation": "factor"})
        data = json.loads(r)
        self.assertNotIn("error", data)
        self.assertIn("3", data.get("factorization", ""))


if __name__ == "__main__":
    unittest.main()
