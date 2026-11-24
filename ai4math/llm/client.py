"""LLM client with tool-calling support via OpenAI-compatible API."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from ai4math.tools.registry import ToolRegistry
from ai4math.tools.theorem_advisor import analyze_problem

# System prompt for the math assistant
SYSTEM_PROMPT = r"""你是一个专业的数学助手，擅长数学分析、抽象代数和概率论。

你可以通过调用工具来执行精确的符号计算，包括：

**数学分析 (SymPy)：** 表达式化简/展开/因式分解、求导、积分、极限、级数展开、方程求解、ODE、矩阵运算、三角化简
**抽象代数 (SymPy)：** 多项式环运算、群论（S_n/Z_n/D_n/A_n）、置换运算、商环、代数结构验证、最小多项式
**概率论 (SymPy)：** 分布信息、期望/方差、概率计算、MGF、特征函数、贝叶斯定理、协方差/相关系数

**高级分析 (SageMath)：** sage_integrate（符号积分，支持含参数和 assumptions）、sage_simplify（高级化简）
**高级代数 (SageMath)：** 有限域多项式分解、Groebner 基、理想成员检验、数域扩张、Galois 群、椭圆曲线、高级群论（中心/换位子群/Sylow子群/共轭类/特征标表）、格运算（Smith/Hermite标准形/LLL约化）
**数论 (SageMath)：** 大整数因式分解、素性检验、欧拉函数、中国剩余定理、模逆
**组合数学 (SageMath)：** 整数分拆、Catalan数、Stirling数、Bell数、Fibonacci数、Bernoulli数、生成函数
**SageMath 通用执行器：** sage_eval 工具可以直接执行任意 SageMath 代码，处理上述工具未覆盖的高级运算

**证明辅助 (SageMath)：** verify_conjecture（批量验证猜想）、explore_structure（探索代数结构：乘法群、二次剩余、幂剩余、类群、素数分裂、二次型表示）、search_counterexample（系统性搜索反例）

**可视化 (matplotlib)：** plot_function（函数图像）、plot_parametric（参数曲线）、plot_implicit（隐式曲线）、plot_inequality_region（不等式区域）、plot_3d（3D 曲面）、plot_riemann_surface（多值复函数三维黎曼面 + 第四维着色）
**可视化 (SageMath)：** sage_plot（函数图像）、sage_implicit_plot（隐式曲线）、sage_region_plot（不等式区域）、sage_plot_3d（3D 曲面）、sage_complex_plot（复变函数色相图）

## 工作原则

1. 对于需要精确计算的问题，**务必调用工具**获取准确结果，不要自己心算
2. 解释你的解题思路和步骤
3. 如果一个问题需要多步计算，可以连续调用多个工具
4. 用中文回复
5. 工具的详细返回结果会由系统自动附加到输出中，你无需重复粘贴原始结果，但应对结果进行解释和分析

## 工具选择策略（重要）

- **简单积分/求导/化简** → 用 SymPy 工具（integrate, differentiate, simplify_expression）
- **含符号参数的复杂积分**（如 $\int \sin^{2s-1}\theta \cos(n\theta) d\theta$）→ **直接用 sage_integrate**，并通过 assumptions 参数指定变量性质（integer, positive, even 等）。sage_integrate 若符号积分超时会自动枚举参数值
- **Gamma 函数/Beta 函数/特殊函数化简** → 用 sage_simplify 或 sage_eval
- **SymPy 工具调用失败或返回未化简结果时** → 改用对应的 SageMath 工具
- **万能后备** → sage_eval 可执行任意 SageMath 代码
- **不要反复用相同工具重试失败的计算**，换一个更强的工具

### 计算策略（重要）

遇到计算量可能很大的问题时，**先用 theorem_advisor 判断规模和可用定理**：
1. 调用 theorem_advisor(problem=问题描述) 分析问题，获取规模估计和定理建议
2. 如果 scale 为 "heavy" 或 "infeasible_brute_force"，**必须先用理论降维**，不要直接暴力计算
3. 根据建议的定理和 sage_hint，选择高效的计算路线
4. 只有 scale 为 "trivial" 或 "moderate" 时才可以直接计算
5. 对于有限域上的曲线点数等问题，优先用 zeta 函数 / Frobenius 特征多项式，而非逐点枚举

