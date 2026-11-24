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


@math_tool(
    category="plotting",
    description="Plot 3D Riemann surface of a multi-valued complex function (e.g. sqrt(z), z**(1/3), log(z), sqrt(z**2-1)) using 3D projection + 4th-dimension coloring",
)
def plot_riemann_surface(
    expr: str,
    variable: str = "z",
    sheets: int = 2,
    height_part: str = "auto",
    radius: float = 2.0,
    title: str = "",
) -> str:
    """Plot the 3D Riemann surface of a multi-valued complex function w = f(z).

    Projects (Re(z), Im(z), Re(w) or Im(w)) into 3D space and encodes the 4th
    real coordinate into surface color so apparent self-intersections are resolved.

    Args:
        expr: Complex multi-valued expression, e.g. 'sqrt(z)', 'sqrt(x)', 'z**(1/3)', 'log(z)', 'sqrt(z**2 - 1)'
        variable: Complex independent variable name, e.g. 'z' or 'x'
        sheets: Number of sheets / winding turns to display (e.g. 2 for sqrt, 3 for cbrt or log)
        height_part: Vertical Z-axis component: 'auto' (Re(w), or Im(w) for log), 'real', 'imag', or 'abs'
        radius: Domain radius R > 0 on the complex plane, default 2.0
        title: Plot title (use English only)
    """
    try:
        from matplotlib import cm, colors as mcolors
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        if radius <= 0:
            return _result("Plot error", error="radius must be positive")
        n_sheets = max(1, min(int(sheets), 8))
        var = sp.Symbol(variable)
        sym_expr = safe_parse_expr(expr, local_dict=_LOCAL_DICT, extra_locals={variable: var})

        h_mode = height_part.strip().lower() or "auto"
        if h_mode not in ("auto", "real", "imag", "abs"):
            h_mode = "auto"

        has_log = bool(sym_expr.atoms(sp.log))
        if h_mode == "auto":
            h_mode = "imag" if has_log else "real"

        def _extract_hc(W_arr: np.ndarray) -> tuple[np.ndarray, np.ndarray, str, str]:
            if h_mode == "imag":
                return np.imag(W_arr), np.real(W_arr), f"$\\mathrm{{Im}}({sp.latex(sym_expr)})$", f"$\\mathrm{{Re}}({sp.latex(sym_expr)})$"
            if h_mode == "abs":
                return np.abs(W_arr), np.angle(W_arr), f"$|{sp.latex(sym_expr)}|$", f"$\\arg({sp.latex(sym_expr)})$"
            return np.real(W_arr), np.imag(W_arr), f"$\\mathrm{{Re}}({sp.latex(sym_expr)})$", f"$\\mathrm{{Im}}({sp.latex(sym_expr)})$"

        frac_pows = [
            pw for pw in sym_expr.atoms(sp.Pow)
            if pw.base.has(var) and isinstance(pw.exp, sp.Rational) and pw.exp.q > 1
        ]

        # Check single-branch-point uniformization: all fractional power bases are linear in `var` with a shared root z0
        single_center_z0 = None
        if frac_pows and not has_log:
            roots = []
            all_linear = True
            for pw in frac_pows:
                try:
                    poly_b = sp.Poly(pw.base, var)
                    if poly_b.degree() != 1:
                        all_linear = False
                        break
                    sol = sp.solve(pw.base, var)
                    if len(sol) != 1:
                        all_linear = False
                        break
                    roots.append(sp.simplify(sol[0]))
                except Exception:
                    all_linear = False
                    break
            if all_linear and roots and all(sp.simplify(r - roots[0]) == 0 for r in roots):
                single_center_z0 = roots[0]

        cmap = cm.coolwarm
        fig = plt.figure(figsize=(9.5, 7.5))
        ax = fig.add_subplot(111, projection="3d")

        if has_log:
            log_atom = next(iter(sym_expr.atoms(sp.log)))
            inner = log_atom.args[0]
            sol = sp.solve(inner, var)
            z0 = complex(sol[0].evalf()) if len(sol) == 1 else 0j

            r_min = max(0.05, radius * 0.03)
            rv = np.linspace(r_min, radius, 70)
            tv = np.linspace(-np.pi * n_sheets, np.pi * n_sheets, 140 * n_sheets)
            R_g, T_g = np.meshgrid(rv, tv)
            Z_c = z0 + R_g * np.exp(1j * T_g)

            L_sym = sp.Symbol("_log_branch")
            f_inner = sp.lambdify(var, inner, modules=["numpy"])
            inner_vals = np.asarray(f_inner(Z_c), dtype=complex)
            unwrapped_arg = np.unwrap(np.angle(inner_vals), axis=0)
            L_vals = np.log(np.maximum(np.abs(inner_vals), 1e-12)) + 1j * unwrapped_arg

            f_outer = sp.lambdify((var, L_sym), sym_expr.subs(log_atom, L_sym), modules=["numpy"])
            W = np.broadcast_to(np.asarray(f_outer(Z_c, L_vals), dtype=complex), Z_c.shape)

            X_p, Y_p = np.real(Z_c), np.imag(Z_c)
            H_p, C_p, z_label, c_label = _extract_hc(W)

            c_abs = max(float(np.nanmax(np.abs(C_p))), 1e-6)
            norm = mcolors.Normalize(vmin=-c_abs if np.nanmin(C_p) < 0 else float(np.nanmin(C_p)), vmax=float(np.nanmax(C_p)))
            fc = cmap(norm(C_p))
            ax.plot_surface(
                X_p, Y_p, H_p,
                facecolors=fc, rstride=1, cstride=1,
                alpha=0.9, edgecolor=(0, 0, 0, 0.08), linewidth=0.25, antialiased=True, shade=False,
            )

        elif single_center_z0 is not None:
            q_lcm = math.lcm(*(int(pw.exp.q) for pw in frac_pows))
            has_neg_exp = any(float(pw.exp) < 0 for pw in frac_pows)
            r_start = radius * 0.12 if has_neg_exp else 0.0

            u_sym = sp.Symbol("_u_unif")
            sub_map = {}
            for pw in frac_pows:
                lead = sp.Poly(pw.base, var).LC()
                p_num, q_den = int(pw.exp.p), int(pw.exp.q)
                sub_map[pw] = (lead ** sp.Rational(p_num, q_den)) * (u_sym ** (p_num * (q_lcm // q_den)))

            unif_expr = sym_expr.subs(sub_map).subs(var, single_center_z0 + u_sym ** q_lcm)
            f_unif = sp.lambdify(u_sym, unif_expr, modules=["numpy"])

            rv = np.linspace(r_start, radius, 70)
            phiv = np.linspace(0.0, 2.0 * np.pi, 180)
            R_g, Phi_g = np.meshgrid(rv, phiv)
            U_g = (R_g ** (1.0 / q_lcm)) * np.exp(1j * Phi_g)
            Z_c = complex(single_center_z0.evalf()) + R_g * np.exp(1j * q_lcm * Phi_g)
            W = np.broadcast_to(np.asarray(f_unif(U_g), dtype=complex), Z_c.shape)

            X_p, Y_p = np.real(Z_c), np.imag(Z_c)
            H_p, C_p, z_label, c_label = _extract_hc(W)

            c_abs = max(float(np.nanmax(np.abs(C_p))), 1e-6)
            norm = mcolors.Normalize(vmin=-c_abs, vmax=c_abs)
            fc = cmap(norm(C_p))
            ax.plot_surface(
                X_p, Y_p, H_p,
                facecolors=fc, rstride=1, cstride=1,
                alpha=0.9, edgecolor=(0, 0, 0, 0.08), linewidth=0.25, antialiased=True, shade=False,
            )
            bp = complex(single_center_z0.evalf())
            if not has_neg_exp:
                w_bp = complex(f_unif(0.0))
                h_bp = w_bp.imag if h_mode == "imag" else abs(w_bp) if h_mode == "abs" else w_bp.real
                ax.scatter([bp.real], [bp.imag], [h_bp], color="black", s=38, zorder=10, label="Branch point")

        elif frac_pows:
            # Multi-branch algebraic expression (e.g. sqrt(z**2 - 1)): analytic continuation quad root-matching
            pw_main = max(frac_pows, key=lambda item: int(item.exp.q))
            p_num, q_den = int(pw_main.exp.p), int(pw_main.exp.q)
            w_sym = sp.Symbol("_w_sheet")
            f_base = sp.lambdify(var, pw_main.base, modules=["numpy"])
            f_outer = sp.lambdify((var, w_sym), sym_expr.subs(pw_main, w_sym), modules=["numpy"])

            ng = 58
            xv = np.linspace(-radius, radius, ng)
            yv = np.linspace(-radius, radius, ng)
            X_g, Y_g = np.meshgrid(xv, yv)
            Z_c = X_g + 1j * Y_g
            G_val = np.broadcast_to(np.asarray(f_base(Z_c), dtype=complex), Z_c.shape)
            abs_g = np.abs(G_val) ** (p_num / q_den)
            arg_g = np.angle(G_val)

            W_sheets = np.zeros((q_den, ng, ng), dtype=complex)
            for k in range(q_den):
                wk = abs_g * np.exp(1j * p_num * (arg_g + 2.0 * np.pi * k) / q_den)
                W_sheets[k] = np.broadcast_to(np.asarray(f_outer(Z_c, wk), dtype=complex), Z_c.shape)

            H_all, C_all, z_label, c_label = _extract_hc(W_sheets)
            c_abs = max(float(np.nanmax(np.abs(C_all))), 1e-6)
            norm = mcolors.Normalize(vmin=-c_abs, vmax=c_abs)

            polys = []
            quad_c_vals = []
            for iy in range(ng - 1):
                for ix in range(ng - 1):
                    for k0 in range(q_den):
                        w0 = W_sheets[k0, iy, ix]
                        k1 = int(np.argmin(np.abs(W_sheets[:, iy, ix + 1] - w0)))
                        w1 = W_sheets[k1, iy, ix + 1]
                        k2 = int(np.argmin(np.abs(W_sheets[:, iy + 1, ix + 1] - w1)))
                        w2 = W_sheets[k2, iy + 1, ix + 1]
                        k3 = int(np.argmin(np.abs(W_sheets[:, iy + 1, ix] - w2)))

                        quad = [
                            (X_g[iy, ix], Y_g[iy, ix], H_all[k0, iy, ix]),
                            (X_g[iy, ix + 1], Y_g[iy, ix + 1], H_all[k1, iy, ix + 1]),
                            (X_g[iy + 1, ix + 1], Y_g[iy + 1, ix + 1], H_all[k2, iy + 1, ix + 1]),
                            (X_g[iy + 1, ix], Y_g[iy + 1, ix], H_all[k3, iy + 1, ix]),
                        ]
                        polys.append(quad)
                        quad_c_vals.append(
                            0.25 * (
                                C_all[k0, iy, ix]
                                + C_all[k1, iy, ix + 1]
                                + C_all[k2, iy + 1, ix + 1]
                                + C_all[k3, iy + 1, ix]
                            )
                        )

            face_rgba = cmap(norm(np.asarray(quad_c_vals)))
            face_rgba[:, 3] = 0.86
            coll = Poly3DCollection(polys, facecolors=face_rgba, edgecolors=(0, 0, 0, 0.05), linewidths=0.15)
            ax.add_collection3d(coll)
            ax.set_xlim(-radius, radius)
            ax.set_ylim(-radius, radius)
            ax.set_zlim(float(np.nanmin(H_all)), float(np.nanmax(H_all)))
        else:
            # Single-valued analytic expression fallback in 3D + 4D color
            f_single = sp.lambdify(var, sym_expr, modules=["numpy"])
            rv = np.linspace(0.0, radius, 65)
            tv = np.linspace(0.0, 2.0 * np.pi, 140)
            R_g, T_g = np.meshgrid(rv, tv)
            Z_c = R_g * np.exp(1j * T_g)
            W = np.broadcast_to(np.asarray(f_single(Z_c), dtype=complex), Z_c.shape)
            X_p, Y_p = np.real(Z_c), np.imag(Z_c)
            H_p, C_p, z_label, c_label = _extract_hc(W)
            c_abs = max(float(np.nanmax(np.abs(C_p))), 1e-6)
            norm = mcolors.Normalize(vmin=-c_abs, vmax=c_abs)
            ax.plot_surface(
                X_p, Y_p, H_p,
                facecolors=cmap(norm(C_p)), rstride=1, cstride=1,
                alpha=0.9, edgecolor=(0, 0, 0, 0.08), linewidth=0.25, antialiased=True, shade=False,
            )

        sm = cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.08)
        cbar.set_label(f"4th Dim Color: {c_label}")

        ax.set_xlabel(f"$\\mathrm{{Re}}({variable})$")
        ax.set_ylabel(f"$\\mathrm{{Im}}({variable})$")
        ax.set_zlabel(z_label)
        ax.view_init(elev=26, azim=-55)
        ax.set_title(title or f"Riemann Surface of ${sp.latex(sym_expr)}$")

        path = _save_fig(fig, "riemann_surface")
        return _result(
            title or "Riemann surface",
            image_path=path,
            output=f"Plotted 3D Riemann surface of {expr} (height={h_mode}, 4th-dim colored)",
        )
    except Exception as e:
        return _result("Plot error", error=str(e))
