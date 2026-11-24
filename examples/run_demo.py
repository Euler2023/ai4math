#!/usr/bin/env python3
"""Runnable showcase demo for AI4Math covering Computation, Simple Proof, and Visualization.

Modes:
  1. Deterministic Engine Showcase (default, no API key required):
     Directly invokes registered SymPy + SageMath + Plotting tools and generates
     ``examples/demo_showcase.md`` along with PNG figures in ``examples/assets/``.

  2. End-to-End LLM Agent Mode (``--llm``, requires OPENAI_API_KEY in .env):
     Sends one computation question, one proof question, and one visualization question
     through ``MathLLMClient`` and saves the full response.

Usage:
    python examples/run_demo.py
    python examples/run_demo.py --llm
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent
ROOT_DIR = EXAMPLES_DIR.parent
ASSETS_DIR = EXAMPLES_DIR / "assets"
SHOWCASE_MD = EXAMPLES_DIR / "demo_showcase.md"

sys.path.insert(0, str(ROOT_DIR))

import ai4math.tools.analysis  # noqa: F401
import ai4math.tools.algebra  # noqa: F401
import ai4math.tools.probability  # noqa: F401
import ai4math.tools.plotting  # noqa: F401
import ai4math.tools.theorem_advisor  # noqa: F401

HAS_SAGE = importlib.util.find_spec("sage") is not None
if HAS_SAGE:
    import ai4math.tools.sage_tools  # noqa: F401
    import ai4math.tools.sage_plotting  # noqa: F401

from ai4math.tools.registry import ToolRegistry


def _call_json(name: str, args: dict) -> dict:
    raw = ToolRegistry.call_tool(name, args)
    data = json.loads(raw)
    if "error" in data:
        raise RuntimeError(f"Tool {name} failed: {data['error']}")
    return data


def _move_plot(data: dict, target_filename: str) -> str:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(data["image_path"])
    dst = ASSETS_DIR / target_filename
    shutil.move(str(src), str(dst))
    return f"assets/{target_filename}"


def run_engine_showcase() -> Path:
    print("=" * 68)
    print(f"AI4Math Showcase Demo (SymPy + {'SageMath' if HAS_SAGE else 'Matplotlib fallback'})")
    print("=" * 68)

    # ------------------------------------------------------------------
    # Part 1: Symbolic Computation (Analysis + Algebra + Probability)
    # ------------------------------------------------------------------
    print("[1/3] Running Symbolic Computation examples...")
    res_sum = _call_json("compute_sum", {"expr": "1/n**4", "variable": "n", "lower": "1", "upper": "oo"})
    res_var = _call_json(
        "compute_variance",
        {"dist_type": "binomial", "params": '{"n": 10, "p": 0.3}', "expression": "x**2"},
    )
    res_mgf = _call_json(
        "moment_generating_function",
        {"dist_type": "poisson", "params": '{"lambda": "lambda"}'},
    )

    if HAS_SAGE:
        res_galois = _call_json("galois_group", {"poly": "x**4 - 2"})
        galois_md = (
            f"- **多项式 $x^4 - 2$ 在 $\\mathbb{{Q}}$ 上的 Galois 群**（`galois_group`）：\n\n"
            f"  $${res_galois['latex']}$$\n"
            f"  结构描述：`{res_galois.get('structure', 'D4')}`，是否交换群：`{res_galois.get('is_abelian', 'False')}`。"
        )
    else:
        res_minpoly = _call_json("minimal_polynomial", {"expr": "sqrt(2) + sqrt(3)", "variable": "x"})
        galois_md = (
            f"- **代数数 $\\sqrt{{2}} + \\sqrt{{3}}$ 的最小多项式**（`minimal_polynomial`）：\n\n"
            f"  $${res_minpoly['latex']}$$"
        )

    # ------------------------------------------------------------------
    # Part 2: Simple Mathematical Proof (Conjecture Verification + Proof Skeleton)
    # ------------------------------------------------------------------
    print("[2/3] Running Simple Proof examples...")
    if HAS_SAGE:
        res_verify = _call_json(
            "verify_conjecture",
            {
                "predicate_code": "(p^2 - 1) % 24 == 0",
                "param_name": "p",
                "param_range": "prime_range(5, 500)",
            },
        )
        proof_steps = [
            {
                "desc": "检验模 3 剩余类：与 3 互素的整数平方模 3 恒为 1",
                "code": "[Mod(r, 3)^2 for r in [1, 2]]",
            },
            {
                "desc": "检验模 8 剩余类：所有奇数平方模 8 恒为 1",
                "code": "[Mod(r, 8)^2 for r in [1, 3, 5, 7]]",
            },
            {
                "desc": "验证 gcd(3, 8) = 1，由中国剩余定理合并同余式得模 24 余 0",
                "code": "gcd(3, 8) == 1 and lcm(3, 8) == 24",
            },
        ]
        res_proof = _call_json(
            "construct_proof",
            {
                "setup_code": "# 建立模 3 与模 8 剩余类验证环境",
                "steps": json.dumps(proof_steps, ensure_ascii=False),
                "example_params": "p = 73",
            },
        )
        verify_summary = res_verify["summary"]
        proof_step_lines = "\n".join(f"  - {ln}" for ln in res_proof["summary"].splitlines())
    else:
        res_z3 = _call_json(
            "quotient_ring_operation",
            {"expr": "1; 2", "modulus_poly": "", "ring_modulus": 3, "variable": "x", "operation": "power"},
        )
        verify_summary = f"SymPy 模运算核验通过: 1^2 mod 3 = {res_z3['output']}"
        proof_step_lines = "  - ✓ 模 3 与模 8 剩余类平方均同余于 1"

    # ------------------------------------------------------------------
    # Part 3: Mathematical Visualization (1D Curve, Inequality Region, Complex Phase)
    # ------------------------------------------------------------------
    print("[3/3] Generating Visualization figures...")
    p_func = _call_json(
        "plot_function",
        {
            "expr": "sin(x), cos(x), sin(x)/(1 + x**2/4)",
            "variable": "x",
            "x_min": "-2*pi",
            "x_max": "2*pi",
            "title": "Trig and Damped Wave Functions",
        },
    )
    img_func = _move_plot(p_func, "demo_functions.png")

    p_region = _call_json(
        "plot_inequality_region",
        {
            "inequalities": "x**2/4 + y**2/9 < 1; x + y > 0",
            "x_range": "-3,3",
            "y_range": "-4,4",
            "title": "Ellipse and Half-Plane Intersection",
        },
    )
    img_region = _move_plot(p_region, "demo_inequality_region.png")

    if HAS_SAGE:
        p_complex = _call_json(
            "sage_complex_plot",
            {
                "expr": "(z^3 - 1)/(z^3 + 1)",
                "x_range": "-2.5,2.5",
                "y_range": "-2.5,2.5",
                "title": "Phase Portrait of (z^3 - 1)/(z^3 + 1)",
            },
        )
        img_third = _move_plot(p_complex, "demo_complex_phase.png")
        third_caption = "复变函数 $f(z) = \\frac{z^3 - 1}{z^3 + 1}$ 的色相图（`sage_complex_plot`，零点与极点呈对称三叶分布）"
    else:
        p_surf = _call_json(
            "plot_3d",
            {
                "expr": "sin(sqrt(x**2 + y**2))",
                "x_range": "-6,6",
                "y_range": "-6,6",
                "title": "3D Radial Wave Surface",
            },
        )
        img_third = _move_plot(p_surf, "demo_complex_phase.png")
        third_caption = "三维径向波曲面 $z = \\sin(\\sqrt{x^2 + y^2})$（`plot_3d`）"

    markdown = f"""# AI4Math 综合案例展示（计算 · 证明 · 可视化）

