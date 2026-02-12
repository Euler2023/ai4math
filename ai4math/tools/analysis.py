"""Mathematical analysis tools: calculus, limits, series, ODEs, etc."""

from __future__ import annotations

import json
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)

from ai4math.tools.registry import math_tool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

# Common symbol names pre-defined for convenience
_LOCAL_DICT: dict = {}
for _name in "x y z t a b c n m k alpha beta gamma theta phi psi omega lambda mu sigma rho tau epsilon delta".split():
    _LOCAL_DICT[_name] = sp.Symbol(_name)
# Also add common constants
_LOCAL_DICT["pi"] = sp.pi
_LOCAL_DICT["e"] = sp.E
_LOCAL_DICT["I"] = sp.I
_LOCAL_DICT["oo"] = sp.oo
_LOCAL_DICT["inf"] = sp.oo


def _parse(expr_str: str) -> sp.Expr:
    """Parse a string expression into a SymPy expression."""
    return parse_expr(expr_str, local_dict=_LOCAL_DICT, transformations=_TRANSFORMATIONS)


def _sym(name: str) -> sp.Symbol:
    """Get or create a SymPy symbol."""
    if name in _LOCAL_DICT and isinstance(_LOCAL_DICT[name], sp.Symbol):
        return _LOCAL_DICT[name]
    return sp.Symbol(name)


