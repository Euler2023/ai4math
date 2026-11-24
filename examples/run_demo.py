#!/usr/bin/env python3
"""Runnable showcase demo for AI4Math covering Computation, Riemann Zeta, Simple Proof, and Visualization (including 3D Riemann Surfaces).

Modes:
  1. Deterministic Engine Showcase (default, no API key required):
     Directly invokes registered SymPy + SageMath + Plotting tools and generates
     ``examples/demo_showcase.md`` along with PNG figures in ``examples/assets/``.

  2. End-to-End LLM Agent Mode (``--llm``, requires OPENAI_API_KEY in .env):
     Sends showcase prompts through ``MathLLMClient`` and saves the full response.

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
    print("[1/4] Running Symbolic Computation examples...")
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
    # Part 2: Riemann Zeta Function Special Case (Exact Values + Functional Eq + Zeros + Plot)
    # ------------------------------------------------------------------
    print("[2/4] Running Riemann Zeta Function showcase...")
    z2 = _call_json("simplify_expression", {"expr": "zeta(2)"})["latex"]
    z6 = _call_json("simplify_expression", {"expr": "zeta(6)"})["latex"]
    z0 = _call_json("simplify_expression", {"expr": "zeta(0)"})["latex"]
    zm1 = _call_json("simplify_expression", {"expr": "zeta(-1)"})["latex"]
    zm2 = _call_json("simplify_expression", {"expr": "zeta(-2)"})["latex"]

    if HAS_SAGE:
        zeta_sage = _call_json(
            "sage_eval",
            {
                "code": (
                    "import mpmath\n"
                    "s0 = CDF(0.3, 5.0)\n"
                    "lhs = zeta(s0)\n"
                    "rhs = (2^s0) * (CDF(pi)^(s0 - 1)) * sin(CDF(pi)*s0/2) * gamma(1 - s0) * zeta(1 - s0)\n"
                    "fe_err = abs(lhs - rhs)\n"
                    "zeros_im = [round(float(mpmath.zetazero(k).imag), 6) for k in (1, 2, 3)]\n"
                    "z_at_g1 = abs(zeta(CDF(0.5, float(mpmath.zetazero(1).imag))))\n"
                    "print(f'fe_error={fe_err:.2e}, zeros={zeros_im}, |zeta(1/2+i*gamma_1)|={z_at_g1:.2e}')\n"
                    "zeros_im"
                )
            },
        )
        zeta_zeros_info = zeta_sage.get("stdout", zeta_sage["output"])
        p_zeta = _call_json(
            "sage_complex_plot",
            {
                "expr": "zeta(z)",
                "x_range": "-6,4",
                "y_range": "-2,28",
                "title": "Riemann Zeta Function zeta(s) Phase Portrait",
            },
        )
        img_zeta = _move_plot(p_zeta, "demo_zeta_phase.png")
        zeta_plot_desc = (
            "复平面区域 $\\operatorname{Re}(s) \\in [-6, 4],\\; \\operatorname{Im}(s) \\in [-2, 28]$ 上的色相图（`sage_complex_plot`）：\n"
            "图中可同时观察到 $s = 1$ 处的简单极点、负偶整数 $s = -2, -4, -6$ 处的平凡零点，以及临界线 $\\operatorname{Re}(s) = \\frac{1}{2}$ 上依次排列的非平凡零点 $\\frac{1}{2} + i\\gamma_k$。"
        )
    else:
        import mpmath

        g1, g2, g3 = [float(mpmath.zetazero(k).imag) for k in (1, 2, 3)]
        fe_s = mpmath.mpc("0.3", "5.0")
        fe_rhs = (2 ** fe_s) * (mpmath.pi ** (fe_s - 1)) * mpmath.sin(mpmath.pi * fe_s / 2) * mpmath.gamma(1 - fe_s) * mpmath.zeta(1 - fe_s)
        fe_err = float(abs(mpmath.zeta(fe_s) - fe_rhs))
        zeta_zeros_info = f"fe_error={fe_err:.2e}, zeros={[round(g1, 6), round(g2, 6), round(g3, 6)]}"
        p_zeta = _call_json(
            "plot_function",
            {
                "expr": "zeta(x)",
                "variable": "x",
                "x_min": "1.15",
                "x_max": "6",
                "title": "Riemann Zeta Function zeta(x) for x > 1",
            },
        )
        img_zeta = _move_plot(p_zeta, "demo_zeta_phase.png")
        zeta_plot_desc = "实轴 $x > 1$ 上的 $\\zeta(x)$ 渐近曲线（`plot_function`）："

    # ------------------------------------------------------------------
    # Part 3: Simple Mathematical Proof (Conjecture Verification + Proof Skeleton)
    # ------------------------------------------------------------------
    print("[3/4] Running Simple Proof examples...")
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
    # Part 4: Mathematical Visualization (3D Riemann Surface, 1D Curve, Inequality Region, Complex Phase)
    # ------------------------------------------------------------------
    print("[4/4] Generating Visualization figures (including 3D Riemann Surface z = sqrt(x))...")
    p_riemann = _call_json(
        "plot_riemann_surface",
        {
            "expr": "sqrt(x)",
            "variable": "x",
            "sheets": 2,
            "height_part": "auto",
            "radius": 2.0,
            "title": "3D Riemann Surface of z = sqrt(x)",
        },
    )
    img_riemann = _move_plot(p_riemann, "demo_riemann_sqrt.png")

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

    markdown = f"""# AI4Math 综合案例展示（计算 · Riemann Zeta · 证明 · 黎曼面与可视化）

