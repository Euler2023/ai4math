"""Tests for Sage subprocess isolation in ToolRegistry."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ai4math.tools.analysis  # noqa: F401
import ai4math.tools.algebra  # noqa: F401
import ai4math.tools.probability  # noqa: F401
import ai4math.tools.plotting  # noqa: F401

try:
    import ai4math.tools.sage_tools  # noqa: F401
    import ai4math.tools.sage_plotting  # noqa: F401
    HAS_SAGE = True
except ImportError:
    HAS_SAGE = False

from ai4math.tools.registry import ToolRegistry


class TestNonSageRegression(unittest.TestCase):
    def test_simplify_in_process(self):
        r = ToolRegistry.call_tool("simplify_expression", {"expr": "sin(x)**2 + cos(x)**2"})
        data = json.loads(r)
        self.assertNotIn("error", data)
        self.assertEqual(data["output"], "1")


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
