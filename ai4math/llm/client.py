"""LLM client with tool-calling support via OpenAI-compatible API."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from ai4math.tools.registry import ToolRegistry

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


# ---------------------------------------------------------------------------
# Helper: post-process Markdown to fix display math inside blockquotes
# ---------------------------------------------------------------------------

def _fix_blockquote_display_math(text: str) -> str:
    r"""Remove ``> `` prefix from ``$$...$$`` blocks inside blockquotes.

    In Obsidian, display math (``$$...$$``) inside a ``> `` blockquote
    often fails to render.  This function detects such patterns and
    "breaks out" of the quote for the math lines, e.g.::

        > **结论：** some text
        > $$
        > \int ...
        > $$
        > more text

    becomes::

        > **结论：** some text
        >
        $$
        \int ...
        $$
        >
        > more text
    """
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Detect start of display math in blockquote: "> $$"
        stripped = line.lstrip("> ").strip()
        if (
            line.startswith(">")
            and stripped == "$$"
        ):
            # Collect all lines until closing "> $$"
            math_lines = []
            i += 1
            while i < len(lines):
                inner = lines[i]
                inner_stripped = inner.lstrip("> ").strip()
                if (
                    inner.startswith(">")
                    and inner_stripped == "$$"
                ):
                    # Found closing $$
                    i += 1
                    break
                # Strip the "> " prefix from math content
                if inner.startswith("> "):
                    math_lines.append(inner[2:])
                elif inner.startswith(">"):
                    math_lines.append(inner[1:])
                else:
                    math_lines.append(inner)
                i += 1

            # Emit: blank quote line, math block, blank quote line
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
    """Format a *successful* tool result as a compact Markdown line.

    Returns ``None`` for errors / empty results so that the caller
    can simply skip them — failed tool attempts should not appear in
    the final document.

    Successful results are rendered as a single blockquote line with
    the LaTeX formula, blending naturally into the surrounding text.
    """

    # ---- Parse result --------------------------------------------------
    try:
        data = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        # Non-JSON raw text (e.g. sage_eval stdout).
        text = str(result).strip()
        if not text:
            return None
        # Truncate very long text
        if len(text) > 800:
            text = text[:797] + "..."
        # Show as a compact code block
        code_lines = ["", "```"]
        for tl in text.splitlines():
            code_lines.append(tl)
        code_lines.append("```")
        return "\n".join(code_lines)

    if not isinstance(data, dict):
        return None

    # ---- Skip errors entirely ------------------------------------------
    if data.get("error"):
        return None

    # ---- Extract the meaningful result ---------------------------------
    latex = data.get("latex", "")
    output = data.get("output", "")

    # Skip trivial / None LaTeX
    if latex and "None" in latex:
        latex = ""

    if not latex and not output:
        return None

    # ---- Format as a clean line ----------------------------------------
    if latex:
        return f"> 📐 `{func_name}` 计算结果：$${latex}$$"

    # Fallback to text output
    output = output.strip()
    if not output:
        return None
    if "\n" in output or len(output) > 120:
        # Multi-line output → compact code block in blockquote
        lines = [f"> 📐 `{func_name}` 计算结果：", "> ```"]
        for ol in output.splitlines():
            lines.append(f"> {ol}")
        lines.append("> ```")
        return "\n".join(lines)

    return f"> 📐 `{func_name}` 计算结果：`{output}`"


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
            "OPENAI_BASE_URL", "https://api.openai.com/v1",
        )
        self.model = model or os.getenv("AI4MATH_MODEL", "gpt-4o")

        self.max_iterations = int(
            os.getenv("AI4MATH_MAX_ITERATIONS", "25"),
        )
        self.max_tokens = int(
            os.getenv("AI4MATH_MAX_TOKENS", "8192"),
        )
        self.temperature = float(
            os.getenv("AI4MATH_TEMPERATURE", "0.0"),
        )
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

    def get_tools(self) -> list[dict]:
        """Get all registered tool schemas."""
        return ToolRegistry.get_all_schemas()

    def chat(
        self,
        user_message: str,
        on_tool_call=None,
        on_response=None,
    ) -> str:
        """Send a message and handle tool calling loop.

        Args:
            user_message: The user's message.
            on_tool_call: callback(tool_name, args, result).
            on_response: callback(content) for partial text.

        Returns:
            The final Markdown response (LLM text + tool results).
        """
        self.messages.append(
            {"role": "user", "content": user_message},
        )

        # Collect interleaved LLM text and formatted tool results.
        collected_parts: list[str] = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=self.get_tools(),
                tool_choice="auto",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            choice = response.choices[0]
            message = choice.message

            # Add assistant message to history
            self.messages.append(message.model_dump())

            # Collect any text the model emitted in this round
            if message.content:
                collected_parts.append(message.content)

            # --- Handle truncation (finish_reason == "length") ---
            # The LLM hit its max_tokens limit mid-sentence.
            # Ask it to continue seamlessly.
            if choice.finish_reason == "length":
                self.messages.append({
                    "role": "user",
                    "content": "继续（从上次截断处接着写，不要重复已输出的内容）",
                })
                continue

            # If no tool calls, we're done
            if not message.tool_calls:
                final = "\n\n".join(collected_parts)
                return _fix_blockquote_display_math(final)

            # Process each tool call
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                try:
                    arguments = json.loads(
                        tool_call.function.arguments,
                    )
                except json.JSONDecodeError:
                    arguments = {}

                # Execute the tool
                result = ToolRegistry.call_tool(
                    func_name, arguments,
                )

                if on_tool_call:
                    on_tool_call(func_name, arguments, result)

                # ---- Auto-insert formatted result into output ----
                # Returns None for errors / empty — skip those.
                formatted = _format_tool_result_md(
                    func_name, arguments, result,
                )
                if formatted is not None:
                    collected_parts.append(formatted)

                # Add tool result to messages (for LLM context)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        # Max iterations reached
        collected_parts.append(
            "\n\n> ⚠️ 达到最大工具调用次数"
            f" {self.max_iterations} 次。"
            " 可设置环境变量 `AI4MATH_MAX_ITERATIONS` 调整上限。"
        )
        final = "\n\n".join(collected_parts)
        return _fix_blockquote_display_math(final)
