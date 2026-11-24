"""Visualization tools powered by matplotlib."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sympy as sp

from ai4math.tools._shared import (
    format_result,
    make_local_dict,
    parse_float_expr,
    safe_parse_expr,
    split_top_level,
    unique_plot_path,
)
from ai4math.tools.registry import math_tool

_LOCAL_DICT = make_local_dict()
_PLOT_DIR = Path("output/plots")

_CUSTOM_NUMPY_MAP = {
    "Min": np.minimum,
    "Max": np.maximum,
    "min": np.minimum,
    "max": np.maximum,
    "gamma": np.vectorize(lambda v: math.gamma(float(v)) if not (v <= 0 and float(v).is_integer()) else float("nan")),
}


def _save_fig(fig, name: str) -> str:
    path = unique_plot_path(_PLOT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _result(title: str, **kwargs) -> str:
    return format_result(title, include_display_instruction=False, **kwargs)


def _parse_range_pair(range_str: str) -> tuple[float, float]:
    parts = split_top_level(range_str, ",")
    if len(parts) != 2:
        raise ValueError(f"区间格式应为 'min,max'，收到: {range_str!r}")
    return parse_float_expr(parts[0]), parse_float_expr(parts[1])


def _eval_1d(var: sp.Symbol, sym_expr: sp.Expr, xv: np.ndarray) -> np.ndarray:
    modules = [_CUSTOM_NUMPY_MAP, "numpy", "scipy", "math"]
    f = sp.lambdify(var, sym_expr, modules=modules)
    try:
        raw = f(xv)
        arr = np.broadcast_to(np.asarray(raw), xv.shape)
        return np.real_if_close(arr.astype(complex))
    except Exception:
        # Scalar fallback for special functions without vectorization
        vals = []
        for x_item in xv:
            try:
                v = complex(sym_expr.subs(var, float(x_item)).evalf())
                vals.append(v.real if abs(v.imag) < 1e-9 else float("nan"))
            except Exception:
                vals.append(float("nan"))
        return np.asarray(vals, dtype=float)


def _eval_2d(x_sym: sp.Symbol, y_sym: sp.Symbol, sym_expr: sp.Expr, X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    modules = [_CUSTOM_NUMPY_MAP, "numpy", "scipy"]
    f = sp.lambdify((x_sym, y_sym), sym_expr, modules=modules)
    raw = f(X, Y)
    arr = np.broadcast_to(np.asarray(raw), X.shape)
    return np.real_if_close(arr.astype(complex))


@math_tool(category="plotting", description="Plot 1D functions. Multiple functions separated by commas, e.g. 'sin(x), cos(x)'")
def plot_function(expr: str, variable: str = "x", x_min: str = "-10", x_max: str = "10", title: str = "") -> str:
    """Plot one or more 1D functions.

    Args:
        expr: Function expression(s), comma-separated. e.g. 'sin(x), cos(x), x**2'
        variable: Variable name, default x
        x_min: x-axis minimum (supports constants like '-2*pi')
        x_max: x-axis maximum (supports constants like '2*pi')
        title: Plot title (use English only)
    """
    try:
        var = sp.Symbol(variable)
        exprs = split_top_level(expr, ",")
        sym_exprs = [safe_parse_expr(e, local_dict=_LOCAL_DICT, extra_locals={variable: var}) for e in exprs]

        xv = np.linspace(parse_float_expr(x_min), parse_float_expr(x_max), 500)
        fig, ax = plt.subplots(figsize=(8, 5))
        for se in sym_exprs:
            yv = _eval_1d(var, se, xv)
            ax.plot(xv, yv, label=f"${sp.latex(se)}$")
        ax.set_xlabel(f"${variable}$")
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_title(title or ", ".join(exprs))

        path = _save_fig(fig, "func")
        return _result("Function plot", image_path=path, output=f"Plotted {len(exprs)} function(s)")
    except Exception as e:
        return _result("Plot error", error=str(e))


@math_tool(category="plotting", description="Plot parametric curve (x(t), y(t))")
def plot_parametric(x_expr: str, y_expr: str, t_min: str = "0", t_max: str = "6.2832", title: str = "") -> str:
    """Plot a parametric curve.

    Args:
        x_expr: x(t) expression
        y_expr: y(t) expression
        t_min: Parameter t minimum (supports constants like '0')
        t_max: Parameter t maximum (supports constants like '2*pi')
        title: Plot title (use English only)
    """
    try:
        t = sp.Symbol("t")
        sx = safe_parse_expr(x_expr, local_dict=_LOCAL_DICT, extra_locals={"t": t})
        sy = safe_parse_expr(y_expr, local_dict=_LOCAL_DICT, extra_locals={"t": t})

        tv = np.linspace(parse_float_expr(t_min), parse_float_expr(t_max), 500)
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.plot(_eval_1d(t, sx, tv), _eval_1d(t, sy, tv))
        ax.set_xlabel(f"$x = {sp.latex(sx)}$")
        ax.set_ylabel(f"$y = {sp.latex(sy)}$")
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.set_title(title or "Parametric curve")

        path = _save_fig(fig, "parametric")
        return _result("Parametric curve", image_path=path, output="Plotted parametric curve")
    except Exception as e:
        return _result("Plot error", error=str(e))


@math_tool(category="plotting", description="Plot implicit curve f(x,y)=0, e.g. x**2 + y**2 - 1")
def plot_implicit(equation: str, x_range: str = "-5,5", y_range: str = "-5,5", title: str = "") -> str:
    """Plot an implicit curve f(x,y)=0.

    Args:
        equation: Equation or left side (right side is 0). e.g. 'x**2 + y**2 - 1' or 'x**3 + y**3 = 3*x*y'
        x_range: x range, format 'min,max'
        y_range: y range, format 'min,max'
        title: Plot title (use English only)
    """
    try:
        x, y = sp.Symbol("x"), sp.Symbol("y")
        eq_clean = equation.strip()
        if "==" in eq_clean:
            lhs, rhs = eq_clean.split("==", 1)
            sym_eq = safe_parse_expr(lhs, local_dict=_LOCAL_DICT, extra_locals={"x": x, "y": y}) - safe_parse_expr(
                rhs, local_dict=_LOCAL_DICT, extra_locals={"x": x, "y": y}
            )
        elif "=" in eq_clean:
            lhs, rhs = eq_clean.split("=", 1)
            sym_eq = safe_parse_expr(lhs, local_dict=_LOCAL_DICT, extra_locals={"x": x, "y": y}) - safe_parse_expr(
                rhs, local_dict=_LOCAL_DICT, extra_locals={"x": x, "y": y}
            )
        else:
            sym_eq = safe_parse_expr(eq_clean, local_dict=_LOCAL_DICT, extra_locals={"x": x, "y": y})

        xr = _parse_range_pair(x_range)
        yr = _parse_range_pair(y_range)
        xv = np.linspace(xr[0], xr[1], 400)
        yv = np.linspace(yr[0], yr[1], 400)
        X, Y = np.meshgrid(xv, yv)
        Z = _eval_2d(x, y, sym_eq, X, Y)

        fig, ax = plt.subplots(figsize=(7, 7))
        ax.contour(X, Y, Z, levels=[0], colors="blue")
        ax.set_xlabel("$x$")
        ax.set_ylabel("$y$")
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.set_title(title or f"${sp.latex(sym_eq)} = 0$")

        path = _save_fig(fig, "implicit")
        return _result("Implicit curve", image_path=path, output="Plotted implicit curve")
    except Exception as e:
        return _result("Plot error", error=str(e))


@math_tool(category="plotting", description="Plot inequality region, supports multiple inequalities (intersection)")
def plot_inequality_region(inequalities: str, x_range: str = "-5,5", y_range: str = "-5,5", title: str = "") -> str:
    """Plot inequality region.

    Args:
        inequalities: Semicolon-separated inequalities. e.g. 'x**2+y**2 < 1; x > 0'
        x_range: x range, format 'min,max'
        y_range: y range, format 'min,max'
        title: Plot title (use English only)
    """
    try:
        xr = _parse_range_pair(x_range)
        yr = _parse_range_pair(y_range)
        xv = np.linspace(xr[0], xr[1], 500)
        yv = np.linspace(yr[0], yr[1], 500)
        X, Y = np.meshgrid(xv, yv)

        x_sym, y_sym = sp.Symbol("x"), sp.Symbol("y")
        mask = np.ones_like(X, dtype=bool)
        for ineq_str in inequalities.split(";"):
            ineq_str = ineq_str.strip()
            if not ineq_str:
                continue
            for op, np_op in [("<=", "less_equal"), (">=", "greater_equal"), ("<", "less"), (">", "greater")]:
                if op in ineq_str:
                    lhs, rhs = ineq_str.split(op, 1)
                    sl = safe_parse_expr(lhs.strip(), local_dict=_LOCAL_DICT, extra_locals={"x": x_sym, "y": y_sym})
                    sr = safe_parse_expr(rhs.strip(), local_dict=_LOCAL_DICT, extra_locals={"x": x_sym, "y": y_sym})
                    diff = sl - sr
                    vals = _eval_2d(x_sym, y_sym, diff, X, Y)
                    mask &= getattr(np, np_op)(vals, 0)
                    break
            else:
                return _result("Plot error", error=f"无法识别不等式运算符: {ineq_str}")

        fig, ax = plt.subplots(figsize=(7, 7))
        ax.contourf(X, Y, mask.astype(float), levels=[0.5, 1.5], colors=["#4488ff"], alpha=0.4)
        ax.contour(X, Y, mask.astype(float), levels=[0.5], colors=["blue"], linewidths=1)
        ax.set_xlabel("$x$")
        ax.set_ylabel("$y$")
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.set_title(title or "Inequality region")

        path = _save_fig(fig, "region")
        return _result("Inequality region", image_path=path, output="Plotted inequality region")
    except Exception as e:
        return _result("Plot error", error=str(e))


@math_tool(category="plotting", description="Plot 3D surface z=f(x,y)")
def plot_3d(expr: str, x_range: str = "-5,5", y_range: str = "-5,5", title: str = "") -> str:
    """Plot a 3D surface.

    Args:
        expr: z=f(x,y) expression
        x_range: x range, format 'min,max'
        y_range: y range, format 'min,max'
        title: Plot title (use English only)
    """
    try:
        x_sym, y_sym = sp.Symbol("x"), sp.Symbol("y")
        sym_expr = safe_parse_expr(expr, local_dict=_LOCAL_DICT, extra_locals={"x": x_sym, "y": y_sym})

        xr = _parse_range_pair(x_range)
        yr = _parse_range_pair(y_range)
        xv = np.linspace(xr[0], xr[1], 100)
        yv = np.linspace(yr[0], yr[1], 100)
        X, Y = np.meshgrid(xv, yv)
        Z = _eval_2d(x_sym, y_sym, sym_expr, X, Y)

        fig = plt.figure(figsize=(9, 7))
        ax = fig.add_subplot(111, projection="3d")
        ax.plot_surface(X, Y, Z, cmap="viridis", alpha=0.8)
        ax.set_xlabel("$x$")
        ax.set_ylabel("$y$")
        ax.set_zlabel("$z$")
        ax.set_title(title or f"$z = {sp.latex(sym_expr)}$")

        path = _save_fig(fig, "surface3d")
        return _result("3D surface", image_path=path, output="Plotted 3D surface")
    except Exception as e:
        return _result("Plot error", error=str(e))
