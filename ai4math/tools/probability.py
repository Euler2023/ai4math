"""Probability theory tools: distributions, expectation, variance, MGF, simplification, etc."""

from __future__ import annotations

import json
import sympy as sp
from sympy import stats as sp_stats
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
for _name in "x y z t a b c n m k p q alpha beta gamma theta lambda mu sigma rho tau".split():
    _LOCAL_DICT[_name] = sp.Symbol(_name, positive=True) if _name in ("n", "k", "alpha", "beta", "lambda", "sigma") else sp.Symbol(_name)
_LOCAL_DICT["pi"] = sp.pi
_LOCAL_DICT["e"] = sp.E
_LOCAL_DICT["oo"] = sp.oo
_LOCAL_DICT["inf"] = sp.oo


def _parse(expr_str: str) -> sp.Expr:
    return parse_expr(expr_str, local_dict=_LOCAL_DICT, transformations=_TRANSFORMATIONS)


def _sym(name: str) -> sp.Symbol:
    if name in _LOCAL_DICT and isinstance(_LOCAL_DICT[name], sp.Symbol):
        return _LOCAL_DICT[name]
    return sp.Symbol(name)


def _result(title: str, **kwargs) -> str:
    out = {"title": title}
    for k, v in kwargs.items():
        out[k] = str(v)
    out["_display_instruction"] = "你必须在回复中用 $$ LaTeX $$ 展示此工具返回的 latex 字段内容，不得省略"
    return json.dumps(out, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Distribution constructors
# ---------------------------------------------------------------------------

def _make_distribution(dist_type: str, params: dict, name: str = "X"):
    """Create a SymPy stats random variable."""
    dist_type = dist_type.lower()

    constructors = {
        # Continuous
        "normal": lambda p: sp_stats.Normal(name, p.get("mu", 0), p.get("sigma", 1)),
        "exponential": lambda p: sp_stats.Exponential(name, p.get("lambda", 1)),
        "uniform": lambda p: sp_stats.Uniform(name, p.get("a", 0), p.get("b", 1)),
        "gamma": lambda p: sp_stats.Gamma(name, p.get("alpha", 1), p.get("beta", 1)),
        "beta": lambda p: sp_stats.Beta(name, p.get("alpha", 1), p.get("beta", 1)),
        "chi_squared": lambda p: sp_stats.ChiSquared(name, p.get("k", 1)),
        "cauchy": lambda p: sp_stats.Cauchy(name, p.get("x0", 0), p.get("gamma", 1)),
        "t": lambda p: sp_stats.StudentT(name, p.get("nu", 1)),
        # Discrete
        "poisson": lambda p: sp_stats.Poisson(name, p.get("lambda", 1)),
        "binomial": lambda p: sp_stats.Binomial(name, p.get("n", 10), p.get("p", 0.5)),
        "geometric": lambda p: sp_stats.Geometric(name, p.get("p", 0.5)),
        "bernoulli": lambda p: sp_stats.Bernoulli(name, p.get("p", 0.5)),
    }

    if dist_type not in constructors:
        raise ValueError(f"未知分布: {dist_type}。支持: {', '.join(constructors.keys())}")

    # Convert string params to sympy if needed
    parsed_params = {}
    for k, v in params.items():
        if isinstance(v, str):
            parsed_params[k] = _parse(v)
        else:
            parsed_params[k] = sp.Rational(v) if isinstance(v, (int, float)) else v

    return constructors[dist_type](parsed_params)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@math_tool(category="probability", description="获取概率分布的基本信息：PDF/PMF、CDF、期望、方差等")
def distribution_info(dist_type: str, params: str = "{}") -> str:
    """获取概率分布的完整信息。

    Args:
        dist_type: 分布类型: normal, exponential, uniform, gamma, beta, chi_squared, cauchy, t, poisson, binomial, geometric, bernoulli
        params: JSON 格式的参数，例如 '{"mu": 0, "sigma": 1}' 或 '{"lambda": 2}'
    """
    import ast
    p = ast.literal_eval(params) if isinstance(params, str) else params
    X = _make_distribution(dist_type, p)
    x = _sym("x")

    info = {"分布": f"{dist_type}({params})"}

    try:
        pdf = sp_stats.density(X)(x)
        info["PDF/PMF"] = sp.pretty(pdf)
        info["PDF_latex"] = sp.latex(pdf)
    except Exception:
        info["PDF/PMF"] = "无法计算"

    try:
        info["期望 E[X]"] = sp.pretty(sp.simplify(sp_stats.E(X)))
    except Exception:
        info["期望 E[X]"] = "无法计算"

    try:
        info["方差 Var[X]"] = sp.pretty(sp.simplify(sp_stats.variance(X)))
    except Exception:
        info["方差 Var[X]"] = "无法计算"

    try:
        info["标准差 σ"] = sp.pretty(sp.simplify(sp.sqrt(sp_stats.variance(X))))
    except Exception:
        pass

    return json.dumps(info, ensure_ascii=False)


@math_tool(category="probability", description="计算随机变量的期望 E[g(X)]")
def compute_expectation(dist_type: str, params: str = "{}", expression: str = "x") -> str:
    """计算期望。

    Args:
        dist_type: 分布类型
        params: JSON 格式的分布参数
        expression: 要计算期望的表达式 g(X)，用 'x' 表示随机变量，例如 'x**2' 计算 E[X²]
    """
    import ast
    p = ast.literal_eval(params) if isinstance(params, str) else params
    X = _make_distribution(dist_type, p)

    # Build the expression in terms of X
    x_sym = _sym("x")
    g = _parse(expression)
    # Substitute x with X
    g_X = g.subs(x_sym, X)

    result = sp.simplify(sp_stats.E(g_X))
    return _result(
        f"期望 E[{expression}]",
        distribution=f"{dist_type}({params})",
        output=sp.pretty(result),
        latex=sp.latex(result),
    )


@math_tool(category="probability", description="计算随机变量的方差 Var[X] 或 Var[g(X)]")
def compute_variance(dist_type: str, params: str = "{}", expression: str = "x") -> str:
    """计算方差。

    Args:
        dist_type: 分布类型
        params: JSON 格式的分布参数
        expression: 表达式，默认 'x' 表示 Var[X]
    """
    import ast
    p = ast.literal_eval(params) if isinstance(params, str) else params
    X = _make_distribution(dist_type, p)

    x_sym = _sym("x")
    g = _parse(expression)
    g_X = g.subs(x_sym, X)

    result = sp.simplify(sp_stats.variance(g_X))
    return _result(
        f"方差 Var[{expression}]",
        distribution=f"{dist_type}({params})",
        output=sp.pretty(result),
        latex=sp.latex(result),
    )


@math_tool(category="probability", description="计算概率 P(condition)，例如 P(X > 2)")
def compute_probability(dist_type: str, params: str = "{}", condition: str = "x > 0") -> str:
    """计算概率。

    Args:
        dist_type: 分布类型
        params: JSON 格式的分布参数
        condition: 条件表达式，例如 'x > 0', 'x <= 2', 'x >= 1'
    """
    import ast
    p = ast.literal_eval(params) if isinstance(params, str) else params
    X = _make_distribution(dist_type, p)
    x_sym = _sym("x")

    # Parse condition
    cond_str = condition.strip()
    for op_str, op_func in [(">=", sp.Ge), ("<=", sp.Le), ("!=", sp.Ne), (">", sp.Gt), ("<", sp.Lt), ("==", sp.Eq)]:
        if op_str in cond_str:
            parts = cond_str.split(op_str)
            lhs = _parse(parts[0].strip()).subs(x_sym, X)
            rhs = _parse(parts[1].strip())
            cond = op_func(lhs, rhs)
            break
    else:
        return _result("错误", error=f"无法解析条件: {condition}")

    result = sp.simplify(sp_stats.P(cond))
    return _result(
        f"概率 P({condition})",
        distribution=f"{dist_type}({params})",
        output=sp.pretty(result),
        latex=sp.latex(result),
    )


@math_tool(category="probability", description="计算矩母函数 (MGF) M_X(t) = E[e^(tX)]")
def moment_generating_function(dist_type: str, params: str = "{}") -> str:
    """计算矩母函数。

    Args:
        dist_type: 分布类型
        params: JSON 格式的分布参数
    """
    import ast
    p = ast.literal_eval(params) if isinstance(params, str) else params
    X = _make_distribution(dist_type, p)
    t = _sym("t")

    try:
        mgf = sp.simplify(sp_stats.E(sp.exp(t * X)))
        return _result(
            "矩母函数 M_X(t)",
            distribution=f"{dist_type}({params})",
            output=sp.pretty(mgf),
            latex=sp.latex(mgf),
        )
    except Exception as e:
        return _result("矩母函数", error=f"无法计算: {e}")


@math_tool(category="probability", description="化简含概率/期望的符号表达式")
def simplify_probability_expression(expr: str) -> str:
    """化简含概率的符号表达式。

    Args:
        expr: 概率表达式，例如 'E(X)**2 - E(X**2) + Var(X)' 这里使用符号化简
    """
    # This works on purely symbolic expressions
    e = _parse(expr)
    simplified = sp.simplify(e)
    expanded = sp.expand(simplified)

    return _result(
        "概率表达式化简",
        input=expr,
        simplified=sp.pretty(simplified),
        expanded=sp.pretty(expanded),
        latex=sp.latex(simplified),
    )


@math_tool(category="probability", description="利用概率公式进行条件概率/贝叶斯定理/全概率公式的符号推导")
def bayes_theorem(prior: str, likelihood: str, evidence: str = "") -> str:
    """贝叶斯定理 / 条件概率计算。

    Args:
        prior: 先验概率 P(A)，数值或表达式，例如 '0.3' 或 'p'
        likelihood: 似然 P(B|A)，数值或表达式，例如 '0.8' 或 'q'
        evidence: P(B) 证据概率（留空则用全概率公式说明），例如 '0.5'
    """
    P_A = _parse(prior)
    P_B_given_A = _parse(likelihood)

    if evidence:
        P_B = _parse(evidence)
        posterior = sp.simplify(P_B_given_A * P_A / P_B)
        return _result(
            "贝叶斯定理 P(A|B) = P(B|A)·P(A)/P(B)",
            P_A=sp.pretty(P_A),
            P_B_given_A=sp.pretty(P_B_given_A),
            P_B=sp.pretty(P_B),
            P_A_given_B=sp.pretty(posterior),
            latex=sp.latex(posterior),
        )
    else:
        P_B = sp.Symbol("P_B")
        posterior = sp.simplify(P_B_given_A * P_A / P_B)
        return _result(
            "贝叶斯定理 P(A|B) = P(B|A)·P(A)/P(B)",
            P_A=sp.pretty(P_A),
            P_B_given_A=sp.pretty(P_B_given_A),
            P_B="需要提供或通过全概率公式计算: P(B) = Σ P(B|A_i)·P(A_i)",
            P_A_given_B=sp.pretty(posterior),
            latex=sp.latex(posterior),
            note="P(B) 未提供，结果中包含 P_B 符号",
        )


@math_tool(category="probability", description="计算随机变量的特征函数 φ_X(t) = E[e^(itX)]")
def characteristic_function(dist_type: str, params: str = "{}") -> str:
    """计算特征函数。

    Args:
        dist_type: 分布类型
        params: JSON 格式的分布参数
    """
    import ast
    p = ast.literal_eval(params) if isinstance(params, str) else params
    X = _make_distribution(dist_type, p)
    t = _sym("t")

    try:
        cf = sp.simplify(sp_stats.E(sp.exp(sp.I * t * X)))
        return _result(
            "特征函数 φ_X(t)",
            distribution=f"{dist_type}({params})",
            output=sp.pretty(cf),
            latex=sp.latex(cf),
        )
    except Exception as e:
        return _result("特征函数", error=f"无法计算: {e}")


@math_tool(category="probability", description="计算协方差 Cov(X,Y) 和相关系数，需要联合分布信息")
def covariance_correlation(expr_xy: str, expr_x: str, expr_y: str, expr_x2: str, expr_y2: str) -> str:
    """根据矩信息计算协方差和相关系数。

    Args:
        expr_xy: E[XY] 的值或表达式
        expr_x: E[X] 的值或表达式
        expr_y: E[Y] 的值或表达式
        expr_x2: E[X²] 的值或表达式
        expr_y2: E[Y²] 的值或表达式
    """
    E_XY = _parse(expr_xy)
    E_X = _parse(expr_x)
    E_Y = _parse(expr_y)
    E_X2 = _parse(expr_x2)
    E_Y2 = _parse(expr_y2)

    cov = sp.simplify(E_XY - E_X * E_Y)
    var_x = sp.simplify(E_X2 - E_X ** 2)
    var_y = sp.simplify(E_Y2 - E_Y ** 2)
    corr = sp.simplify(cov / sp.sqrt(var_x * var_y))

    return _result(
        "协方差与相关系数",
        Cov_XY=sp.pretty(cov),
        Var_X=sp.pretty(var_x),
        Var_Y=sp.pretty(var_y),
        Corr_XY=sp.pretty(corr),
        latex_cov=sp.latex(cov),
        latex_corr=sp.latex(corr),
    )