### 工具调用效率（重要）

- **把多步搜索/筛选合并成一次 sage_eval 调用**，不要每个候选值单独调用一次工具
- 例如：需要找满足多个条件的最小素数时，写一个完整的 for 循环在一次 sage_eval 中完成全部筛选，而不是逐个素数分别调用
- 每次 sage_eval 应尽量输出完整的中间结果，减少后续调用次数
- 工具调用总次数有上限（默认 40 次），必须合理分配：搜索/筛选阶段尽量用 1-2 次，把剩余次数留给后续计算
- 如果同一个工具连续 3 次返回相同的错误或相同的可疑结果，**立即停止重试**，改用不同的方法或工具

### 遵循预规划指导（重要）

- 系统会在你的对话上下文中注入一段"预规划结果"，其中可能包含**高置信度定理指导**
- 当预规划中出现 `preferred_recipe` 和 `sage_hint` 时，**优先按照给出的代码模板和步骤执行**，不要自行发明替代方案
- 当预规划中出现 `avoid_patterns` 时，**尽量避免**列出的方法（如数值逼近发散级数、逐个候选值调用工具等）
- 如果 sage_hint 中给出了完整的 SageMath 代码模板，直接基于该模板修改执行，不要从头重写

### 证明题策略（重要）

遇到证明题时，按以下流程操作：

1. **直接构造证明**：遇到证明题，默认直接尝试构造证明，不要先做大量数值验证
   - 用 construct_proof 工具建立代数环境并逐步执行证明步骤的计算，获取证明骨架
   - 你负责填充每步之间的逻辑推理和数学论证
   - 证明类型选择：直接证明、反证法、数学归纳法、构造法、分类讨论
2. **用工具验证关键步骤**：证明中的关键等式/不等式/代数恒等式，用计算工具确认正确性
3. **仅在需要时做数值验证**：只有题目明确要求"验证""对 p<N 检验"时，才用 verify_conjecture 批量验证
4. **探索辅助**：如果证明思路不清晰，用 explore_structure 探索相关代数结构寻找线索，用 search_counterexample 排除错误方向
5. **诚实标注**：超出推理能力的步骤明确标注"此步骤依赖 [具体定理名]，以下给出计算验证而非严格证明"

### 可视化工具选择
- **简单函数绘图**（sin, cos, 多项式等）→ matplotlib 工具（plot_function）
- **参数曲线** → plot_parametric
- **隐式曲线/不等式区域** → 优先 SageMath（sage_implicit_plot, sage_region_plot），表达力更强
- **黎曼面 / 多值复变函数分支结构**（如 $z=\sqrt{x}$、$w=z^{1/n}$、$\ln z$、$\sqrt{z^2-1}$ 等）→ **优先调用 plot_riemann_surface**（三维空间投影曲面 + 第四维颜色映射，完整展现多叶粘连与绕支点换叶拓扑，不要仅画二维色相图）
- **单值复变函数零极点/辐角分布**（如 $(z^3-1)/(z^3+1)$、$\zeta(s)$ 等）→ sage_complex_plot（二维色相图）
- **3D 曲面** → 两者均可，SageMath 对符号表达式更友好
- 当用户要求"画图"、"绘制"、"可视化"、"黎曼面"时，主动调用绘图工具

## 输出格式要求

你的回复将被直接粘贴到 Obsidian 等 Markdown 笔记中，因此必须输出**规范的 Markdown 格式**：

1. **数学公式必须使用 LaTeX**：
   - 行内公式用 `$...$`，例如 $f(x) = x^2$
   - 独立公式用 `$$...$$`，独占一行
   - **绝不使用** SymPy 的 pretty-print 文本格式，**绝不使用** Unicode 数学符号代替 LaTeX

2. **结构清晰**：
   - 用 `##` / `###` 标题分层
   - 推导步骤用有序列表 `1. 2. 3.`
   - 重要结论用 `> **结论：**` 引用块高亮

3. **对工具结果进行解释**：
   - 系统会自动展示每个工具调用的完整返回值
   - 你应重点解释结果的数学意义、推导思路、验证过程