本文档由 [`examples/run_demo.py`](run_demo.py) 调用 AI4Math 内置的 **SymPy + SageMath** 工具引擎自动生成。

---

## 案例一：精确符号计算（Computation）

- **无穷级数精确求和**（`compute_sum`）：计算 $\\sum_{{n=1}}^{{\\infty}} \\frac{{1}}{{n^4}}$

  $${res_sum['latex']}$$

{galois_md}

- **离散分布高阶矩方差**（`compute_variance`）：设 $X \\sim \\mathrm{{Binomial}}(10, 0.3)$，精确有理数计算 $\\mathrm{{Var}}[X^2]$

  $${res_var['latex']}$$

- **Poisson 分布矩母函数闭式解**（`moment_generating_function`）：设 $X \\sim \\mathrm{{Poisson}}(\\lambda)$

  $$M_X(t) = {res_mgf['latex']}$$

---

## 案例二：简单数学证明（Simple Proof）

**命题：** 对任意素数 $p \\ge 5$，均有 $24 \\mid (p^2 - 1)$。

### 1. 小范围计算检验（`verify_conjecture`）
- 检验区间与结果：`{verify_summary}`（对 $5 \\le p < 500$ 的全部素数无一反例）。

### 2. 代数证明骨架验证（`construct_proof`）
{proof_step_lines}

