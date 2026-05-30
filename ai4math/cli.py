"""Interactive CLI for AI4Math."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# Load tools (triggers registration via decorators)
import ai4math.tools.analysis  # noqa: F401
import ai4math.tools.algebra   # noqa: F401
import ai4math.tools.probability  # noqa: F401
import ai4math.tools.plotting  # noqa: F401
import ai4math.tools.theorem_advisor  # noqa: F401

try:
    import ai4math.tools.sage_tools  # noqa: F401
    import ai4math.tools.sage_plotting  # noqa: F401
    _HAS_SAGE = True
except ImportError:
    _HAS_SAGE = False

from ai4math.tools.registry import ToolRegistry
from ai4math.llm.client import MathLLMClient
from ai4math.cli_input import expand_at_paths, make_session, prompt_line

console = Console()

# prompt_toolkit session for the interactive REPL. Created lazily in
# `_run_interactive` so non-interactive entry points (one-shot, batch, pipe)
# don't pay the import + history-file cost.
_session = None

# Conversation history for Markdown export
_conversation: list[dict[str, str]] = []  # [{"role": "user"/"assistant"/"tool", "content": "..."}]
_last_response: str = ""  # Raw Markdown of last assistant response


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_banner():
    """Print welcome banner."""
    banner = Text()
    banner.append("AI4Math", style="bold cyan")
    banner.append(" - LLM 数学工具调用系统\n", style="white")
    engines = "SymPy"
    if _HAS_SAGE:
        engines += " + SageMath"
    banner.append(f"数学分析 | 抽象代数 | 概率论  ({engines})\n", style="dim")
    banner.append(f"已注册 {len(ToolRegistry.get_tool_names())} 个工具", style="green")
    console.print(Panel(banner, box=box.DOUBLE, border_style="cyan"))


def print_tools():
    """Print all registered tools."""
    table = Table(title="已注册的数学工具", box=box.ROUNDED, border_style="cyan")
    table.add_column("工具名称", style="bold yellow")
    table.add_column("类别", style="magenta")
    table.add_column("描述", style="white")

    cat_emojis = {
        "analysis": "📐", "algebra": "🔢", "probability": "🎲",
        "sage_algebra": "🔮", "sage_number_theory": "🔢",
        "sage_combinatorics": "🎯", "sage_general": "⚡",
    }
    for tool in ToolRegistry.list_tools():
        cat = tool["category"]
        emoji = cat_emojis.get(cat, "🔧")
        table.add_row(tool["name"], f"{emoji} {cat}", tool["description"])

    console.print(table)


def on_tool_call(name: str, args: dict, result: str):
    """Callback when a tool is called."""
    console.print(f"  [dim]🔧 调用工具:[/dim] [bold yellow]{name}[/bold yellow]")
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 80:
            v_str = v_str[:77] + "..."
        console.print(f"     [dim]{k}=[/dim][cyan]{v_str}[/cyan]")

    # Record tool call in conversation
    _conversation.append({
        "role": "tool",
        "content": f"**🔧 工具调用:** `{name}({', '.join(f'{k}={v!r}' for k, v in args.items())})`",
    })


def on_route(difficulty: str, model: str):
    """Callback when auto-routing selects a model."""
    label = "简单" if difficulty == "simple" else "复杂"
    style = "green" if difficulty == "simple" else "yellow"
    console.print(f"  [dim]🔀 任务分类:[/dim] [{style}]{label}[/{style}] → [bold]{model}[/bold]")


# ---------------------------------------------------------------------------
# Clipboard & save
# ---------------------------------------------------------------------------

def _copy_to_clipboard(text: str) -> bool:
    """Try to copy text to system clipboard. Returns True on success."""
    for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"],
                ["pbcopy"], ["clip.exe"]):
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            proc.communicate(text.encode("utf-8"))
            if proc.returncode == 0:
                return True
        except FileNotFoundError:
            continue
    return False


def _save_conversation(filepath: str | None = None) -> str:
    """Save entire conversation as a Markdown file."""
    if not filepath:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        filepath = str(output_dir / f"ai4math_{timestamp}.md")

    lines = [
        "# AI4Math 对话记录",
        "",
        f"> 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
    ]

    for entry in _conversation:
        role = entry["role"]
        content = entry["content"]
        if role == "user":
            lines.append("## 🧑 问题\n")
            lines.append(content)
            lines.append("")
        elif role == "assistant":
            lines.append("## 🤖 回答\n")
            lines.append(content)
            lines.append("")
        elif role == "tool":
            lines.append(content)
            lines.append("")
        lines.append("---")
        lines.append("")

    Path(filepath).write_text("\n".join(lines), encoding="utf-8")
    return filepath


def _save_last_response(filepath: str | None = None) -> str:
    """Save only the last assistant response as a Markdown file."""
    if not _last_response:
        return ""

    if not filepath:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        filepath = str(output_dir / f"ai4math_{timestamp}.md")

    Path(filepath).write_text(_last_response, encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _read_multiline() -> str:
    """Read multi-line input until user types closing \"\"\" or an empty line twice."""
    console.print('[dim]  多行输入模式（输入 """ 或连续两个空行结束）：[/dim]')
    lines: list[str] = []
    empty_count = 0
    while True:
        try:
            line = prompt_line(
                _session,
                "[bold green]  ... [/bold green]",
                fallback=console.input,
            )
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip() == '"""':
            break
        if line.strip() == "":
            empty_count += 1
            if empty_count >= 2:
                # Remove trailing empty lines
                while lines and lines[-1].strip() == "":
                    lines.pop()
                break
        else:
            empty_count = 0
        lines.append(line)
    return "\n".join(lines)