"""

ROUTING_PROMPT = """Classify this math question's difficulty. Reply with ONLY one word: "simple" or "complex".

simple = basic calculus, straightforward algebra, direct probability, single-step simplification, standard formulas
complex = multi-step proofs, Galois theory, advanced group theory, complex integrals with parameters, combinatorial identities, anything requiring SageMath

Question: {question}"""

PREPLAN_PROMPT = """你正在为数学求解器做预规划。请基于题目与已有快速分析，输出一个极简 JSON 对象，不要输出任何额外文字。

必须包含这些键：
- "problem_type": 字符串，题型分类
- "should_use_theory_first": 布尔值
- "recommended_tools": 字符串数组，建议优先调用的工具名
- "key_invariants": 字符串数组，建议优先求的中间量/不变量
- "theorem_focus": 字符串数组，应优先锚定的定理或结构
- "invariant_targets": 字符串数组，必须先算出的关键不变量
- "verification_targets": 字符串数组，最终答案前必须检查的验证项
- "strategy": 字符串，控制在 80 字内

要求：
1. 若题目计算规模大，必须令 should_use_theory_first=true
2. 若快速分析已给出 suggested_theorems，应优先围绕这些定理组织策略
3. 对 heavy / infeasible 题，按 theorem -> invariants -> verification 的顺序组织方案
4. 不要建议暴力枚举，除非 scale 是 trivial 或 moderate
5. 输出必须是合法 JSON

题目：
{question}

快速分析：
{analysis}
"""

DECOMPOSE_PROMPT = """你正在为数学求解器做长题分解。请把下面的复杂数学问题拆分为有依赖关系的子问题，输出一个 JSON 对象，不要输出任何额外文字。

必须包含这些键：
- "objects": 字符串数组，题目中出现的关键数学对象
- "subproblems": 数组，每个元素包含 "id"（如 "sp1"）、"statement"（子问题描述）、"depends_on"（依赖的子问题 id 数组）、"domain"（所属领域）
- "final_target": 字符串，最终要计算/证明的目标
- "dependency_order": 字符串数组，按依赖顺序排列的子问题 id

要求：
1. 子问题之间的依赖关系必须正确，后续子问题只能依赖前面的子问题
2. 每个子问题应该是一个可以独立求解的单元
3. 先求常数/参数，再求依赖这些常数的对象，最后做最终计算
4. 输出必须是合法 JSON

题目：
{question}

