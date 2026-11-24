"""Probability theory tools: distributions, expectation, variance, MGF, simplification, etc."""

from __future__ import annotations

import ast
import json
import re
import sympy as sp
from sympy import stats as sp_stats

from ai4math.tools._shared import (
    format_result,
    get_or_make_symbol,
    make_local_dict,
    safe_literal_eval,
    safe_parse_expr,
)
from ai4math.tools.registry import math_tool

_POSITIVE_PROB_SYMBOLS = frozenset({"n", "k", "alpha", "beta", "lambda", "sigma"})
_LOCAL_DICT = make_local_dict(_POSITIVE_PROB_SYMBOLS)


def _parse(expr_str: str, extra_locals: dict | None = None) -> sp.Expr:
    return safe_parse_expr(expr_str, local_dict=_LOCAL_DICT, extra_locals=extra_locals)


def _sym(name: str) -> sp.Symbol:
    return get_or_make_symbol(name, _LOCAL_DICT)


def _result(title: str, **kwargs) -> str:
    return format_result(title, **kwargs)


def _parse_params(params: str | dict) -> dict:
    if isinstance(params, dict):
        return params
    if not params or not params.strip():
        return {}
    res = safe_literal_eval(params)
    if not isinstance(res, dict):
        raise ValueError("params 必须是 JSON 对象或字典格式")
    return res


# ---------------------------------------------------------------------------
# Distribution constructors
# ---------------------------------------------------------------------------

def _make_distribution(dist_type: str, params: dict, name: str = "X"):
    """Create a SymPy stats random variable with exact decimal-to-Rational conversion."""
    dist_type = dist_type.lower().strip()

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
        "binomial": lambda p: sp_stats.Binomial(name, p.get("n", 10), p.get("p", sp.Rational(1, 2))),
        "geometric": lambda p: sp_stats.Geometric(name, p.get("p", sp.Rational(1, 2))),
        "bernoulli": lambda p: sp_stats.Bernoulli(name, p.get("p", sp.Rational(1, 2))),
    }

    if dist_type not in constructors:
        raise ValueError(f"未知分布: {dist_type}。支持: {', '.join(constructors.keys())}")

    parsed_params = {}
    for k, v in params.items():
        if isinstance(v, str):
            # Convert exact decimal strings like "0.3" to Rational("0.3") = 3/10
            if re.fullmatch(r"[+-]?\d+\.\d+", v.strip()):
                parsed_params[k] = sp.Rational(v.strip())
            else:
                parsed_params[k] = _parse(v)
        elif isinstance(v, bool):
            parsed_params[k] = int(v)
        elif isinstance(v, (int, float)):
            # str(v) avoids IEEE-754 binary mantissa expansion such as Rational(0.3) -> 5404319552844595/2^54
            parsed_params[k] = sp.Rational(str(v))
        else:
            parsed_params[k] = v

    return constructors[dist_type](parsed_params)


def _normalize_single_comparison(lhs: sp.Expr, op_node: ast.cmpop, rhs: sp.Expr):
    """Build a SymPy relational, rewriting |f(X)| op c into compound inequalities SymPy stats can reduce."""
    # Canonicalize c op Abs(...) into Abs(...) rev_op c
    if isinstance(rhs, sp.Abs) and not isinstance(lhs, sp.Abs):
        rev_map = {
            ast.Lt: ast.Gt,
            ast.LtE: ast.GtE,
            ast.Gt: ast.Lt,
            ast.GtE: ast.LtE,
            ast.Eq: ast.Eq,
            ast.NotEq: ast.NotEq,
        }
        op_type = rev_map.get(type(op_node))
        if op_type is not None:
            lhs, rhs = rhs, lhs
            op_node = op_type()

    if isinstance(lhs, sp.Abs) and not rhs.free_symbols.intersection(lhs.free_symbols):
        inner = lhs.args[0]
        if isinstance(op_node, ast.Gt):
            return sp.true if rhs.is_negative else sp.Or(inner > rhs, inner < -rhs)
        if isinstance(op_node, ast.GtE):
            return sp.true if (rhs.is_negative or rhs.is_zero) else sp.Or(inner >= rhs, inner <= -rhs)
        if isinstance(op_node, ast.Lt):
            return sp.false if (rhs.is_negative or rhs.is_zero) else sp.And(inner > -rhs, inner < rhs)
        if isinstance(op_node, ast.LtE):
            return sp.false if rhs.is_negative else sp.And(inner >= -rhs, inner <= rhs)

    op_funcs = {
        ast.Gt: sp.Gt,
        ast.GtE: sp.Ge,
        ast.Lt: sp.Lt,
        ast.LtE: sp.Le,
        ast.Eq: sp.Eq,
        ast.NotEq: sp.Ne,
    }
    for cls, fn in op_funcs.items():
        if isinstance(op_node, cls):
            return fn(lhs, rhs)
    raise ValueError(f"不支持的比较运算符: {type(op_node).__name__}")