def _result(title: str, **kwargs) -> str:
    """Format a result dict as a JSON string."""
    out = {"title": title}
    for k, v in kwargs.items():
        out[k] = str(v)
    out["_display_instruction"] = "你必须在回复中用 $$ LaTeX $$ 展示此工具返回的 latex 字段内容，不得省略"
    return json.dumps(out, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@math_tool(category="analysis", description="化简数学表达式，返回最简形式")
def simplify_expression(expr: str) -> str:
    """化简数学表达式。

    Args:
        expr: 要化简的数学表达式，例如 'sin(x)**2 + cos(x)**2'
    """
    e = _parse(expr)
    simplified = sp.simplify(e)
    return _result("化简结果", input=expr, output=sp.pretty(simplified), latex=sp.latex(simplified))


@math_tool(category="analysis", description="展开数学表达式")
def expand_expression(expr: str) -> str:
    """展开数学表达式（多项式展开、三角函数展开等）。

    Args:
        expr: 要展开的数学表达式，例如 '(x+1)**3'
    """
    e = _parse(expr)
    expanded = sp.expand(e)
    return _result("展开结果", input=expr, output=sp.pretty(expanded), latex=sp.latex(expanded))


@math_tool(category="analysis", description="因式分解数学表达式")
def factor_expression(expr: str) -> str:
    """因式分解数学表达式。

    Args:
        expr: 要因式分解的表达式，例如 'x**2 - 1'
    """
    e = _parse(expr)
    factored = sp.factor(e)
    return _result("因式分解结果", input=expr, output=sp.pretty(factored), latex=sp.latex(factored))


@math_tool(category="analysis", description="计算函数的导数（支持高阶导数和偏导数）")
def differentiate(expr: str, variable: str = "x", order: int = 1) -> str:
    """计算导数。

    Args:
        expr: 要求导的表达式，例如 'x**3 * sin(x)'
        variable: 求导变量，默认为 'x'
        order: 求导阶数，默认为 1
    """
    e = _parse(expr)
    var = _sym(variable)
    result = sp.diff(e, var, order)
    simplified = sp.simplify(result)
    return _result(
        f"{'偏' if len(e.free_symbols) > 1 else ''}导数 (对 {variable}, {order} 阶)",
        input=expr,
        output=sp.pretty(simplified),
        latex=sp.latex(simplified),
    )


@math_tool(category="analysis", description="计算不定积分或定积分")
def integrate(expr: str, variable: str = "x", lower: str = "", upper: str = "") -> str:
    """计算积分。

    Args:
        expr: 被积函数，例如 'x**2 * exp(-x)'
        variable: 积分变量，默认为 'x'
        lower: 定积分下限（留空表示不定积分），例如 '0'
        upper: 定积分上限（留空表示不定积分），例如 'oo'
    """
    e = _parse(expr)
    var = _sym(variable)

    if lower and upper:
        lo = _parse(lower)
        hi = _parse(upper)
        result = sp.integrate(e, (var, lo, hi))
        title = f"定积分 ∫[{lower},{upper}]"
    else:
        result = sp.integrate(e, var)
        title = "不定积分"

    simplified = sp.simplify(result)
    return _result(title, input=expr, variable=variable, output=sp.pretty(simplified), latex=sp.latex(simplified))


@math_tool(category="analysis", description="计算函数的极限")
def compute_limit(expr: str, variable: str = "x", point: str = "0", direction: str = "") -> str:
    """计算极限。

    Args:
        expr: 表达式，例如 'sin(x)/x'
        variable: 趋近的变量，默认为 'x'
        point: 趋近的点，例如 '0', 'oo', '-oo'
        direction: 趋近方向，'+' 右极限, '-' 左极限, '' 双侧（默认）
    """
    e = _parse(expr)
    var = _sym(variable)
    pt = _parse(point)

    kwargs = {}
    if direction in ("+", "-"):
        kwargs["dir"] = direction

    result = sp.limit(e, var, pt, **kwargs)
    dir_str = {"": "", "+": "⁺", "-": "⁻"}.get(direction, "")
    return _result(
        f"极限 ({variable}→{point}{dir_str})",
        input=expr,
        output=sp.pretty(result),
        latex=sp.latex(result),
    )


@math_tool(category="analysis", description="计算泰勒/麦克劳林级数展开")
def series_expansion(expr: str, variable: str = "x", point: str = "0", order: int = 6) -> str:
    """计算泰勒级数展开。

    Args:
        expr: 要展开的表达式，例如 'exp(x)'
        variable: 展开变量，默认为 'x'
        point: 展开点，默认为 '0'（麦克劳林级数）
        order: 展开阶数，默认为 6
    """
    e = _parse(expr)
    var = _sym(variable)
    pt = _parse(point)
    result = sp.series(e, var, pt, n=order)
    return _result(
        f"级数展开 (在 {variable}={point} 处, {order} 阶)",
        input=expr,
        output=sp.pretty(result),
        latex=sp.latex(result),
    )


@math_tool(category="analysis", description="求解方程或方程组")
def solve_equation(equations: str, variables: str = "") -> str:
    """求解方程。

    Args:
        equations: 方程（用逗号分隔多个方程），例如 'x**2 - 3*x + 2' 或 'x + y - 1, x - y - 3'
        variables: 求解的变量（逗号分隔），例如 'x' 或 'x,y'，留空自动检测
    """
    eq_strs = [s.strip() for s in equations.split(",")]
    eqs = []
    for eq_str in eq_strs:
        if "=" in eq_str:
            lhs, rhs = eq_str.split("=", 1)
            eqs.append(sp.Eq(_parse(lhs.strip()), _parse(rhs.strip())))
        else:
            eqs.append(_parse(eq_str))

    if variables:
        vars_ = [_sym(v.strip()) for v in variables.split(",")]
    else:
        vars_ = list(set().union(*(eq.free_symbols if hasattr(eq, 'free_symbols') else set() for eq in eqs)))
        vars_.sort(key=str)

    result = sp.solve(eqs if len(eqs) > 1 else eqs[0], vars_ if len(vars_) > 1 else vars_[0])

    if isinstance(result, list):
        solutions = [str(r) for r in result]
    elif isinstance(result, dict):
        solutions = {str(k): str(v) for k, v in result.items()}
    else:
        solutions = str(result)

    return _result("方程求解", equations=equations, solutions=json.dumps(solutions, ensure_ascii=False, default=str))


@math_tool(category="analysis", description="求解常微分方程 (ODE)")
def solve_ode(ode: str, func: str = "f(x)", variable: str = "x") -> str:
    """求解常微分方程。

    Args:
        ode: ODE 表达式，使用 f(x) 表示未知函数，f(x).diff(x) 表示导数。例如 "f(x).diff(x, 2) + f(x)"
        func: 未知函数，默认为 'f(x)'
        variable: 自变量，默认为 'x'
    """
    var = _sym(variable)
    # Create the function
    func_name = func.split("(")[0].strip()
    F = sp.Function(func_name)
    local = {**_LOCAL_DICT, func_name: F, variable: var}

    ode_expr = parse_expr(ode, local_dict=local, transformations=_TRANSFORMATIONS)
    f_var = F(var)
    result = sp.dsolve(ode_expr, f_var)
    return _result(
        "ODE 求解",
        ode=ode,
        output=sp.pretty(result),
        latex=sp.latex(result),
    )


@math_tool(category="analysis", description="计算求和（有限或无穷级数求和）")
def compute_sum(expr: str, variable: str = "n", lower: str = "0", upper: str = "oo") -> str:
    """计算级数求和。

    Args:
        expr: 通项表达式，例如 '1/n**2'
        variable: 求和变量，默认为 'n'
        lower: 下界，默认为 '0'
        upper: 上界，默认为 'oo'（无穷）
    """
    e = _parse(expr)
    var = _sym(variable)
    lo = _parse(lower)
    hi = _parse(upper)
    result = sp.summation(e, (var, lo, hi))
    simplified = sp.simplify(result)
    return _result(
        f"求和 Σ[{variable}={lower}..{upper}]",
        input=expr,
        output=sp.pretty(simplified),
        latex=sp.latex(simplified),
    )


@math_tool(category="analysis", description="计算矩阵运算（行列式、逆、特征值等）")
def matrix_operation(matrix: str, operation: str = "det") -> str:
    """对矩阵执行运算。

    Args:
        matrix: 矩阵，用嵌套列表表示，例如 '[[1,2],[3,4]]'
        operation: 运算类型: det(行列式), inv(逆), eigenvals(特征值), eigenvects(特征向量), rank(秩), rref(行最简形式)
    """
    import ast
    data = ast.literal_eval(matrix)
    M = sp.Matrix(data)

    ops = {
        "det": lambda: M.det(),
        "inv": lambda: M.inv(),
        "eigenvals": lambda: M.eigenvals(),
        "eigenvects": lambda: M.eigenvects(),
        "rank": lambda: M.rank(),
        "rref": lambda: M.rref(),
        "transpose": lambda: M.T,
    }

    if operation not in ops:
        return _result("错误", error=f"未知运算: {operation}，支持: {', '.join(ops.keys())}")

    result = ops[operation]()
    return _result(
        f"矩阵{operation}运算",
        matrix=matrix,
        operation=operation,
        output=sp.pretty(result) if hasattr(result, '__class__') else str(result),
        latex=sp.latex(result) if hasattr(result, 'atoms') else str(result),
    )


@math_tool(category="analysis", description="对表达式进行三角函数化简")
def trig_simplify(expr: str) -> str:
    """三角函数化简。

    Args:
        expr: 含三角函数的表达式，例如 'sin(x)**2 + cos(x)**2'
    """
    e = _parse(expr)
    result = sp.trigsimp(e)
    return _result("三角函数化简", input=expr, output=sp.pretty(result), latex=sp.latex(result))


@math_tool(category="analysis", description="逐步推导表达式化简过程")
def step_by_step_simplify(expr: str) -> str:
    """逐步展示表达式化简过程，返回多个中间步骤。

    Args:
        expr: 要化简的表达式
    """
    e = _parse(expr)
    steps = []
    steps.append(("原始表达式", e))

    # Step 1: Expand
    expanded = sp.expand(e)
    if expanded != e:
        steps.append(("展开", expanded))

    # Step 2: Trig simplify
    trig = sp.trigsimp(expanded)
    if trig != expanded:
        steps.append(("三角化简", trig))

    # Step 3: Factor
    current = steps[-1][1]
    factored = sp.factor(current)
    if factored != current:
        steps.append(("因式分解", factored))

    # Step 4: General simplify
    current = steps[-1][1]
    simplified = sp.simplify(current)
    if simplified != current:
        steps.append(("化简", simplified))

    # Step 5: Cancel
    current = steps[-1][1]
    cancelled = sp.cancel(current)
    if cancelled != current:
        steps.append(("约分", cancelled))

    result = {}
    for i, (step_name, step_expr) in enumerate(steps):
        result[f"step_{i}"] = f"[{step_name}] {sp.pretty(step_expr)}"
    result["latex_final"] = sp.latex(steps[-1][1])

    return json.dumps(result, ensure_ascii=False)