快速分析：
{analysis}
"""

_COMPLEX_ROUTING_PATTERNS = [
    r"sage(?:math|_)",
    r"galois",
    r"groebner",
    r"mordell[- ]weil",
    r"elliptic\s*curve|椭圆曲线",
    r"number\s*field|数域",
    r"sylow|共轭类|character table|特征标",
    r"smith\s*标准形|hermite\s*标准形|lll",
    r"finite\s*field|有限域|gf\(",
    r"证明|求证|prove|show\s+that",
    r"class\s*number|判别式|整数环基",
    r"conductor|torsion|rank|j-?invariant",
    r"F_\{?\d+\^?\d{2,}\}?|\\mathbb\{F\}|GF\(\d+\^\d{2,}\)",
]

_COMPLEX_ROUTING_HINTS = (
    "证明", "验证", "进一步", "并判断", "并求", "生成元", "扭子群",
    "点数", "hasse", "galois", "groebner", "mordell-weil",
)

_PLOTTING_KEYWORDS_RE = re.compile(
    r"画|绘|图像|图形|曲线图|色相|黎曼面|可视化|三维曲面|plot|graph|draw|sketch|visuali[sz]|riemann\s*surface|phase\s*portrait|surface",
    re.IGNORECASE,
)

_META_SKIP_KEYS = {
    "_display_instruction",
    "title",
    "code",
    "setup_code",
    "input",
    "latex",
    "latex_final",
    "latex_q",
    "latex_r",
    "latex_cov",
    "latex_corr",
    "output",
    "stdout",
    "image_path",
    "steps_detail",
    "steps_summary",
    "PDF_latex",
}


def _as_bool(value: Any, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in ("true", "1", "yes"):
            return True
        if cleaned in ("false", "0", "no", ""):
            return False
    return fallback


def _as_str_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(fallback)
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned if cleaned else list(fallback)


# ---------------------------------------------------------------------------
# Helper: post-process Markdown to fix display math inside blockquotes
# ---------------------------------------------------------------------------

def _fix_blockquote_display_math(text: str) -> str:
    r"""Remove ``> `` prefix from ``$$...$$`` blocks inside blockquotes."""
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip("> ").strip()
        if line.startswith(">") and stripped == "$$":
            math_lines = []
            i += 1
            while i < len(lines):
                inner = lines[i]
                inner_stripped = inner.lstrip("> ").strip()
                if inner.startswith(">") and inner_stripped == "$$":
                    i += 1
                    break
                if inner.startswith("> "):
                    math_lines.append(inner[2:])
                elif inner.startswith(">"):
                    math_lines.append(inner[1:])
                else:
                    math_lines.append(inner)
                i += 1

            result.append(">")
            result.append("$$")
            result.extend(math_lines)
            result.append("$$")
            result.append(">")
        else:
            result.append(line)
            i += 1

    return "\n".join(result)


# ---------------------------------------------------------------------------
# Helper: format a tool call + result as a Markdown block
# ---------------------------------------------------------------------------

def _format_tool_result_md(
    func_name: str,
    arguments: dict,
    result: str,
) -> str | None:
    """Format a *successful* tool result as a Markdown blockquote."""
    if func_name == "theorem_advisor":
        return None

    try:
        data = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        text = str(result).strip()
        if not text:
            return None
        if len(text) > 800:
            text = text[:797] + "..."
        code_lines = ["", "```"]
        for tl in text.splitlines():
            code_lines.append(tl)
        code_lines.append("```")
        return "\n".join(code_lines)

    if not isinstance(data, dict):
        return None
    if data.get("error"):
        return None

    image_path = str(data.get("image_path", "")).strip()
    if image_path:
        title = data.get("title", func_name)
        return f"> 📊 `{func_name}` 绘图结果：\n> ![{title}]({image_path})"

    latex = str(data.get("latex", "")).strip()
    if not latex:
        if data.get("latex_final"):
            latex = str(data["latex_final"]).strip()
        elif data.get("latex_cov") or data.get("latex_corr"):
            cov_l = data.get("latex_cov", "")
            corr_l = data.get("latex_corr", "")
            latex = f"\\operatorname{{Cov}} = {cov_l},\\quad \\rho = {corr_l}"
        elif data.get("latex_q") or data.get("latex_r"):
            latex = f"q = {data.get('latex_q', '')},\\quad r = {data.get('latex_r', '')}"

    if latex and "None" in latex:
        latex = ""

    output = str(data.get("output", "")).strip()
    stdout = str(data.get("stdout", "")).strip()
    steps_summary = str(data.get("steps_summary", "")).strip()

    # Collect extra structured summary fields (e.g. rank, torsion, class_number, counterexamples, solutions)
    extra_items: list[str] = []
    for k, v in data.items():
        if k in _META_SKIP_KEYS or k.startswith("step_"):
            continue
        v_str = str(v).strip()
        if not v_str or v_str == output:
            continue
        if len(v_str) > 240:
            v_str = v_str[:237] + "..."
        extra_items.append(f"{k}: `{v_str}`")

    lines: list[str] = []
    if latex:
        lines.append(f"> 📐 `{func_name}` 计算结果：$${latex}$$")
        if steps_summary:
            for sl in steps_summary.splitlines():
                lines.append(f"> - {sl}")
        elif func_name in ("elliptic_curve_info", "number_field_info", "distribution_info") and extra_items:
            lines.append("> " + " | ".join(extra_items[:6]))
    elif output:
        if "\n" in output or len(output) > 120:
            lines.append(f"> 📐 `{func_name}` 计算结果：")
            lines.append("> ```")
            for ol in output.splitlines():
                lines.append(f"> {ol}")
            lines.append("> ```")
        else:
            lines.append(f"> 📐 `{func_name}` 计算结果：`{output}`")
    elif extra_items:
        lines.append(f"> 📐 `{func_name}` 计算结果：" + "；".join(extra_items[:8]))

    if stdout and stdout != output:
        lines.append("> 打印输出：")
        lines.append("> ```")
        for sl in stdout.splitlines()[:30]:
            lines.append(f"> {sl}")
        lines.append("> ```")

    return "\n".join(lines) if lines else None


class MathLLMClient:
    """LLM client that supports math tool calling."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url or os.getenv(
            "OPENAI_BASE_URL", "https://api.deepseek.com/beta",
        )
        explicit_model = (model or os.getenv("AI4MATH_MODEL", "")).strip()
        self.model = explicit_model or "deepseek-v4-pro"

        self.max_iterations = int(
            os.getenv("AI4MATH_MAX_ITERATIONS", "40"),
        )
        self.max_tokens = int(
            os.getenv("AI4MATH_MAX_TOKENS", "8192"),
        )
        self.temperature = float(
            os.getenv("AI4MATH_TEMPERATURE", "0.0"),
        )
        self.reasoning_effort = os.getenv(
            "AI4MATH_REASONING_EFFORT", "high",
        )
        self.auto_route = _as_bool(os.getenv("AI4MATH_AUTO_ROUTE", "true"), True)

        # If the user explicitly configured AI4MATH_MODEL (or passed model=...) without setting
        # the individual route/planner models, fall back to that explicit model instead of
        # sending requests to non-existent deepseek-v4-* endpoints.
        default_flash = explicit_model or "deepseek-v4-flash"
        default_pro = explicit_model or "deepseek-v4-pro"
        self.flash_model = os.getenv("AI4MATH_FLASH_MODEL", "").strip() or default_flash
        self.pro_model = os.getenv("AI4MATH_PRO_MODEL", "").strip() or default_pro
        self.preplan_enabled = _as_bool(os.getenv("AI4MATH_PREPLAN_ENABLED", "true"), True)
        self.preplan_model = os.getenv("AI4MATH_PREPLAN_MODEL", "").strip() or self.pro_model
        self.preplan_max_tokens = int(
            os.getenv("AI4MATH_PREPLAN_MAX_TOKENS", "512"),
        )
        self.trim_tools = _as_bool(os.getenv("AI4MATH_TRIM_TOOLS", "true"), True)

        self.client = OpenAI(
            api_key=self.api_key, base_url=self.base_url,
        )
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def reset(self):
        """Reset conversation history."""
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def _classify_difficulty(self, question: str, analysis: dict[str, Any] | None = None) -> str:
        """Classify question difficulty with deterministic Sage-heavy heuristics first."""
        if analysis and analysis.get("structural_complexity", {}).get("is_complex"):
            return "complex"
        if analysis and analysis.get("scale") in {"heavy", "infeasible_brute_force"}:
            return "complex"
        lowered = question.lower()
        if any(re.search(pattern, lowered) for pattern in _COMPLEX_ROUTING_PATTERNS):
            return "complex"
        if sum(hint in question or hint in lowered for hint in _COMPLEX_ROUTING_HINTS) >= 2:
            return "complex"
        if len(re.findall(r"[，；。]", question)) >= 2 and sum(
            token in question or token in lowered for token in ("验证", "f_p", "证明", "进一步")
        ) >= 1:
            return "complex"
        try:
            response = self.client.chat.completions.create(
                model=self.flash_model,
                messages=[{
                    "role": "user",
                    "content": ROUTING_PROMPT.format(question=question),
                }],
                max_tokens=8,
                temperature=0.0,
            )
            answer = (response.choices[0].message.content or "").strip().lower()
            if answer == "simple" or ("simple" in answer and "complex" not in answer):
                return "simple"
            return "complex"
        except Exception:
            return "complex"

    def _build_preplan_context(self, analysis: dict[str, Any], plan: dict[str, Any], decomposition: dict[str, Any] | None = None) -> str:
        parts: list[str] = []

        if isinstance(decomposition, dict):
            raw_subs = decomposition.get("subproblems")
            if isinstance(raw_subs, list) and raw_subs:
                valid_subs = [sp_item for sp_item in raw_subs if isinstance(sp_item, dict)]
                if valid_subs:
                    parts.append("子问题分解：")
                    for sp_item in valid_subs:
                        deps_list = _as_str_list(sp_item.get("depends_on"), [])
                        deps = ", ".join(deps_list) or "none"
                        parts.append(
                            f"- [{sp_item.get('id', '?')}] {sp_item.get('statement', '')} "
                            f"(depends: {deps}, domain: {sp_item.get('domain', '?')})"
                        )
                    if decomposition.get("final_target"):
                        parts.append(f"- 最终目标: {decomposition['final_target']}")
                    dep_order = _as_str_list(decomposition.get("dependency_order"), [])
                    if dep_order:
                        parts.append(f"- 求解顺序: {' -> '.join(dep_order)}")
                    parts.append("- 执行规则: 必须按依赖顺序逐步求解，每个子问题完成后再进入下一个。每个子问题的搜索/筛选应合并为一次 sage_eval 调用，不要逐个候选值单独调用工具。")
                    parts.append("")

        strategy = str(plan.get("strategy", ""))
        should_use_theory_first = _as_bool(plan.get("should_use_theory_first"), False)
        recommended_tools = ", ".join(_as_str_list(plan.get("recommended_tools"), [])) or "无"
        key_invariants = ", ".join(_as_str_list(plan.get("key_invariants"), [])) or "无"
        theorem_names = [
            str(item.get("theorem"))
            for item in analysis.get("suggested_theorems", [])
            if isinstance(item, dict) and item.get("theorem")
        ]
        theorem_focus = ", ".join(_as_str_list(plan.get("theorem_focus"), [])) or ", ".join(theorem_names) or "无"
        invariant_targets = ", ".join(_as_str_list(plan.get("invariant_targets"), [])) or ", ".join(
            analysis.get("suggested_invariants", [])
        ) or key_invariants
        verification_targets = ", ".join(_as_str_list(plan.get("verification_targets"), [])) or ", ".join(
            analysis.get("verification_checks", [])
        ) or "无"

        soft_constraints = [sc for sc in analysis.get("soft_constraints", []) if isinstance(sc, dict)]
        top_soft = None
        if soft_constraints:
            top_soft = max(
                soft_constraints,
                key=lambda item: (
                    float(item.get("score", 0.0)),
                    2 if item.get("confidence") == "high" else 1 if item.get("confidence") == "medium" else 0,
                ),
            )
        workflow = analysis.get("workflow", {})
        workflow_order = " -> ".join(workflow.get("phases", [])) or "theorem -> invariants -> verification"
        scale = analysis.get("scale", "unknown")
        hard_constraint = (
            "禁止暴力枚举，必须先锚定定理/结构，再计算关键不变量，并在最终答案前完成 verification checks。"
            if scale in {"heavy", "infeasible_brute_force"} or should_use_theory_first
            else "允许直接计算，但优先使用已有结构、定理建议与中间不变量。"
        )
        top_score = float(top_soft.get("score", 0.0)) if top_soft else 0.0
        # Require at least score >= 2.0 (a regex signal match or >=2 corroborating keywords)
        # before injecting high-confidence recipes, preventing 1-keyword false-positive hijacking.
        if top_soft and (
            (top_soft.get("confidence") == "high" and top_score >= 2.0)
            or top_score >= 4.0
        ):
            recipe = _as_str_list(top_soft.get("preferred_recipe"), [])
            avoids = _as_str_list(top_soft.get("avoid_patterns"), [])
            sage_hint = str(top_soft.get("sage_hint", "")).strip()
            source_tag = " [外部定理库]" if top_soft.get("source") == "external" else ""
            if recipe or avoids or sage_hint:
                parts.extend([
                    f"高置信度定理指导{source_tag} ({top_soft.get('theorem', 'unknown')}, confidence={top_soft.get('confidence', 'unknown')}, score={top_score})：",
                ])
                if recipe:
                    parts.append(f"- preferred_recipe: {' → '.join(recipe)}")
                if avoids:
                    parts.append(f"- avoid_patterns: {' | '.join(avoids)}")
                if sage_hint:
                    parts.append(f"- sage_hint: {sage_hint}")
                parts.append("")

        parts.extend([
            "预规划结果：",
            f"- scale: {scale}",
            f"- problem_type: {plan.get('problem_type', 'unknown')}",
            f"- suggested_theorems: {', '.join(theorem_names) or '无'}",
            f"- theorem_focus: {theorem_focus}",
            f"- recommended_tools: {recommended_tools}",
            f"- key_invariants: {key_invariants}",
            f"- invariant_targets: {invariant_targets}",
            f"- verification_targets: {verification_targets}",
            f"- workflow_order: {workflow_order}",
            f"- strategy: {strategy or analysis.get('recommended_approach', '')}",
            f"- constraint: {hard_constraint}",
            "- execution_rule: 在得到关键 invariants 前不要直接下结论；最终答案前先检查 verification targets。",
        ])
        return "\n".join(parts)

    def _decompose_problem(self, user_message: str, analysis: dict[str, Any]) -> dict[str, Any] | None:
        try:
            response = self.client.chat.completions.create(
                model=self.preplan_model,
                messages=[{
                    "role": "user",
                    "content": DECOMPOSE_PROMPT.format(
                        question=user_message,
                        analysis=json.dumps(analysis, ensure_ascii=False),
                    ),
                }],
                max_tokens=max(self.preplan_max_tokens, 1024),
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = (response.choices[0].message.content or "").strip()
            parsed = json.loads(content)
            if isinstance(parsed, dict) and isinstance(parsed.get("subproblems"), list):
                return parsed
        except Exception:
            return None
        return None

    def _run_preplanning(self, user_message: str, analysis: dict[str, Any], decomposition: dict[str, Any] | None = None) -> dict[str, Any]:
        default_plan = {
            "problem_type": "general",
            "should_use_theory_first": analysis.get("scale") in {"heavy", "infeasible_brute_force"},
            "recommended_tools": ["theorem_advisor"],
            "key_invariants": list(analysis.get("suggested_invariants", [])),
            "theorem_focus": [
                item.get("theorem") for item in analysis.get("suggested_theorems", []) if item.get("theorem")
            ],
            "invariant_targets": list(analysis.get("suggested_invariants", [])),
            "verification_targets": list(analysis.get("verification_checks", [])),
            "strategy": analysis.get("recommended_approach", ""),
        }
        if not self.preplan_enabled:
            return default_plan

        analysis_payload = dict(analysis)
        if decomposition:
            analysis_payload["decomposition"] = decomposition

        parsed: Any = None
        try:
            response = self.client.chat.completions.create(
                model=self.preplan_model,
                messages=[{
                    "role": "user",
                    "content": PREPLAN_PROMPT.format(
                        question=user_message,
                        analysis=json.dumps(analysis_payload, ensure_ascii=False),
                    ),
                }],
                max_tokens=max(self.preplan_max_tokens, 1200) if decomposition else self.preplan_max_tokens,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = (response.choices[0].message.content or "").strip()
            parsed = json.loads(content)
        except Exception:
            parsed = None

        raw = parsed if isinstance(parsed, dict) else {}
        plan = dict(default_plan)
        plan["should_use_theory_first"] = _as_bool(
            raw.get("should_use_theory_first"),
            default_plan["should_use_theory_first"],
        )
        if analysis.get("scale") in {"heavy", "infeasible_brute_force"}:
            plan["should_use_theory_first"] = True

        for list_key in ("recommended_tools", "key_invariants", "theorem_focus", "invariant_targets", "verification_targets"):
            plan[list_key] = _as_str_list(raw.get(list_key), default_plan[list_key])

        if isinstance(raw.get("problem_type"), str) and raw["problem_type"].strip():
            plan["problem_type"] = raw["problem_type"].strip()
        if isinstance(raw.get("strategy"), str) and raw["strategy"].strip():
            plan["strategy"] = raw["strategy"].strip()
        return plan

    def get_tools(self, user_message: str = "") -> list[dict]:
        """Get registered tool schemas, optionally trimming plotting tools when unused."""
        if self.trim_tools and user_message and not _PLOTTING_KEYWORDS_RE.search(user_message):
            return ToolRegistry.get_all_schemas(exclude_categories={"plotting", "sage_plotting"})
        return ToolRegistry.get_all_schemas()

    def _clear_stale_preplan_messages(self) -> None:
        """Remove injected preplanning system messages from earlier turns while keeping SYSTEM_PROMPT."""
        self.messages = [
            msg for msg in self.messages
            if not (msg.get("role") == "system" and msg.get("content") != SYSTEM_PROMPT)
        ]

    def chat(
        self,
        user_message: str,
        on_tool_call=None,
        on_response=None,
        on_route=None,
    ) -> str:
        """Send a message and handle tool calling loop."""
        analysis = analyze_problem(user_message)
        decomposition = None
        if analysis.get("structural_complexity", {}).get("is_complex"):
            decomposition = self._decompose_problem(user_message, analysis)
        preplan = self._run_preplanning(user_message, analysis, decomposition=decomposition)

        effective_model = self.model
        effective_reasoning = self.reasoning_effort
        if self.auto_route:
            difficulty = self._classify_difficulty(user_message, analysis=analysis)
            if difficulty == "simple":
                effective_model = self.flash_model
                effective_reasoning = "none"
            else:
                effective_model = self.pro_model
                effective_reasoning = self.reasoning_effort
            if on_route:
                on_route(difficulty, effective_model)

        self._clear_stale_preplan_messages()
        msg_checkpoint = len(self.messages)
        self.messages.append({"role": "user", "content": user_message})
        self.messages.append({
            "role": "system",
            "content": self._build_preplan_context(analysis, preplan, decomposition=decomposition),
        })

        tools_schema = self.get_tools(user_message)
        collected_parts: list[str] = []
        pending_continuation = False
        iteration = 0

        try:
            while iteration < self.max_iterations:
                iteration += 1

                extra_kwargs = {}
                if "deepseek-v4" in effective_model and effective_reasoning != "none":
                    extra_kwargs["reasoning_effort"] = effective_reasoning
                    extra_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

                response = self.client.chat.completions.create(
                    model=effective_model,
                    messages=self.messages,
                    tools=tools_schema,
                    tool_choice="auto",
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    **extra_kwargs,
                )

                choice = response.choices[0]
                message = choice.message
                self.messages.append(message.model_dump())

                if message.content:
                    if pending_continuation and collected_parts:
                        collected_parts[-1] = collected_parts[-1] + message.content
                    else:
                        collected_parts.append(message.content)
                    if on_response:
                        on_response(message.content)

                if choice.finish_reason == "length":
                    # If the output was truncated mid-tool-call, we MUST supply matching tool responses
                    # for every tool_call_id to satisfy the OpenAI/DeepSeek message protocol.
                    if message.tool_calls:
                        pending_continuation = False
                        for tc in message.tool_calls:
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(
                                    {"error": "模型输出达到 max_tokens 上限导致工具调用参数被截断，请精简参数或拆分步骤后重试"},
                                    ensure_ascii=False,
                                ),
                            })
                        continue

                    pending_continuation = True
                    self.messages.append({
                        "role": "user",
                        "content": "继续（从上次截断处接着写，不要重复已输出的内容）",
                    })
                    continue

                pending_continuation = False

                if not message.tool_calls:
                    final = "\n\n".join(collected_parts)
                    return _fix_blockquote_display_math(final)

                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    raw_args = tool_call.function.arguments or ""
                    try:
                        arguments = json.loads(raw_args)
                        if not isinstance(arguments, dict):
                            raise ValueError("arguments 必须是 JSON 对象")
                    except (json.JSONDecodeError, ValueError) as err:
                        result = json.dumps(
                            {"error": f"工具调用参数 arguments 不是合法 JSON 对象 ({err})，请修正 JSON 语法后重试"},
                            ensure_ascii=False,
                        )
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        })
                        continue

                    result = ToolRegistry.call_tool(func_name, arguments)

                    if on_tool_call:
                        on_tool_call(func_name, arguments, result)

                    formatted = _format_tool_result_md(func_name, arguments, result)
                    if formatted is not None:
                        collected_parts.append(formatted)

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

            collected_parts.append(
                "\n\n> ⚠️ 达到最大工具调用次数"
                f" {self.max_iterations} 次。"
                " 可设置环境变量 `AI4MATH_MAX_ITERATIONS` 调整上限。"
            )
            final = "\n\n".join(collected_parts)
            return _fix_blockquote_display_math(final)
        except KeyboardInterrupt:
            # Roll back incomplete turn so interactive REPL history remains valid
            self.messages = self.messages[:msg_checkpoint]
            raise