def _parse_prob_condition(cond_str: str, x_sym: sp.Symbol, X) -> Any:
    """Parse single, chained ('0.5 < x < 0.8'), boolean ('and'/'or'), and '|x| > c' conditions."""
    # Normalize |...| notation to abs(...) when paired
    cleaned = re.sub(r"\|([^|]+)\|", r"abs(\1)", cond_str.strip())

    def _parse_scalar_or_rv(expr_code: str) -> sp.Expr:
        # Convert float literals in condition to exact Rationals for clean exact integration
        expr_exact = re.sub(
            r"(?<![A-Za-z0-9_.])(\d+\.\d+)(?![A-Za-z0-9_.])",
            r"Rational('\1')",
            expr_code,
        )
        parsed = _parse(expr_exact, extra_locals={"X": x_sym})
        return parsed.subs(x_sym, X)

    tree = ast.parse(cleaned, "<prob_cond>", mode="eval")

    def _convert(node: ast.AST):
        if isinstance(node, ast.BoolOp):
            converted = [_convert(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return sp.And(*converted)
            if isinstance(node.op, ast.Or):
                return sp.Or(*converted)
            raise ValueError(f"不支持的逻辑运算: {type(node.op).__name__}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return sp.Not(_convert(node.operand))
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitAnd, ast.BitOr)):
            left = _convert(node.left)
            right = _convert(node.right)
            return sp.And(left, right) if isinstance(node.op, ast.BitAnd) else sp.Or(left, right)
        if isinstance(node, ast.Compare):
            pieces = []
            cur_left = _parse_scalar_or_rv(ast.unparse(node.left))
            for op_node, comp_ast in zip(node.ops, node.comparators):
                cur_right = _parse_scalar_or_rv(ast.unparse(comp_ast))
                pieces.append(_normalize_single_comparison(cur_left, op_node, cur_right))
                cur_left = cur_right
            return pieces[0] if len(pieces) == 1 else sp.And(*pieces)
        raise ValueError(f"无法解析概率条件: {cond_str}")

    return _convert(tree.body)


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
    p = _parse_params(params)
    X = _make_distribution(dist_type, p)
    x = _sym("x")

    info: dict[str, str] = {"title": "概率分布信息", "分布": f"{dist_type}({params})"}

    try:
        pdf = sp_stats.density(X)(x)
        info["PDF/PMF"] = sp.pretty(pdf)
        info["PDF_latex"] = sp.latex(pdf)
        info["latex"] = sp.latex(pdf)
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
    p = _parse_params(params)
    X = _make_distribution(dist_type, p)

    x_sym = _sym("x")
    g = _parse(expression, extra_locals={"X": x_sym})
    g_X = g.subs(x_sym, X)

    raw_exp = sp_stats.E(g_X)
    if hasattr(raw_exp, "doit"):
        raw_exp = raw_exp.doit()
    result = sp.simplify(raw_exp)
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
    p = _parse_params(params)
    X = _make_distribution(dist_type, p)

    x_sym = _sym("x")
    g = _parse(expression, extra_locals={"X": x_sym})
    g_X = g.subs(x_sym, X)

    raw_var = sp_stats.variance(g_X)
    if hasattr(raw_var, "doit"):
        raw_var = raw_var.doit()
    result = sp.simplify(raw_var)
    return _result(
        f"方差 Var[{expression}]",
        distribution=f"{dist_type}({params})",
        output=sp.pretty(result),
        latex=sp.latex(result),
    )


@math_tool(category="probability", description="计算概率 P(condition)，支持单侧、双侧区间、绝对值与逻辑组合，例如 P(0.5 < x < 0.8) 或 P(abs(x) > 2)")
def compute_probability(dist_type: str, params: str = "{}", condition: str = "x > 0") -> str:
    """计算概率。

    Args:
        dist_type: 分布类型
        params: JSON 格式的分布参数
        condition: 条件表达式，例如 'x > 0', '0.5 < x < 0.8', 'abs(x) > 2', 'x > 0.2 and x < 0.8'
    """
    p = _parse_params(params)
    X = _make_distribution(dist_type, p)
    x_sym = _sym("x")

    try:
        cond = _parse_prob_condition(condition, x_sym, X)
    except Exception as e:
        return _result("错误", error=f"无法解析条件 {condition!r}: {e}")

    raw_prob = sp_stats.P(cond)
    if hasattr(raw_prob, "doit"):
        raw_prob = raw_prob.doit()
    result = sp.simplify(raw_prob)
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
    p = _parse_params(params)
    X = _make_distribution(dist_type, p)
    t = sp.Symbol("t", real=True)

    try:
        try:
            raw_mgf = sp_stats.moment_generating_function(X)(t)
        except Exception:
            raw_mgf = sp_stats.E(sp.exp(t * X))
        if hasattr(raw_mgf, "rewrite"):
            raw_mgf = raw_mgf.rewrite(sp.factorial)
        if hasattr(raw_mgf, "doit"):
            raw_mgf = raw_mgf.doit(deep=True)
        mgf = sp.simplify(raw_mgf)
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

    if evidence.strip():
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
    p = _parse_params(params)
    X = _make_distribution(dist_type, p)
    t = sp.Symbol("t", real=True)

    try:
        try:
            raw_cf = sp_stats.characteristic_function(X)(t)
        except Exception:
            raw_cf = sp_stats.E(sp.exp(sp.I * t * X))
        if hasattr(raw_cf, "rewrite"):
            raw_cf = raw_cf.rewrite(sp.factorial)
        if hasattr(raw_cf, "doit"):
            raw_cf = raw_cf.doit(deep=True)
        cf = sp.simplify(raw_cf)
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
        latex=f"\\operatorname{{Cov}}(X,Y) = {sp.latex(cov)},\\quad \\rho_{{X,Y}} = {sp.latex(corr)}",
    )
