"""Visualization tools powered by SageMath."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ai4math.tools.registry import math_tool

_PLOT_DIR = Path("output/plots")


def _sage():
    """Lazy import sage.all to avoid slow startup when not needed."""
    import sage.all as sa
    return sa


def _save_sage(plot_obj, name: str) -> str:
    _PLOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = str(_PLOT_DIR / f"{name}_{ts}.png")
    plot_obj.save(path, dpi=150)
    return path


def _result(title: str, **kwargs) -> str:
    out = {"title": title}
    for k, v in kwargs.items():
        out[k] = str(v)
    return json.dumps(out, ensure_ascii=False)


def _parse_range(s: str) -> tuple:
    parts = [float(v) for v in s.split(",")]
    return (parts[0], parts[1])

@math_tool(category="sage_plotting", description="SageMath function plot, multiple functions comma-separated")
def sage_plot(expr: str, x_min: str = "-10", x_max: str = "10", title: str = "") -> str:
    """Plot functions using SageMath.

    Args:
        expr: Function expression(s), comma-separated. e.g. 'sin(x), cos(x)'
        x_min: x-axis minimum
        x_max: x-axis maximum
        title: Plot title (use English only)
    """
    try:
        sa = _sage()
        x = sa.var("x")
        exprs = [e.strip() for e in expr.split(",")]
        colors = ["blue", "red", "green", "orange", "purple", "brown", "magenta", "cyan"]
        p = None
        for i, e in enumerate(exprs):
            se = sa.sage_eval(e, locals={"x": x})
            pi = sa.plot(se, (x, float(x_min), float(x_max)),
                         color=colors[i % len(colors)], legend_label=str(se))
            p = pi if p is None else p + pi
        if title:
            p.axes_labels(["$x$", "$y$"])
        path = _save_sage(p, "sage_func")
        return _result("SageMath function plot", image_path=path, output=f"Plotted {len(exprs)} function(s)")
    except Exception as e:
        return _result("Plot error", error=str(e))


@math_tool(category="sage_plotting", description="SageMath implicit curve plot, e.g. x^2+y^2==1")
def sage_implicit_plot(equation: str, x_range: str = "-5,5", y_range: str = "-5,5", title: str = "") -> str:
    """Plot implicit curve using SageMath.

    Args:
        equation: Implicit equation using ==. e.g. 'x^2+y^2==1'. Also supports inequalities like 'x^2+y^2<1'
        x_range: x range, format 'min,max'
        y_range: y range, format 'min,max'
        title: Plot title (use English only)
    """
    try:
        sa = _sage()
        x, y = sa.var("x y")
        eq = sa.sage_eval(equation, locals={"x": x, "y": y})
        xr = _parse_range(x_range)
        yr = _parse_range(y_range)
        p = sa.implicit_plot(eq, (x, xr[0], xr[1]), (y, yr[0], yr[1]))
        path = _save_sage(p, "sage_implicit")
        return _result("SageMath implicit curve", image_path=path, output="Plotted implicit curve")
    except Exception as e:
        return _result("Plot error", error=str(e))


@math_tool(category="sage_plotting", description="SageMath inequality region plot, multiple conditions (intersection)")
def sage_region_plot(inequalities: str, x_range: str = "-5,5", y_range: str = "-5,5", title: str = "") -> str:
    """Plot inequality region using SageMath.

    Args:
        inequalities: Semicolon-separated inequalities. e.g. 'x^2+y^2<1; x>0'
        x_range: x range, format 'min,max'
        y_range: y range, format 'min,max'
        title: Plot title (use English only)
    """
    try:
        sa = _sage()
        x, y = sa.var("x y")
        conds = []
        for ineq_str in inequalities.split(";"):
            ineq_str = ineq_str.strip()
            if ineq_str:
                conds.append(sa.sage_eval(ineq_str, locals={"x": x, "y": y}))
        xr = _parse_range(x_range)
        yr = _parse_range(y_range)
        p = sa.region_plot(conds, (x, xr[0], xr[1]), (y, yr[0], yr[1]),
                           incol="#4488ff", bordercol="blue", alpha=0.4)
        path = _save_sage(p, "sage_region")
        return _result("SageMath region plot", image_path=path, output="Plotted inequality region")
    except Exception as e:
        return _result("Plot error", error=str(e))


@math_tool(category="sage_plotting", description="SageMath 3D surface plot z=f(x,y)")
def sage_plot_3d(expr: str, x_range: str = "-5,5", y_range: str = "-5,5", title: str = "") -> str:
    """Plot 3D surface using SageMath.

    Args:
        expr: z=f(x,y) expression
        x_range: x range, format 'min,max'
        y_range: y range, format 'min,max'
        title: Plot title (use English only)
    """
    try:
        sa = _sage()
        x, y = sa.var("x y")
        se = sa.sage_eval(expr, locals={"x": x, "y": y})
        xr = _parse_range(x_range)
        yr = _parse_range(y_range)
        p = sa.plot3d(se, (x, xr[0], xr[1]), (y, yr[0], yr[1]))
        path = _save_sage(p, "sage_3d")
        return _result("SageMath 3D surface", image_path=path, output="Plotted 3D surface")
    except Exception as e:
        return _result("Plot error", error=str(e))


@math_tool(category="sage_plotting", description="SageMath complex function phase plot (complex_plot)")
def sage_complex_plot(expr: str, x_range: str = "-5,5", y_range: str = "-5,5", title: str = "") -> str:
    """Plot complex function phase portrait using SageMath.

    Args:
        expr: Complex function expression with variable z. e.g. '(z^2-1)/(z^2+1)'
        x_range: Real part range, format 'min,max'
        y_range: Imaginary part range, format 'min,max'
        title: Plot title (use English only)
    """
    try:
        sa = _sage()
        z = sa.var("z")
        se = sa.sage_eval(expr, locals={"z": z})
        xr = _parse_range(x_range)
        yr = _parse_range(y_range)
        p = sa.complex_plot(se, (xr[0], xr[1]), (yr[0], yr[1]))
        path = _save_sage(p, "sage_complex")
        return _result("SageMath complex plot", image_path=path, output="Plotted complex function phase portrait")
    except Exception as e:
        return _result("Plot error", error=str(e))
