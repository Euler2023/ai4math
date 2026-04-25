"""Visualization tools powered by matplotlib."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)

from ai4math.tools.registry import math_tool

_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

_LOCAL_DICT: dict = {}
for _name in "x y z t a b c n m k alpha beta gamma theta phi psi omega".split():
    _LOCAL_DICT[_name] = sp.Symbol(_name)
_LOCAL_DICT["pi"] = sp.pi
_LOCAL_DICT["e"] = sp.E
_LOCAL_DICT["I"] = sp.I

_PLOT_DIR = Path("output/plots")


def _save_fig(fig, name: str) -> str:
    _PLOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = str(_PLOT_DIR / f"{name}_{ts}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _result(title: str, **kwargs) -> str:
    out = {"title": title}
    for k, v in kwargs.items():
        out[k] = str(v)
    return json.dumps(out, ensure_ascii=False)

@math_tool(category="plotting", description="Plot 1D functions. Multiple functions separated by commas, e.g. 'sin(x), cos(x)'")
def plot_function(expr: str, variable: str = "x", x_min: str = "-10", x_max: str = "10", title: str = "") -> str:
    """Plot one or more 1D functions.

    Args:
        expr: Function expression(s), comma-separated. e.g. 'sin(x), cos(x), x**2'
        variable: Variable name, default x
        x_min: x-axis minimum
        x_max: x-axis maximum
        title: Plot title (use English only)
    """
    try:
        var = sp.Symbol(variable)
        exprs = [e.strip() for e in expr.split(",")]
        sym_exprs = [parse_expr(e, local_dict=_LOCAL_DICT, transformations=_TRANSFORMATIONS) for e in exprs]
        funcs = [sp.lambdify(var, se, modules=["numpy"]) for se in sym_exprs]

        xv = np.linspace(float(x_min), float(x_max), 500)
        fig, ax = plt.subplots(figsize=(8, 5))
        for se, f in zip(sym_exprs, funcs):
            yv = np.real_if_close(f(xv).astype(complex))
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
        t_min: Parameter t minimum
        t_max: Parameter t maximum (default 2pi)
        title: Plot title (use English only)
    """
    try:
        t = sp.Symbol("t")
        sx = parse_expr(x_expr, local_dict=_LOCAL_DICT, transformations=_TRANSFORMATIONS)
        sy = parse_expr(y_expr, local_dict=_LOCAL_DICT, transformations=_TRANSFORMATIONS)
        fx = sp.lambdify(t, sx, modules=["numpy"])
        fy = sp.lambdify(t, sy, modules=["numpy"])

        tv = np.linspace(float(t_min), float(t_max), 500)
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.plot(fx(tv), fy(tv))
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
        equation: Left side of equation (right side is 0). e.g. 'x**2 + y**2 - 1' means x^2+y^2=1
        x_range: x range, format 'min,max'
        y_range: y range, format 'min,max'
        title: Plot title (use English only)
    """
    try:
        x, y = sp.Symbol("x"), sp.Symbol("y")
        sym_eq = parse_expr(equation, local_dict=_LOCAL_DICT, transformations=_TRANSFORMATIONS)
        f = sp.lambdify((x, y), sym_eq, modules=["numpy"])

        xr = [float(v) for v in x_range.split(",")]
        yr = [float(v) for v in y_range.split(",")]
        xv = np.linspace(xr[0], xr[1], 400)
        yv = np.linspace(yr[0], yr[1], 400)
        X, Y = np.meshgrid(xv, yv)
        Z = np.real_if_close(f(X, Y).astype(complex))

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
        xr = [float(v) for v in x_range.split(",")]
        yr = [float(v) for v in y_range.split(",")]
        xv = np.linspace(xr[0], xr[1], 500)
        yv = np.linspace(yr[0], yr[1], 500)
        X, Y = np.meshgrid(xv, yv)

        x_sym, y_sym = sp.Symbol("x"), sp.Symbol("y")
        mask = np.ones_like(X, dtype=bool)
        for ineq_str in inequalities.split(";"):
            ineq_str = ineq_str.strip()
            if not ineq_str:
                continue
            for op, np_op in [("<=", "le"), (">=", "ge"), ("<", "lt"), (">", "gt")]:
                if op in ineq_str:
                    lhs, rhs = ineq_str.split(op, 1)
                    sl = parse_expr(lhs.strip(), local_dict=_LOCAL_DICT, transformations=_TRANSFORMATIONS)
                    sr = parse_expr(rhs.strip(), local_dict=_LOCAL_DICT, transformations=_TRANSFORMATIONS)
                    diff = sl - sr
                    f = sp.lambdify((x_sym, y_sym), diff, modules=["numpy"])
                    vals = np.real_if_close(f(X, Y).astype(complex))
                    mask &= getattr(np, np_op)(vals, 0)
                    break

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
        sym_expr = parse_expr(expr, local_dict=_LOCAL_DICT, transformations=_TRANSFORMATIONS)
        f = sp.lambdify((x_sym, y_sym), sym_expr, modules=["numpy"])

        xr = [float(v) for v in x_range.split(",")]
        yr = [float(v) for v in y_range.split(",")]
        xv = np.linspace(xr[0], xr[1], 100)
        yv = np.linspace(yr[0], yr[1], 100)
        X, Y = np.meshgrid(xv, yv)
        Z = np.real_if_close(f(X, Y).astype(complex))

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
