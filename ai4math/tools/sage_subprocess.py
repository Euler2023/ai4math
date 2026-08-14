"""Run one Sage-category tool call in an isolated subprocess."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from typing import Any


def _child_env() -> dict[str, str]:
    """Return the subprocess environment, guaranteeing a writable Sage cache dir.

    SageMath writes its cache to ``DOT_SAGE`` (or ``~/.sage`` by default). In
    containers / sandboxes / read-only homes this default is not writable, which
    makes every Sage tool fail with ``[Errno 30] Read-only file system``. If the
    configured location is missing or not writable, fall back to a temp dir.
    """
    env = os.environ.copy()
    dot_sage = env.get("DOT_SAGE") or os.path.join(os.path.expanduser("~"), ".sage")
    try:
        os.makedirs(dot_sage, exist_ok=True)
        if os.access(dot_sage, os.W_OK):
            return env
    except OSError:
        pass

    fallback = os.path.join(tempfile.gettempdir(), "ai4math_dot_sage")
    os.makedirs(fallback, exist_ok=True)
    env["DOT_SAGE"] = fallback
    return env


def run_sage_tool_subprocess(name: str, arguments: dict[str, Any], timeout: int, cwd: str) -> str:
    payload = json.dumps(
        {"tool_name": name, "arguments": arguments, "cwd": cwd},
        ensure_ascii=False,
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "ai4math.tools.sage_subprocess"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        start_new_session=True,
        env=_child_env(),
    )
    try:
        stdout, stderr = proc.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_process_group(proc, kill=False)
        try:
            stdout, stderr = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            _terminate_process_group(proc, kill=True)
            stdout, stderr = proc.communicate()
        return json.dumps(
            {"error": f"工具 {name} 执行超时 ({timeout}s)，已终止"},
            ensure_ascii=False,
        )

    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        message = stderr.strip() or stdout.strip() or f"工具 {name} 子进程返回无效输出"
        return json.dumps({"error": message}, ensure_ascii=False)

    if envelope.get("ok"):
        return str(envelope.get("result", ""))
    return json.dumps({"error": envelope.get("error", "unknown error")}, ensure_ascii=False)


def _terminate_process_group(proc: subprocess.Popen[str], kill: bool) -> None:
    sig = signal.SIGKILL if kill else signal.SIGTERM
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except ProcessLookupError:
        pass


def _load_all_tools() -> None:
    import ai4math.tools.analysis  # noqa: F401
    import ai4math.tools.algebra  # noqa: F401
    import ai4math.tools.probability  # noqa: F401
    import ai4math.tools.plotting  # noqa: F401
    import ai4math.tools.theorem_advisor  # noqa: F401
    import ai4math.tools.sage_tools  # noqa: F401
    import ai4math.tools.sage_plotting  # noqa: F401


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        cwd = payload.get("cwd")
        if cwd:
            os.chdir(cwd)

        _load_all_tools()

        from ai4math.tools.registry import _execute_registered_tool

        result = _execute_registered_tool(payload["tool_name"], payload.get("arguments", {}))
        sys.stdout.write(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        return 0
    except Exception as e:
        sys.stdout.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
