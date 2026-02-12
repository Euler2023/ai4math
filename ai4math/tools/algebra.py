"""Abstract algebra tools: groups, rings, fields, polynomials, permutations, etc."""

from __future__ import annotations

import json
import sympy as sp
from sympy.combinatorics import Permutation, PermutationGroup
from sympy.combinatorics.named_groups import (
    SymmetricGroup,
    CyclicGroup,
    DihedralGroup,
    AlternatingGroup,
)
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
for _name in "x y z t a b c n m k alpha beta".split():
    _LOCAL_DICT[_name] = sp.Symbol(_name)


def _parse(expr_str: str) -> sp.Expr:
    return parse_expr(expr_str, local_dict=_LOCAL_DICT, transformations=_TRANSFORMATIONS)


def _result(title: str, **kwargs) -> str:
    out = {"title": title}
    for k, v in kwargs.items():
        out[k] = str(v)
    out["_display_instruction"] = "你必须在回复中用 $$ LaTeX $$ 展示此工具返回的 latex 字段内容，不得省略"
    return json.dumps(out, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Polynomial Ring Tools
# ---------------------------------------------------------------------------

@math_tool(category="algebra", description="多项式环上的运算：GCD、LCM、因式分解、除法等")
def polynomial_operation(expr: str, operation: str = "factor", variable: str = "x", modulus: int = 0) -> str:
    """多项式环运算。

    Args:
        expr: 多项式表达式，多个多项式用分号分隔。例如 'x**4 - 1' 或 'x**3 + 1; x**2 - 1'
        operation: 运算类型: factor(因式分解), gcd(最大公因式), lcm(最小公倍式), div(带余除法), roots(求根)
        variable: 主变量，默认 'x'
        modulus: 模数（0 表示在 Q[x] 上，素数 p 表示在 F_p[x] 上），默认 0
    """
    var = sp.Symbol(variable)
    polys = [_parse(s.strip()) for s in expr.split(";")]

    domain = sp.QQ if modulus == 0 else sp.GF(modulus)

    if operation == "factor":
        result = sp.factor(polys[0], var, modulus=modulus if modulus else None)
        return _result("多项式因式分解", input=expr, output=sp.pretty(result), latex=sp.latex(result))

    elif operation == "gcd":
        if len(polys) < 2:
            return _result("错误", error="GCD 需要至少两个多项式，用分号分隔")
        result = sp.gcd(polys[0], polys[1], var, modulus=modulus if modulus else None)
        return _result("多项式 GCD", input=expr, output=sp.pretty(result), latex=sp.latex(result))

    elif operation == "lcm":
        if len(polys) < 2:
            return _result("错误", error="LCM 需要至少两个多项式，用分号分隔")
        result = sp.lcm(polys[0], polys[1], var)
        return _result("多项式 LCM", input=expr, output=sp.pretty(result), latex=sp.latex(result))

    elif operation == "div":
        if len(polys) < 2:
            return _result("错误", error="除法需要两个多项式，用分号分隔")
        q, r = sp.div(polys[0], polys[1], var, domain=domain)
        return _result("多项式带余除法", input=expr, quotient=sp.pretty(q), remainder=sp.pretty(r),
                       latex_q=sp.latex(q), latex_r=sp.latex(r))

    elif operation == "roots":
        result = sp.roots(polys[0], var)
        return _result("多项式求根", input=expr, roots=str(result))

    else:
        return _result("错误", error=f"未知运算: {operation}")


@math_tool(category="algebra", description="生成常见命名群：对称群 S_n、循环群 Z_n、二面体群 D_n、交替群 A_n")
def named_group(group_type: str, n: int) -> str:
    """生成常见命名群并返回其基本性质。

    Args:
        group_type: 群类型: symmetric(对称群 S_n), cyclic(循环群 Z_n), dihedral(二面体群 D_n), alternating(交替群 A_n)
        n: 群的参数 n
    """
    constructors = {
        "symmetric": SymmetricGroup,
        "cyclic": CyclicGroup,
        "dihedral": DihedralGroup,
        "alternating": AlternatingGroup,
    }
    if group_type not in constructors:
        return _result("错误", error=f"未知群类型: {group_type}，支持: {', '.join(constructors.keys())}")

    G = constructors[group_type](n)
    return _result(
        f"{group_type.capitalize()} 群 (n={n})",
        order=str(G.order()),
        is_abelian=str(G.is_abelian),
        is_solvable=str(G.is_solvable),
        is_nilpotent=str(G.is_nilpotent),
        generators=str(G.generators),
    )


@math_tool(category="algebra", description="置换运算：乘法、求逆、阶数、循环结构")
def permutation_operation(perm: str, operation: str = "info", perm2: str = "") -> str:
    """置换运算。

    Args:
        perm: 置换（循环表示），例如 '(0 1 2)(3 4)' 或 '[1, 2, 0, 4, 3]'（数组表示）
        operation: 运算: info(基本信息), multiply(乘法), inverse(逆), power(幂), order(阶)
        perm2: 第二个置换（乘法时使用）
    """
    import ast

    def _make_perm(s: str) -> Permutation:
        s = s.strip()
        if s.startswith("["):
            return Permutation(ast.literal_eval(s))
        elif s.startswith("("):
            # Parse cycle notation: (0 1 2)(3 4) -> Permutation(0,1,2)(3,4)
            cycles = []
            i = 0
            while i < len(s):
                if s[i] == "(":
                    j = s.index(")", i)
                    cycle = list(map(int, s[i + 1 : j].split()))
                    cycles.append(cycle)
                    i = j + 1
                else:
                    i += 1
            if len(cycles) == 1:
                return Permutation(cycles[0])
            p = Permutation(cycles[0])
            for c in cycles[1:]:
                p = p * Permutation(c)
            return p
        else:
            return Permutation(ast.literal_eval(s))

    p = _make_perm(perm)

    if operation == "info":
        return _result(
            "置换信息",
            array_form=str(p.array_form),
            cyclic_form=str(p.cyclic_form),
            order=str(p.order()),
            is_even=str(p.is_even),
            parity=("偶置换" if p.is_even else "奇置换"),
            inversions=str(p.inversions()),
        )
    elif operation == "multiply":
        if not perm2:
            return _result("错误", error="乘法需要提供 perm2")
        p2 = _make_perm(perm2)
        result = p * p2
        return _result("置换乘法", perm1=str(p.cyclic_form), perm2=str(p2.cyclic_form),
                       result_cyclic=str(result.cyclic_form), result_array=str(result.array_form))
    elif operation == "inverse":
        inv = p ** (-1)
        return _result("置换逆", input=str(p.cyclic_form), inverse=str(inv.cyclic_form))
    elif operation == "order":
        return _result("置换阶", input=str(p.cyclic_form), order=str(p.order()))
    else:
        return _result("错误", error=f"未知运算: {operation}")


@math_tool(category="algebra", description="计算商环 Z[x]/(f(x)) 中的多项式运算，或整数模运算 Z/nZ")
def quotient_ring_operation(
    expr: str, modulus_poly: str = "", ring_modulus: int = 0, variable: str = "x", operation: str = "simplify"
) -> str:
    """商环运算。

    Args:
        expr: 表达式，多个用分号分隔（乘法/加法时需要两个）
        modulus_poly: 模多项式，例如 'x**2 + 1'，留空表示整数环
        ring_modulus: 系数环的模数（0 表示 Z 或 Q），例如 7 表示 F_7
        variable: 变量，默认 'x'
        operation: 运算: simplify(化简), add(加法), multiply(乘法), power(幂)
    """
    var = sp.Symbol(variable)
    exprs = [_parse(s.strip()) for s in expr.split(";")]

    if modulus_poly:
        mod_p = _parse(modulus_poly)

        if operation == "simplify":
            result = sp.rem(exprs[0], mod_p, var)
        elif operation == "add":
            result = sp.rem(exprs[0] + exprs[1], mod_p, var) if len(exprs) >= 2 else exprs[0]
        elif operation == "multiply":
            result = sp.rem(exprs[0] * exprs[1], mod_p, var) if len(exprs) >= 2 else exprs[0]
        elif operation == "power":
            if len(exprs) >= 2:
                n = int(exprs[1])
                result = sp.rem(exprs[0] ** n, mod_p, var)
            else:
                result = exprs[0]
        else:
            return _result("错误", error=f"未知运算: {operation}")

        if ring_modulus > 0:
            poly = sp.Poly(result, var, domain=sp.GF(ring_modulus))
            result = poly.as_expr()

        return _result(
            f"商环运算 ({variable}[{variable}]/({modulus_poly}))",
            input=expr,
            operation=operation,
            output=sp.pretty(result),
            latex=sp.latex(result),
        )
    else:
        # Z/nZ arithmetic
        if ring_modulus <= 0:
            return _result("错误", error="整数商环需要 ring_modulus > 0")
        vals = [int(e) for e in exprs]
        if operation == "simplify":
            result = vals[0] % ring_modulus
        elif operation == "add":
            result = (vals[0] + vals[1]) % ring_modulus if len(vals) >= 2 else vals[0] % ring_modulus
        elif operation == "multiply":
            result = (vals[0] * vals[1]) % ring_modulus if len(vals) >= 2 else vals[0] % ring_modulus
        elif operation == "power":
            result = pow(vals[0], vals[1], ring_modulus) if len(vals) >= 2 else vals[0] % ring_modulus
        else:
            return _result("错误", error=f"未知运算: {operation}")

        return _result(f"Z/{ring_modulus}Z 运算", input=expr, operation=operation, output=str(result))


@math_tool(category="algebra", description="验证集合在某运算下是否构成群/环/域")
def check_algebraic_structure(elements: str, operation_table: str, structure: str = "group") -> str:
    """验证代数结构。

    Args:
        elements: 元素列表，例如 '[0, 1, 2, 3]'
        operation_table: 运算表（嵌套列表），例如 '[[0,1,2,3],[1,2,3,0],[2,3,0,1],[3,0,1,2]]' 表示 Z/4Z 加法
        structure: 要验证的结构类型: group, abelian_group
    """
    import ast
    elems = ast.literal_eval(elements)
    table = ast.literal_eval(operation_table)
    n = len(elems)

    results: dict[str, str] = {"elements": str(elems)}

    # Closure check
    closure = all(table[i][j] in range(n) for i in range(n) for j in range(n))
    results["封闭性"] = "✓" if closure else "✗"

    if not closure:
        return _result("代数结构检验", **results, conclusion="不构成群（不满足封闭性）")

    # Identity check
    identity = None
    for e in range(n):
        if all(table[e][j] == j for j in range(n)) and all(table[i][e] == i for i in range(n)):
            identity = e
            break
    results["单位元"] = str(elems[identity]) if identity is not None else "✗ 不存在"

    if identity is None:
        return _result("代数结构检验", **results, conclusion="不构成群（无单位元）")

    # Inverse check
    has_inverses = True
    inverses = {}
    for i in range(n):
        found = False
        for j in range(n):
            if table[i][j] == identity and table[j][i] == identity:
                inverses[elems[i]] = elems[j]
                found = True
                break
        if not found:
            has_inverses = False
            break
    results["逆元"] = str(inverses) if has_inverses else "✗ 不是所有元素都有逆"

    if not has_inverses:
        return _result("代数结构检验", **results, conclusion="不构成群（部分元素无逆元）")

    # Associativity check (brute force for small groups)
    assoc = True
    for i in range(n):
        for j in range(n):
            for k in range(n):
                if table[table[i][j]][k] != table[i][table[j][k]]:
                    assoc = False
                    break
            if not assoc:
                break
        if not assoc:
            break
    results["结合律"] = "✓" if assoc else "✗"

    if not assoc:
        return _result("代数结构检验", **results, conclusion="不构成群（不满足结合律）")

    # Commutativity
    commutative = all(table[i][j] == table[j][i] for i in range(n) for j in range(n))
    results["交换律"] = "✓" if commutative else "✗"

    if structure == "abelian_group":
        if commutative:
            return _result("代数结构检验", **results, conclusion=f"✓ 构成 {n} 阶交换群")
        else:
            return _result("代数结构检验", **results, conclusion=f"构成 {n} 阶群（但不是交换群）")
    else:
        return _result("代数结构检验", **results,
                       conclusion=f"✓ 构成 {n} 阶{'交换' if commutative else '非交换'}群")


@math_tool(category="algebra", description="计算最小多项式或特征多项式")
def minimal_polynomial(expr: str, variable: str = "x") -> str:
    """计算代数数的最小多项式。

    Args:
        expr: 代数数表达式，例如 'sqrt(2) + sqrt(3)'
        variable: 最小多项式的变量，默认 'x'
    """
    e = _parse(expr)
    var = _sym(variable)
    result = sp.minimal_polynomial(e, var)
    factored = sp.factor(result)
    return _result(
        "最小多项式",
        algebraic_number=expr,
        minimal_poly=sp.pretty(result),
        factored=sp.pretty(factored),
        latex=sp.latex(result),
        degree=str(sp.degree(result, var)),
    )


def _sym(name: str) -> sp.Symbol:
    if name in _LOCAL_DICT and isinstance(_LOCAL_DICT[name], sp.Symbol):
        return _LOCAL_DICT[name]
    return sp.Symbol(name)