def _make_client() -> MathLLMClient:
    """Create LLM client from env vars."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "")
    model = os.getenv("AI4MATH_MODEL", "")

    if not api_key:
        console.print("[bold red]错误:[/bold red] 未设置 OPENAI_API_KEY 环境变量")
        console.print("请在项目根目录创建 .env 文件或设置环境变量：")
        console.print("  [cyan]export OPENAI_API_KEY=your-api-key[/cyan]")
        sys.exit(1)

    return MathLLMClient(api_key=api_key, base_url=base_url or None, model=model or None)


def _do_chat(client: MathLLMClient, user_input: str, *, save_path: str = "") -> str:
    """Send user_input to LLM and display result. Returns raw Markdown response."""
    global _last_response

    _conversation.append({"role": "user", "content": user_input})

    console.print()
    response = client.chat(user_input, on_tool_call=on_tool_call, on_route=on_route)

    _last_response = response
    _conversation.append({"role": "assistant", "content": response})

    # Display rendered Markdown
    console.print()
    console.print(Panel(
        Markdown(response),
        title="[bold cyan]AI4Math[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    # Auto-save if requested
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        Path(save_path).write_text(response, encoding="utf-8")
        console.print(f"[green]✓ 已保存到:[/green] [bold]{save_path}[/bold]")

    return response


# ---------------------------------------------------------------------------
# Non-interactive mode
# ---------------------------------------------------------------------------

def _run_oneshot(question: str, save_path: str = ""):
    """Run a single question and exit."""
    load_dotenv()
    client = _make_client()
    try:
        _do_chat(client, question, save_path=save_path)
    except Exception as e:
        console.print(f"[bold red]错误:[/bold red] {e}")
        sys.exit(1)


def _batch_worker(args: tuple) -> dict:
    """Process a single question in a subprocess. Must be top-level for pickling."""
    os.setpgrp()
    import atexit, signal
    atexit.register(lambda: os.killpg(0, signal.SIGTERM))

    i, question, output_dir = args

    from dotenv import load_dotenv
    load_dotenv()

    # Each process imports tools and creates its own client
    import ai4math.tools.analysis   # noqa: F401
    import ai4math.tools.algebra    # noqa: F401
    import ai4math.tools.probability  # noqa: F401
    import ai4math.tools.plotting   # noqa: F401
    try:
        import ai4math.tools.sage_tools     # noqa: F401
        import ai4math.tools.sage_plotting  # noqa: F401
    except ImportError:
        pass

    from ai4math.llm.client import MathLLMClient

    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "")
    model = os.getenv("AI4MATH_MODEL", "")
    client = MathLLMClient(
        api_key=api_key,
        base_url=base_url or None,
        model=model or None,
    )

    tool_calls = []
    route_info = None

    def _on_tool(name, args_dict, result):
        args_short = ", ".join(f"{k}={str(v)[:60]}" for k, v in args_dict.items())
        tool_calls.append(f"{name}({args_short})")

    def _on_route(difficulty, model_name):
        nonlocal route_info
        route_info = (difficulty, model_name)

    t0 = time.time()
    try:
        response = client.chat(question, on_tool_call=_on_tool, on_route=_on_route)
        elapsed = time.time() - t0
        error = None
    except Exception as e:
        elapsed = time.time() - t0
        response = f"**错误：** {e}"
        error = str(e)

    q_file = str(Path(output_dir) / f"q{i:03d}.md")
    q_content = f"# 第 {i} 题\n\n## 问题\n\n{question}\n\n## 回答\n\n{response}\n"
    Path(q_file).write_text(q_content, encoding="utf-8")

    return {
        "i": i,
        "question": question,
        "q_file": q_file,
        "elapsed": elapsed,
        "error": error,
        "tool_calls": tool_calls,
        "route_info": route_info,
        "response": response,
    }


def _run_batch(file_path: str, output_dir: str = "", workers: int = 1, timeout: int = 300):
    """Run batch processing on a file with multiple questions."""
    load_dotenv()

    p = Path(file_path)
    if not p.exists():
        console.print(f"[bold red]错误:[/bold red] 文件不存在: {file_path}")
        sys.exit(1)

    content = p.read_text(encoding="utf-8").strip()
    questions = [q.strip() for q in content.split("---") if q.strip()]

    if not questions:
        console.print("[yellow]文件中未找到问题。[/yellow]")
        return

    if not output_dir:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = str(Path("output") / f"batch_{ts}")
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # --- Setup logging ---
    log_file = out_path / "batch.log"
    logger = logging.getLogger("ai4math.batch")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)

    total = len(questions)
    mode = f"并行 ×{workers} (多进程)" if workers > 1 else "串行"
    console.print(f"[bold cyan]批量处理:[/bold cyan] 共 {total} 道题（{mode}），单题超时 {timeout}s，结果保存到 [bold]{output_dir}/[/bold]")
    console.print(f"[dim]日志文件: {log_file}[/dim]")
    console.print()

    logger.info(f"批量处理开始: {total} 道题, 模式={mode}, 源文件={file_path}")

    results: dict[int, tuple[str, str, float]] = {}
    batch_start = time.time()

    task_args = [(i, q, output_dir) for i, q in enumerate(questions, 1)]

    with ProcessPoolExecutor(max_workers=max(workers, 1)) as executor:
        futures = {
            executor.submit(_batch_worker, arg): arg[0]
            for arg in task_args
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                r = future.result(timeout=timeout)
                i = r["i"]
                elapsed = r["elapsed"]

                # Log tool calls and route
                if r["route_info"]:
                    d, m = r["route_info"]
                    logger.info(f"[Q{i:03d}] 路由: {d} → {m}")
                for tc in r["tool_calls"]:
                    logger.info(f"[Q{i:03d}] 工具调用: {tc}")

                if r["error"]:
                    logger.error(f"[Q{i:03d}] 失败: {elapsed:.1f}s, 错误={r['error']}")
                else:
                    logger.info(f"[Q{i:03d}] 完成: {elapsed:.1f}s, 响应长度={len(r['response'])}")

                # Console output
                console.print(f"[bold cyan]━━━ 第 {i}/{total} 题完成 ({elapsed:.1f}s) ━━━[/bold cyan]")
                q_short = r["question"][:100]
                console.print(f"[dim]{q_short}{'...' if len(r['question']) > 100 else ''}[/dim]")
                if r["route_info"]:
                    d, m = r["route_info"]
                    label = "简单" if d == "simple" else "复杂"
                    style = "green" if d == "simple" else "yellow"
                    console.print(f"  [dim]🔀 任务分类:[/dim] [{style}]{label}[/{style}] → [bold]{m}[/bold]")
                console.print()
                console.print(Panel(
                    Markdown(r["response"]),
                    title=f"[bold cyan]第 {i}/{total} 题[/bold cyan]",
                    border_style="cyan",
                    padding=(1, 2),
                ))
                console.print(f"[green]✓ 已保存到:[/green] {r['q_file']}")
                console.print()

                results[i] = (r["question"], r["q_file"], elapsed)

            except TimeoutError:
                logger.error(f"[Q{idx:03d}] 超时 ({timeout}s)")
                results[idx] = (questions[idx - 1], "", float(timeout))
                console.print(f"[bold red]第 {idx} 题超时 ({timeout}s)，已跳过[/bold red]")
                q_file = out_path / f"q{idx:03d}.md"
                q_file.write_text(
                    f"# 第 {idx} 题\n\n## 问题\n\n{questions[idx-1]}\n\n## 回答\n\n**超时 ({timeout}s)**\n",
                    encoding="utf-8",
                )
            except Exception as e:
                logger.error(f"[Q{idx:03d}] 异常: {e}")
                console.print(f"[bold red]第 {idx} 题异常:[/bold red] {e}")

    batch_elapsed = time.time() - batch_start

    summary_lines = [
        f"# AI4Math 批量处理结果\n",
        f"> 源文件：{file_path}",
        f"> 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 共 {total} 道题（{mode}），总耗时 {batch_elapsed:.1f}s\n",
        "---\n",
    ]
    for i in sorted(results.keys()):
        question, _, elapsed = results[i]
        summary_lines.append(f"## 第 {i} 题 ({elapsed:.1f}s)\n")
        summary_lines.append(f"**问题：** {question[:200]}\n")
        summary_lines.append(f"**结果：** [q{i:03d}.md](q{i:03d}.md)\n")

    summary_file = out_path / "summary.md"
    summary_file.write_text("\n".join(summary_lines), encoding="utf-8")

    logger.info(f"批量处理完成: {total} 道题, 总耗时={batch_elapsed:.1f}s, 成功={len(results)}, 失败={total - len(results)}")

    console.print(f"[bold green]批量处理完成！[/bold green] 共 {total} 题，耗时 {batch_elapsed:.1f}s")
    console.print(f"[green]汇总文件:[/green] {summary_file}")
    console.print(f"[green]日志文件:[/green] {log_file}")


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def _run_interactive():
    """Run interactive REPL."""
    global _last_response, _session

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "")
    model = os.getenv("AI4MATH_MODEL", "")

    if not api_key:
        console.print("[bold red]错误:[/bold red] 未设置 OPENAI_API_KEY 环境变量")
        console.print("请在项目根目录创建 .env 文件或设置环境变量：")
        console.print("  [cyan]export OPENAI_API_KEY=your-api-key[/cyan]")
        console.print("  [cyan]export OPENAI_BASE_URL=https://api.deepseek.com/beta[/cyan]  (可选)")
        console.print("  [cyan]export AI4MATH_MODEL=deepseek-v4-pro[/cyan]  (可选)")
        sys.exit(1)

    print_banner()

    console.print(f"[dim]模型: {model or 'deepseek-v4-pro (默认)'}[/dim]")
    if base_url:
        console.print(f"[dim]API: {base_url}[/dim]")

    client = MathLLMClient(api_key=api_key, base_url=base_url or None, model=model or None)

    if client.auto_route:
        console.print(f"[dim]路由: 自动 (flash={client.flash_model}, pro={client.pro_model})[/dim]")
    console.print()

    # Initialize prompt_toolkit session with @<path> + slash completion and a
    # persistent history file. Falls back to console.input if unavailable.
    history_dir = Path.home() / ".cache" / "ai4math"
    try:
        history_dir.mkdir(parents=True, exist_ok=True)
        history_path: str | None = str(history_dir / "repl_history")
    except OSError:
        history_path = None
    _session = make_session(history_file=history_path)

    console.print("[dim]输入数学问题开始对话。特殊命令：[/dim]")
    console.print('[dim]  \"\"\"     - 多行输入模式    /reset  - 重置对话[/dim]')
    console.print("[dim]  /tools  - 显示所有工具    /save   - 保存对话[/dim]")
    console.print("[dim]  /copy   - 复制最后回答    /last   - 显示原始 Markdown[/dim]")
    console.print("[dim]  /help   - 显示帮助        /quit   - 退出[/dim]")
    console.print('[dim]  @<path> - Tab 补全文件路径，发送时会自动内联文件内容[/dim]')
    console.print()

    while True:
        try:
            user_input = prompt_line(
                _session,
                "[bold green]You > [/bold green]",
                fallback=console.input,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]再见！[/dim]")
            break

        if not user_input:
            continue

        # --- Multi-line trigger ---
        if user_input == '"""' or user_input.lower() == "/ml":
            user_input = _read_multiline()
            if not user_input.strip():
                console.print("[yellow]输入为空，已取消。[/yellow]")
                continue
            # Show collected input
            console.print(Panel(
                user_input,
                title="[bold]多行输入内容[/bold]",
                border_style="green",
                padding=(0, 2),
            ))
        elif user_input.startswith('"""') and len(user_input) > 3:
            # Inline start: """some text... continues until closing """
            rest = user_input[3:]
            if rest.endswith('"""'):
                # Single-line wrapped in """..."""
                user_input = rest[:-3]
            else:
                # Start of multi-line block
                lines = [rest]
                while True:
                    try:
                        line = prompt_line(
                            _session,
                            "[bold green]  ... [/bold green]",
                            fallback=console.input,
                        )
                    except (EOFError, KeyboardInterrupt):
                        break
                    if line.strip().endswith('"""'):
                        remaining = line.strip()[:-3]
                        if remaining:
                            lines.append(remaining)
                        break
                    lines.append(line)
                user_input = "\n".join(lines)

        # --- Commands ---
        if user_input.startswith("/"):
            cmd = user_input.lower().strip()
            parts = cmd.split(maxsplit=1)
            cmd_name = parts[0]
            cmd_arg = parts[1] if len(parts) > 1 else ""

            if cmd_name in ("/quit", "/exit", "/q"):
                console.print("[dim]再见！[/dim]")
                break

            elif cmd_name == "/tools":
                print_tools()
                continue

            elif cmd_name in ("/reset", "/clear"):
                client.reset()
                _conversation.clear()
                _last_response = ""
                console.print("[green]对话已重置。[/green]")
                continue

            elif cmd_name == "/copy":
                if not _last_response:
                    console.print("[yellow]暂无回答可复制。[/yellow]")
                else:
                    if _copy_to_clipboard(_last_response):
                        console.print("[green]✓ 最后回答的 Markdown 已复制到剪贴板[/green]")
                    else:
                        console.print("[yellow]未检测到剪贴板工具 (xclip/xsel)，已输出原始 Markdown：[/yellow]")
                        console.print()
                        console.print(_last_response)
                continue

            elif cmd_name == "/last":
                if not _last_response:
                    console.print("[yellow]暂无回答。[/yellow]")
                else:
                    console.print(Panel(
                        _last_response,
                        title="[bold]原始 Markdown（可直接复制）[/bold]",
                        border_style="green",
                        padding=(1, 2),
                    ))
                continue

            elif cmd_name == "/save":
                if cmd_arg == "last":
                    if not _last_response:
                        console.print("[yellow]暂无回答可保存。[/yellow]")
                    else:
                        path = _save_last_response()
                        console.print(f"[green]✓ 最后回答已保存到:[/green] [bold]{path}[/bold]")
                else:
                    if not _conversation:
                        console.print("[yellow]暂无对话可保存。[/yellow]")
                    else:
                        custom_path = cmd_arg if cmd_arg and cmd_arg != "last" else None
                        path = _save_conversation(custom_path)
                        console.print(f"[green]✓ 对话已保存到:[/green] [bold]{path}[/bold]")
                continue

            elif cmd_name in ("/ml", "/multiline"):
                user_input = _read_multiline()
                if not user_input.strip():
                    console.print("[yellow]输入为空，已取消。[/yellow]")
                    continue
                console.print(Panel(
                    user_input,
                    title="[bold]多行输入内容[/bold]",
                    border_style="green",
                    padding=(0, 2),
                ))
                # Fall through to send to LLM

            elif cmd_name == "/help":
                console.print(Panel(
                    "[bold]AI4Math 使用帮助[/bold]\n\n"
                    "[bold]输入方式：[/bold]\n"
                    '  直接输入    单行问题\n'
                    '  \"\"\"         进入多行输入模式（再输 \"\"\" 或连续两个空行结束）\n'
                    '  \"\"\"...\"\"\"   行内多行包裹\n'
                    "  /ml         同 \"\"\"\n\n"
                    "[bold]示例问题：[/bold]\n"
                    "  • 化简 sin(x)^2 + cos(x)^2\n"
                    "  • 求 ∫x²e^(-x)dx\n"
                    "  • 对称群 S4 的阶是多少？\n"
                    "  • 正态分布 N(0,1) 的矩母函数\n"
                    "  • 求多项式 x^4 - 2 的 Galois 群\n\n"
                    "[bold]Markdown 输出：[/bold]\n"
                    "  /copy       复制最后回答的 Markdown 到剪贴板\n"
                    "  /last       显示最后回答的原始 Markdown\n"
                    "  /save       保存整个对话为 .md 文件\n"
                    "  /save last  仅保存最后一条回答\n"
                    "  /save x.md  保存到指定文件名\n\n"
                    "[bold]命令行用法：[/bold]\n"
                    '  ai4math "问题"              直接提问并退出\n'
                    "  ai4math -f question.md      从文件读取问题\n"
                    "  echo \"问题\" | ai4math       管道输入\n"
                    "  ai4math -o result.md \"问题\"  提问并保存结果\n\n"
                    "[dim]其他：/tools /reset /help /quit[/dim]",
                    title="帮助",
                    border_style="cyan",
                ))
                continue
            else:
                console.print(f"[yellow]未知命令: {cmd}[/yellow]")
                continue

        # --- Send to LLM ---
        try:
            expanded, inlined = expand_at_paths(user_input)
            if inlined:
                for path in inlined:
                    console.print(f"  [dim]📎 已内联文件:[/dim] [cyan]{path}[/cyan]")
            _do_chat(client, expanded)
            console.print("[dim]提示: /copy 复制 Markdown | /save 保存对话 | /last 查看原始 Markdown[/dim]")
        except Exception as e:
            console.print(f"[bold red]错误:[/bold red] {e}")

        console.print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        prog="ai4math",
        description="AI4Math - LLM 数学工具调用系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  ai4math                              交互模式
  ai4math "化简 sin(x)^2+cos(x)^2"      直接提问
  ai4math -f question.md               从文件读取问题
  ai4math -b questions.md              批量处理（用 --- 分隔多道题）
  ai4math -b questions.md -w 5         5 题并行处理
  ai4math -b questions.md -w 5 -o res/ 并行处理并指定输出目录
  echo "求导 x^3" | ai4math            管道输入
  ai4math -o result.md "问题"           提问并保存结果