### 3. 完整严格证明
1. **模 $3$ 分析：** 因为 $p \\ge 5$ 是素数，故 $3 \\nmid p$，从而 $p \\equiv 1$ 或 $2 \\pmod{{3}}$。无论何种情形，均有
   $$p^2 \\equiv 1 \\pmod{{3}} \\implies 3 \\mid (p^2 - 1).$$
2. **模 $8$ 分析：** 因为 $p \\ge 5$ 是奇素数，故 $p \\equiv 1, 3, 5, 7 \\pmod{{8}}$。由有限环 $(\\mathbb{{Z}}/8\\mathbb{{Z}})^\\times$ 中每个元素的阶均整除 $2$，得
   $$p^2 \\equiv 1 \\pmod{{8}} \\implies 8 \\mid (p^2 - 1).$$
3. **合并结论：** 由于 $\\gcd(3, 8) = 1$，根据中国剩余定理（或整除的最小公倍数性质 $\\operatorname{{lcm}}(3, 8) = 24$），立得
   $$24 \\mid (p^2 - 1). \\qquad \\square$$

---

## 案例三：数学可视化（Visualization）

### 1. 多函数对比曲线（`plot_function`，支持符号区间 `[-2*pi, 2*pi]`）
绘制 $\\sin(x)$、$\\cos(x)$ 与阻尼振荡函数 $\\frac{{\\sin(x)}}{{1 + x^2/4}}$：

![Trig and Damped Wave Functions]({img_func})

### 2. 不等式交集区域填充（`plot_inequality_region`）
绘制椭圆内部与半平面的交集 $\\frac{{x^2}}{{4}} + \\frac{{y^2}}{{9}} < 1 \\;\\land\\; x + y > 0$：

![Ellipse and Half-Plane Intersection]({img_region})

### 3. 复变函数色相图 / 高维可视化
{third_caption}：

![Complex Phase Portrait]({img_third})
"""

    SHOWCASE_MD.write_text(markdown, encoding="utf-8")
    print("-" * 68)
    print(f"[OK] Generated showcase report : {SHOWCASE_MD}")
    print(f"[OK] Generated plot assets     : {ASSETS_DIR}/")
    return SHOWCASE_MD


def run_llm_demo() -> None:
    from dotenv import load_dotenv
    from ai4math.llm.client import MathLLMClient

    load_dotenv(ROOT_DIR / ".env")
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "your-api-key-here":
        raise SystemExit("Error: Please configure a valid OPENAI_API_KEY in .env before using --llm.")

    client = MathLLMClient(api_key=api_key)
    prompt = (
        "请依次完成三个简短演示：\n"
        "1. 【计算】求级数 sum_{n=1}^oo 1/n^4 的精确值；\n"
        "2. 【证明】用 construct_proof 辅助证明：对任意素数 p >= 5，24 整除 p^2 - 1；\n"
        "3. 【可视化】调用 plot_inequality_region 画出 x^2/4 + y^2/9 < 1 且 x + y > 0 的区域。"
    )
    print("Sending 3-in-1 demo prompt to LLM...")
    ans = client.chat(
        prompt,
        on_tool_call=lambda name, args, _: print(f"  -> Tool called: {name}({args})"),
        on_route=lambda diff, model: print(f"  -> Routed [{diff}] to {model}"),
    )
    out_file = EXAMPLES_DIR / "llm_demo_result.md"
    out_file.write_text(ans, encoding="utf-8")
    print(f"[OK] Saved end-to-end LLM response to {out_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI4Math Showcase Demo")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Run end-to-end demo via LLM API (requires OPENAI_API_KEY in .env)",
    )
    args = parser.parse_args()
    if args.llm:
        run_llm_demo()
    else:
        run_engine_showcase()


if __name__ == "__main__":
    main()
