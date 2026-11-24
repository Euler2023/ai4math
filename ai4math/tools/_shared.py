"""Shared safe parsing, formatting, and splitting helpers for AI4Math tools."""

from __future__ import annotations

import ast
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    standard_transformations,
    stringify_expr,
)

MAX_EXPR_LENGTH = 10_000

_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

# Safe whitelist of SymPy functions, constants, and types exposed to expression parsing.
_SAFE_SYMPY_NAMES = (
    # Core types & constructors
    "Symbol", "Integer", "Float", "Rational", "Function", "Matrix", "Tuple",
    # Logic & relations
    "Eq", "Ne", "Lt", "Le", "Gt", "Ge", "And", "Or", "Not", "Piecewise",
    # Calculus & algebra
    "Sum", "Product", "Integral", "Derivative", "Limit", "Mod", "gcd", "lcm",
    # Constants
    "pi", "E", "I", "oo", "zoo", "nan", "true", "false", "EulerGamma", "GoldenRatio", "Catalan",
    # Elementary functions
    "sin", "cos", "tan", "cot", "sec", "csc",
    "asin", "acos", "atan", "atan2", "acot", "asec", "acsc",
    "sinh", "cosh", "tanh", "coth", "sech", "csch",
    "asinh", "acosh", "atanh", "acoth",
    "exp", "log", "ln", "sqrt", "cbrt", "root",
    "Abs", "sign", "floor", "ceiling", "frac", "Max", "Min",
    "re", "im", "conjugate", "arg",
    # Combinatorial & special functions
    "factorial", "factorial2", "binomial", "ff", "rf", "fibonacci", "lucas", "bell", "bernoulli", "catalan",
    "gamma", "loggamma", "polygamma", "digamma", "trigamma", "beta", "zeta", "dirichlet_eta",
    "erf", "erfc", "erfi", "Ei", "li", "Si", "Ci", "Shi", "Chi",
    "besselj", "bessely", "besseli", "besselk", "airyai", "airybi",
    "legendre", "chebyshevt", "chebyshevu", "hermite", "laguerre",
    "LambertW", "Heaviside", "DiracDelta", "KroneckerDelta", "LeviCivita",
)

SAFE_SYMPY_GLOBALS: dict[str, Any] = {
    "__builtins__": {},
    "abs": sp.Abs,
    "min": sp.Min,
    "max": sp.Max,
    "pow": pow,
    "round": round,
    "int": sp.Integer,
    "float": sp.Float,
}
for _sym_name in _SAFE_SYMPY_NAMES:
    if hasattr(sp, _sym_name):
        SAFE_SYMPY_GLOBALS[_sym_name] = getattr(sp, _sym_name)

_COMMON_SYMBOL_NAMES = (
    "x y z t a b c n m k p q s r u v w "
    "alpha beta gamma theta phi psi omega lambda mu sigma rho tau epsilon delta"
).split()

_FORBIDDEN_AST_NODES = (
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
    ast.NamedExpr,
    ast.JoinedStr,
    ast.FormattedValue,
)

_PLOT_COUNTER = 0
_PLOT_LOCK = threading.Lock()


def make_local_dict(positive_names: set[str] | frozenset[str] = frozenset()) -> dict[str, Any]:
    """Build a symbol dictionary with standard mathematical constants."""
    local_dict: dict[str, Any] = {}
    for name in _COMMON_SYMBOL_NAMES:
        if name in positive_names:
            local_dict[name] = sp.Symbol(name, positive=True)
        else:
            local_dict[name] = sp.Symbol(name)
    local_dict["pi"] = sp.pi
    local_dict["e"] = sp.E
    local_dict["E"] = sp.E
    local_dict["I"] = sp.I
    local_dict["oo"] = sp.oo
    local_dict["inf"] = sp.oo
    return local_dict