""",
    )
    parser.add_argument("question", nargs="?", default=None,
                        help="直接提问（单次模式）")
    parser.add_argument("-f", "--file", default=None,
                        help="从文件读取问题（支持纯文本和 Markdown）")
    parser.add_argument("-b", "--batch", default=None,
                        help="批量处理文件（用 --- 分隔多道题）")
    parser.add_argument("-w", "--workers", type=int, default=1,
                        help="批量处理并行数（默认 1，即串行）")
    parser.add_argument("--timeout", type=int, default=300,
                        help="批量处理单题超时秒数（默认 300）")
    parser.add_argument("-o", "--output", default="",
                        help="将回答保存到指定文件或目录")
    parser.add_argument("-t", "--temperature", type=float,
                        default=None,
                        help="控制输出随机性 (0=确定性, 1=创造性, 默认0)")
    parser.add_argument("-n", "--max-iterations", type=int,
                        default=None,
                        help="工具调用最大轮数（默认 100）")

    args = parser.parse_args()

    # Apply temperature if specified via CLI
    if args.temperature is not None:
        os.environ["AI4MATH_TEMPERATURE"] = str(args.temperature)

    if args.max_iterations is not None:
        os.environ["AI4MATH_MAX_ITERATIONS"] = str(args.max_iterations)
    else:
        os.environ.setdefault("AI4MATH_MAX_ITERATIONS", "100")

    # --- Batch mode ---
    if args.batch:
        _run_batch(args.batch, output_dir=args.output, workers=args.workers, timeout=args.timeout)
        return

    # --- Pipe / stdin mode ---
    if not sys.stdin.isatty() and args.question is None and args.file is None:
        question = sys.stdin.read().strip()
        if question:
            _run_oneshot(question, save_path=args.output)
            return

    # --- File input mode ---
    if args.file:
        p = Path(args.file)
        if not p.exists():
            console.print(f"[bold red]错误:[/bold red] 文件不存在: {args.file}")
            sys.exit(1)
        question = p.read_text(encoding="utf-8").strip()
        if question:
            _run_oneshot(question, save_path=args.output)
        return

    # --- Direct question mode ---
    if args.question:
        _run_oneshot(args.question, save_path=args.output)
        return

    # --- Interactive mode ---
    _run_interactive()


if __name__ == "__main__":
    main()
