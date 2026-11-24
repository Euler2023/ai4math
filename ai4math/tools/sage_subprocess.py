"""Run one tool call in an isolated subprocess with credential stripping and process-group cleanup."""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
from typing import Any

_SENSITIVE_ENV_EXACT = {
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
    "DEEPSEEK_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "HF_TOKEN",
    "HUGGINGFACE_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
}

_SENSITIVE_ENV_SUFFIXES = (
    "_API_KEY",
    "_SECRET",
    "_SECRET_KEY",
    "_ACCESS_TOKEN",
    "_AUTH_TOKEN",
    "_PASSWORD",
    "_CREDENTIAL",
    "_CREDENTIALS",
)

_SAGE_PLOTTING_TOOLS = {
    "sage_plot",
    "sage_implicit_plot",
    "sage_region_plot",
    "sage_plot_3d",
    "sage_complex_plot",
}

_SAGE_GENERAL_TOOLS = {
    "number_theory_operation",
    "finite_field_polynomial",
    "groebner_basis",
    "ideal_membership",
    "number_field_info",
    "galois_group",
    "galois_group_chebotarev",
    "elliptic_curve_info",
    "advanced_group_theory",
    "combinatorics_operation",
    "lattice_operation",
    "sage_integrate",
    "sage_simplify",
    "sage_eval",
    "verify_conjecture",
    "explore_structure",
    "search_counterexample",
    "construct_proof",
}


def _is_sensitive_env_key(key: str) -> bool:
    upper = key.upper()
    if upper in _SENSITIVE_ENV_EXACT:
        return True
    return any(upper.endswith(suffix) for suffix in _SENSITIVE_ENV_SUFFIXES)


def _ensure_private_dot_sage() -> str:
    """Create and validate a per-user 0700 fallback DOT_SAGE directory."""
    uid = os.getuid() if hasattr(os, "getuid") else 0
    candidate = os.path.join(tempfile.gettempdir(), f"ai4math_dot_sage_{uid}")
    try:
        os.makedirs(candidate, mode=0o700, exist_ok=True)
        st = os.lstat(candidate)
        if (
            stat.S_ISDIR(st.st_mode)
            and not stat.S_ISLNK(st.st_mode)
            and (not hasattr(os, "getuid") or st.st_uid == uid)
        ):
            os.chmod(candidate, 0o700)
            if os.access(candidate, os.W_OK | os.X_OK):
                return candidate
    except OSError:
        pass
    return tempfile.mkdtemp(prefix="ai4math_dot_sage_")


def _child_env() -> dict[str, str]:
    """Return a sanitized subprocess environment with a writable private DOT_SAGE dir."""
    env = {k: v for k, v in os.environ.items() if not _is_sensitive_env_key(k)}
    dot_sage = env.get("DOT_SAGE") or os.path.join(os.path.expanduser("~"), ".sage")
    try:
        os.makedirs(dot_sage, exist_ok=True)
        if os.access(dot_sage, os.W_OK):
            return env
    except OSError:
        pass

    env["DOT_SAGE"] = _ensure_private_dot_sage()
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
    for mod in (
        "ai4math.tools.analysis",
        "ai4math.tools.algebra",
        "ai4math.tools.probability",
        "ai4math.tools.plotting",
        "ai4math.tools.theorem_advisor",
        "ai4math.tools.sage_tools",
        "ai4math.tools.sage_plotting",
    ):
        try:
            importlib.import_module(mod)
        except ImportError:
            continue


def _load_tools_for_name(tool_name: str) -> None:
    """Import only the module needed for ``tool_name`` first to avoid ~0.4s extra import cost."""
    if tool_name in _SAGE_PLOTTING_TOOLS:
        import ai4math.tools.sage_plotting  # noqa: F401
        return
    if tool_name in _SAGE_GENERAL_TOOLS:
        import ai4math.tools.sage_tools  # noqa: F401
        return
    if tool_name == "theorem_advisor":
        import ai4math.tools.theorem_advisor  # noqa: F401
        return
    _load_all_tools()


def main() -> int:
    real_stdout = sys.stdout
    try:
        payload = json.loads(sys.stdin.read())
        cwd = payload.get("cwd")
        if cwd:
            os.chdir(cwd)

        tool_name = payload["tool_name"]
        _load_tools_for_name(tool_name)

        from ai4math.tools.registry import _REGISTRY, _execute_registered_tool

        if tool_name not in _REGISTRY:
            _load_all_tools()

        # Isolate any stray print() in tool implementations from corrupting the JSON IPC channel.
        with contextlib.redirect_stdout(sys.stderr):
            result = _execute_registered_tool(tool_name, payload.get("arguments", {}))

        real_stdout.write(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        real_stdout.flush()
        return 0
    except Exception as e:
        real_stdout.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        real_stdout.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
