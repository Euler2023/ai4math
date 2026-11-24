"""Visualization tools powered by SageMath."""

from __future__ import annotations

from pathlib import Path

from ai4math.tools._shared import (
    format_result,
    parse_float_expr,
    split_top_level,
    unique_plot_path,
)
from ai4math.tools.registry import math_tool

_PLOT_DIR = Path("output/plots")


def _sage():
    """Lazy import sage.all to avoid slow startup when not needed."""
    import sage.all as sa
    return sa


def _save_sage(plot_obj, name: str, title: str = "") -> str:
    path = unique_plot_path(_PLOT_DIR, name)
    save_kwargs = {"dpi": 150}
    if title:
        save_kwargs["title"] = title
    try:
        plot_obj.save(path, **save_kwargs)
    except TypeError:
        # 3D Tachyon/Jmol plots may not accept title/dpi kwargs directly
        try:
            plot_obj.save(path, dpi=150)
        except TypeError:
            plot_obj.save(path)
    return path


def _result(title: str, **kwargs) -> str:
    return format_result(title, include_display_instruction=False, **kwargs)


def _parse_range(s: str) -> tuple[float, float]:
    parts = split_top_level(s, ",")
    if len(parts) != 2:
        raise ValueError(f"区间格式应为 'min,max'，收到: {s!r}")
    return (parse_float_expr(parts[0]), parse_float_expr(parts[1]))


@math_tool(category="sage_plotting", description="SageMath function plot, multiple functions comma-separated")
def sage_plot(expr: str, x_min: str = "-10", x_max: str = "10", title: str = "") -> str:
    """Plot functions using SageMath.

    Args:
        expr: Function expression(s), comma-separated. e.g. 'sin(x), cos(x)'
        x_min: x-axis minimum (supports constants like '-2*pi')
        x_max: x-axis maximum (supports constants like '2*pi')
        title: Plot title (use English only)
    """
    try:
        sa = _sage()
        x = sa.var("x")
        exprs = split_top_level(expr, ",")
        colors = ["blue", "red", "green", "orange", "purple", "brown", "magenta", "cyan"]
        xmin_f = parse_float_expr(x_min)
        xmax_f = parse_float_expr(x_max)
        p = None
        for i, e in enumerate(exprs):
            se = sa.sage_eval(e, locals={"x": x})
            pi = sa.plot(
                se,
                (x, xmin_f, xmax_f),
                color=colors[i % len(colors)],
                legend_label=str(se),
            )
            p = pi if p is None else p + pi
        p.axes_labels(["$x$", "$y$"])
        path = _save_sage(p, "sage_func", title=title)
        return _result("SageMath function plot", image_path=path, title=title or "SageMath function plot", output=f"Plotted {len(exprs)} function(s)")
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
        path = _save_sage(p, "sage_implicit", title=title)
        return _result("SageMath implicit curve", image_path=path, title=title or "SageMath implicit curve", output="Plotted implicit curve")
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
        p = sa.region_plot(
            conds,
            (x, xr[0], xr[1]),
            (y, yr[0], yr[1]),
            incol="#4488ff",
            bordercol="blue",
            alpha=0.4,
        )
        path = _save_sage(p, "sage_region", title=title)
        return _result("SageMath region plot", image_path=path, title=title or "SageMath region plot", output="Plotted inequality region")
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
        path = _save_sage(p, "sage_3d", title=title)
        return _result("SageMath 3D surface", image_path=path, title=title or "SageMath 3D surface", output="Plotted 3D surface")
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
        path = _save_sage(p, "sage_complex", title=title)
        return _result("SageMath complex plot", image_path=path, title=title or "SageMath complex plot", output="Plotted complex function phase portrait")
    except Exception as e:
        return _result("Plot error", error=str(e))