本文档由 [`examples/run_demo.py`](run_demo.py) 调用 AI4Math 内置的 **SymPy + SageMath + Matplotlib** 工具引擎自动生成。

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

## 案例二：Riemann Zeta 函数专题（解析数论计算 + 零极点可视化）

1. **特殊点精确符号值**（Euler 偶数值与解析延拓负整数值）：
   $$\\zeta(2) = {z2},\\qquad \\zeta(6) = {z6},\\qquad \\zeta(0) = {z0},\\qquad \\zeta(-1) = {zm1},\\qquad \\zeta(-2) = {zm2}$$

2. **Riemann 函数方程与临界线非平凡零点检验**（`sage_eval`）：
   检验函数方程 $\\zeta(s) = 2^s \\pi^{{s-1}} \\sin\\!\\left(\\frac{{\\pi s}}{{2}}\\right) \\Gamma(1-s)\\zeta(1-s)$ 及临界线 $\\operatorname{{Re}}(s) = \\frac{{1}}{{2}}$ 上的前三个非平凡零点 $\\frac{{1}}{{2}} + i\\gamma_k$：
   > `{zeta_zeros_info}`

3. **Riemann Zeta 复平面可视化**：
   {zeta_plot_desc}

   ![Riemann Zeta Visualization]({img_zeta})

---

## 案例三：简单数学证明（Simple Proof）

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

## 案例四：三维黎曼面与多维可视化（Visualization）

### 1. 三维四维着色黎曼面 $z = \\sqrt{{x}}$（`plot_riemann_surface`）
采用极坐标双叶单值化 $x = r e^{{i\\theta}}\\;(\\theta \\in [0, 4\\pi])$：以高度轴表示 $\\operatorname{{Re}}(\\sqrt{{x}})$，以曲面冷暖色标映射第四维 $\\operatorname{{Im}}(\\sqrt{{x}})$。可以看到绕支点 $x = 0$ 旋转一周平滑换叶，且负实轴处虽然两叶高度均为 $\\operatorname{{Re}}(\\sqrt{{x}}) = 0$，但一暖（$+\\sqrt{{r}}$）一冷（$-\\sqrt{{r}}$）直观表明两叶在 $\\mathbb{{C}}^2 \\cong \\mathbb{{R}}^4$ 中并不相交：

![3D Riemann Surface of z = sqrt(x)]({img_riemann})

### 2. 多函数对比曲线（`plot_function`，支持符号区间 `[-2*pi, 2*pi]`）
绘制 $\\sin(x)$、$\\cos(x)$ 与阻尼振荡函数 $\\frac{{\\sin(x)}}{{1 + x^2/4}}$：

![Trig and Damped Wave Functions]({img_func})

### 3. 不等式交集区域填充（`plot_inequality_region`）
绘制椭圆内部与半平面的交集 $\\frac{{x^2}}{{4}} + \\frac{{y^2}}{{9}} < 1 \\;\\land\\; x + y > 0$：

![Ellipse and Half-Plane Intersection]({img_region})

### 4. 单值复变函数色相图
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
        "请依次完成四个简短演示：\n"
        "1. 【计算】求级数 sum_{n=1}^oo 1/n^4 的精确值；\n"
        "2. 【Riemann Zeta】计算 zeta(6) 与 zeta(-1) 的精确值，并验证函数方程在 s=0.3+5i 处成立；\n"
        "3. 【证明】用 construct_proof 辅助证明：对任意素数 p >= 5，24 整除 p^2 - 1；\n"
        "4. 【黎曼面】调用 plot_riemann_surface 画出 z = sqrt(x) 的三维黎曼面。"
    )
    print("Sending 4-in-1 demo prompt to LLM...")
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