def _validate_expr_ast(tree: ast.AST) -> None:
    """Reject dangerous AST constructs (dunder attributes, private names, comprehensions)."""
    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_AST_NODES):
            raise ValueError(f"表达式中包含不允许的语法结构: {type(node).__name__}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError(f"表达式中禁止访问内部属性: {node.attr}")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError(f"表达式中禁止引用内部标识符: {node.id}")


def safe_parse_expr(
    expr_str: str,
    local_dict: dict[str, Any] | None = None,
    extra_locals: dict[str, Any] | None = None,
) -> sp.Expr:
    """Safely parse a mathematical expression string into a SymPy expression."""
    if not isinstance(expr_str, str):
        expr_str = str(expr_str)
    cleaned = expr_str.strip()
    if not cleaned:
        raise ValueError("表达式不能为空")
    if len(cleaned) > MAX_EXPR_LENGTH:
        raise ValueError(f"表达式长度超过安全上限 ({MAX_EXPR_LENGTH})")

    eff_locals = dict(local_dict) if local_dict is not None else make_local_dict()
    # If gamma(...) or beta(...) is called as a function, expose sp.gamma / sp.beta
    # instead of shadowing them with a plain Symbol (which implicit_multiplication turns into gamma*x).
    for fn_name in ("gamma", "beta", "zeta", "catalan", "bell", "bernoulli", "fibonacci", "lucas"):
        if re.search(rf"\b{fn_name}\s*\(", cleaned):
            eff_locals.pop(fn_name, None)

    if extra_locals:
        eff_locals.update(extra_locals)

    code = stringify_expr(cleaned, eff_locals, SAFE_SYMPY_GLOBALS, _TRANSFORMATIONS)
    tree = ast.parse(code, "<sympy_expr>", mode="eval")
    _validate_expr_ast(tree)
    return eval(compile(tree, "<sympy_expr>", "eval"), SAFE_SYMPY_GLOBALS, eff_locals)


def get_or_make_symbol(name: str, local_dict: dict[str, Any] | None = None) -> sp.Symbol:
    """Return a pre-defined Symbol from local_dict or create a new one."""
    cleaned = name.strip()
    if local_dict and cleaned in local_dict and isinstance(local_dict[cleaned], sp.Symbol):
        return local_dict[cleaned]
    return sp.Symbol(cleaned)


def safe_literal_eval(raw: str, max_len: int = MAX_EXPR_LENGTH) -> Any:
    """Safely parse Python/JSON literal structures with length guard."""
    if not isinstance(raw, str):
        return raw
    s = raw.strip()
    if len(s) > max_len:
        raise ValueError(f"输入长度超过上限 ({max_len})")
    try:
        return json.loads(s)
    except Exception:
        return ast.literal_eval(s)


def parse_float_expr(val: str | float | int) -> float:
    """Parse a numeric or symbolic constant bound (such as '-2*pi' or 'pi/2') into a float."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    try:
        return float(s)
    except ValueError:
        expr = safe_parse_expr(s)
        evaluated = expr.evalf()
        return float(evaluated)


def split_top_level(text: str, sep: str = ",") -> list[str]:
    """Split text by ``sep`` only at top level (outside parentheses, brackets, braces, and quotes)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote_char: str | None = None
    i = 0
    sep_len = len(sep)

    while i < len(text):
        ch = text[i]
        if quote_char is not None:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(text):
                i += 1
                buf.append(text[i])
            elif ch == quote_char:
                quote_char = None
            i += 1
            continue

        if ch in ("'", '"'):
            quote_char = ch
            buf.append(ch)
            i += 1
            continue

        if ch in "([{":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue

        if depth == 0 and text.startswith(sep, i):
            parts.append("".join(buf).strip())
            buf.clear()
            i += sep_len
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail or parts:
        parts.append(tail)
    return [p for p in parts if p]


def unique_plot_path(plot_dir: Path, prefix: str) -> str:
    """Generate a collision-free plot file path across concurrent workers."""
    global _PLOT_COUNTER
    plot_dir.mkdir(parents=True, exist_ok=True)
    with _PLOT_LOCK:
        _PLOT_COUNTER += 1
        seq = _PLOT_COUNTER
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return str(plot_dir / f"{prefix}_{ts}_{os.getpid()}_{seq}.png")


def format_result(title: str, *, include_display_instruction: bool = True, **kwargs: Any) -> str:
    """Format a tool result dictionary as a JSON string."""
    out: dict[str, Any] = {"title": title}
    for k, v in kwargs.items():
        out[k] = v if isinstance(v, str) else str(v)
    if include_display_instruction:
        out["_display_instruction"] = "你必须在回复中用 $$ LaTeX $$ 展示此工具返回的 latex 字段内容，不得省略"
    return json.dumps(out, ensure_ascii=False, default=str)
