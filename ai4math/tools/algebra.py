"""Abstract algebra tools: groups, rings, fields, polynomials, permutations, etc."""

from __future__ import annotations

import sympy as sp
from sympy.combinatorics import Permutation
from sympy.combinatorics.named_groups import (
    AlternatingGroup,
    CyclicGroup,
    DihedralGroup,
    SymmetricGroup,
)

from ai4math.tools._shared import (
    format_result,
    get_or_make_symbol,
    make_local_dict,
    safe_literal_eval,
    safe_parse_expr,
)
from ai4math.tools.registry import math_tool

_LOCAL_DICT = make_local_dict()


def _parse(expr_str: str, extra_locals: dict | None = None) -> sp.Expr:
    return safe_parse_expr(expr_str, local_dict=_LOCAL_DICT, extra_locals=extra_locals)


def _sym(name: str) -> sp.Symbol:
    return get_or_make_symbol(name, _LOCAL_DICT)


def _result(title: str, **kwargs) -> str:
    return format_result(title, **kwargs)


def _poly_pow_mod(base_expr: sp.Expr, exp: int, mod_expr: sp.Expr, var: sp.Symbol, domain) -> sp.Expr:
    """Compute (base_expr ** exp) mod mod_expr via binary modular exponentiation."""
    if exp < 0:
        raise ValueError("商环多项式幂指数必须为非负整数")
    mod_poly = sp.Poly(mod_expr, var, domain=domain)
    acc = sp.Poly(1, var, domain=domain) % mod_poly
    cur = sp.Poly(base_expr, var, domain=domain) % mod_poly
    n = exp
    while n > 0:
        if n & 1:
            acc = (acc * cur) % mod_poly
        cur = (cur * cur) % mod_poly
        n >>= 1
    return acc.as_expr()


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
    var = _sym(variable)
    polys = [_parse(s.strip(), extra_locals={variable: var}) for s in expr.split(";") if s.strip()]
    if not polys:
        return _result("错误", error="请提供至少一个多项式表达式")

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
        if modulus:
            p1 = sp.Poly(polys[0], var, domain=domain)
            p2 = sp.Poly(polys[1], var, domain=domain)
            result = p1.lcm(p2).as_expr()
        else:
            result = sp.lcm(polys[0], polys[1], var)
        return _result("多项式 LCM", input=expr, output=sp.pretty(result), latex=sp.latex(result))

    elif operation == "div":
        if len(polys) < 2:
            return _result("错误", error="除法需要两个多项式，用分号分隔")
        q, r = sp.div(polys[0], polys[1], var, domain=domain)
        return _result(
            "多项式带余除法",
            input=expr,
            quotient=sp.pretty(q),
            remainder=sp.pretty(r),
            latex_q=sp.latex(q),
            latex_r=sp.latex(r),
            latex=f"q(x) = {sp.latex(q)},\\; r(x) = {sp.latex(r)}",
        )

    elif operation == "roots":
        if modulus:
            poly_gf = sp.Poly(polys[0], var, domain=domain)
            if poly_gf.is_zero:
                return _result("错误", error="零多项式在有限域上有全体元素为根")
            _, factors = poly_gf.factor_list()
            roots_mod: dict[int, int] = {}
            for fac, mult in factors:
                if fac.degree() == 1:
                    coeffs = fac.all_coeffs()
                    c1 = int(coeffs[0]) % modulus
                    c0 = int(coeffs[1]) % modulus
                    root_val = (-c0 * pow(c1, -1, modulus)) % modulus
                    roots_mod[root_val] = roots_mod.get(root_val, 0) + int(mult)
            roots_mod = dict(sorted(roots_mod.items()))
            ltx = r",\; ".join(f"{r}\\text{{ (重数 {m})}}" for r, m in roots_mod.items()) or r"\varnothing"
            return _result(
                f"F_{modulus} 上多项式求根",
                input=expr,
                modulus=str(modulus),
                roots=str(roots_mod),
                output=str(roots_mod),
                latex=ltx,
            )
        result = sp.roots(polys[0], var)
        ltx = r",\; ".join(f"{sp.latex(r)}\\text{{ (重数 {m})}}" for r, m in result.items()) or r"\varnothing"
        return _result("多项式求根", input=expr, roots=str(result), output=str(result), latex=ltx)

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
    order_str = str(G.order())
    return _result(
        f"{group_type.capitalize()} 群 (n={n})",
        order=order_str,
        is_abelian=str(G.is_abelian),
        is_solvable=str(G.is_solvable),
        is_nilpotent=str(G.is_nilpotent),
        generators=str(G.generators),
        output=f"|G| = {order_str}, abelian={G.is_abelian}, solvable={G.is_solvable}",
    )


@math_tool(category="algebra", description="置换运算：乘法、求逆、幂、阶数、循环结构")
def permutation_operation(perm: str, operation: str = "info", perm2: str = "") -> str:
    """置换运算（默认采用 0-基循环或数组表示，如 '(0 1 2)(3 4)'；也兼容不含 0 的正整数循环如 '(1 2 3)'）。

    Args:
        perm: 置换（循环表示），例如 '(0 1 2)(3 4)' 或 '[1, 2, 0, 4, 3]'（数组表示）
        operation: 运算: info(基本信息), multiply(乘法), inverse(逆), power(幂, perm2 填整数指数), order(阶)
        perm2: 第二个置换（multiply 时使用）或整数幂指数（power 时使用，如 '2' 或 '-1'）
    """

    def _make_perm(s: str) -> Permutation:
        s = s.strip()
        if s.startswith("["):
            arr = safe_literal_eval(s)
            return Permutation(arr)
        elif s.startswith("("):
            cycles: list[list[int]] = []
            i = 0
            while i < len(s):
                if s[i] == "(":
                    j = s.index(")", i)
                    inner = s[i + 1 : j].replace(",", " ").strip()
                    if inner:
                        cycles.append([int(tok) for tok in inner.split()])
                    i = j + 1
                else:
                    i += 1
            if not cycles:
                return Permutation()
            # SymPy treats a 2D list as disjoint/sequential cycles: Permutation([[0, 1, 2], [3, 4]])
            p_acc = Permutation([cycles[0]])
            for cyc in cycles[1:]:
                c_perm = Permutation([cyc])
                max_sz = max(p_acc.size, c_perm.size)
                p_acc = Permutation(p_acc, size=max_sz) * Permutation(c_perm, size=max_sz)
            return p_acc
        else:
            parsed = safe_literal_eval(s)
            return Permutation(parsed)

    p = _make_perm(perm)

    if operation == "info":
        parity = "偶置换" if p.is_even else "奇置换"
        return _result(
            "置换信息",
            array_form=str(p.array_form),
            cyclic_form=str(p.cyclic_form),
            order=str(p.order()),
            is_even=str(p.is_even),
            parity=parity,
            inversions=str(p.inversions()),
            output=f"cyclic={p.cyclic_form}, order={p.order()}, parity={parity}",
        )
    elif operation == "multiply":
        if not perm2.strip():
            return _result("错误", error="乘法需要提供 perm2")
        p2 = _make_perm(perm2)
        max_sz = max(p.size, p2.size)
        result = Permutation(p, size=max_sz) * Permutation(p2, size=max_sz)
        return _result(
            "置换乘法",
            perm1=str(p.cyclic_form),
            perm2=str(p2.cyclic_form),
            result_cyclic=str(result.cyclic_form),
            result_array=str(result.array_form),
            order=str(result.order()),
            output=f"cyclic={result.cyclic_form}, order={result.order()}",
        )
    elif operation == "inverse":
        inv = p ** (-1)
        return _result(
            "置换逆",
            input=str(p.cyclic_form),
            inverse=str(inv.cyclic_form),
            output=str(inv.cyclic_form),
        )
    elif operation == "power":
        if not perm2.strip():
            return _result("错误", error="幂运算需要在 perm2 中提供整数指数，例如 perm2='2'")
        try:
            k = int(perm2.strip())
        except ValueError:
            return _result("错误", error=f"幂指数必须为整数，收到: {perm2!r}")
        pw = p ** k
        return _result(
            f"置换 {k} 次幂",
            input=str(p.cyclic_form),
            exponent=str(k),
            result_cyclic=str(pw.cyclic_form),
            result_array=str(pw.array_form),
            order=str(pw.order()),
            output=str(pw.cyclic_form),
        )
    elif operation == "order":
        return _result(
            "置换阶",
            input=str(p.cyclic_form),
            order=str(p.order()),
            output=str(p.order()),
        )
    else:
        return _result("错误", error=f"未知运算: {operation}")


@math_tool(category="algebra", description="计算商环 Z[x]/(f(x)) 中的多项式运算，或整数模运算 Z/nZ")
def quotient_ring_operation(
    expr: str, modulus_poly: str = "", ring_modulus: int = 0, variable: str = "x", operation: str = "simplify"
) -> str:
    """商环运算。

    Args:
        expr: 表达式，多个用分号分隔（乘法/加法/幂运算时需要两个）
        modulus_poly: 模多项式，例如 'x**2 + 1'，留空表示整数环
        ring_modulus: 系数环的模数（0 表示 Z 或 Q），例如 7 表示 F_7
        variable: 变量，默认 'x'
        operation: 运算: simplify(化简), add(加法), multiply(乘法), power(幂)
    """
    var = _sym(variable)
    exprs = [_parse(s.strip(), extra_locals={variable: var}) for s in expr.split(";") if s.strip()]
    if not exprs:
        return _result("错误", error="请提供至少一个表达式")

    if modulus_poly.strip():
        mod_p = _parse(modulus_poly, extra_locals={variable: var})
        domain = sp.GF(ring_modulus) if ring_modulus > 0 else sp.QQ

        if operation == "simplify":
            result = sp.rem(exprs[0], mod_p, var, domain=domain)
        elif operation == "add":
            result = sp.rem(exprs[0] + exprs[1], mod_p, var, domain=domain) if len(exprs) >= 2 else exprs[0]
        elif operation == "multiply":
            result = sp.rem(exprs[0] * exprs[1], mod_p, var, domain=domain) if len(exprs) >= 2 else exprs[0]
        elif operation == "power":
            if len(exprs) >= 2:
                n = int(exprs[1])
                result = _poly_pow_mod(exprs[0], n, mod_p, var, domain=domain)
            else:
                result = sp.rem(exprs[0], mod_p, var, domain=domain)
        else:
            return _result("错误", error=f"未知运算: {operation}")

        if ring_modulus > 0:
            poly = sp.Poly(result, var, domain=sp.GF(ring_modulus))
            result = poly.as_expr()

        coeff_ring = f"F_{ring_modulus}" if ring_modulus > 0 else "Q"
        return _result(
            f"商环运算 ({coeff_ring}[{variable}]/({modulus_poly}))",
            input=expr,
            operation=operation,
            output=sp.pretty(result),
            latex=sp.latex(result),
        )
    else:
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


@math_tool(category="algebra", description="验证集合在某运算下是否构成群/交换群")
def check_algebraic_structure(elements: str, operation_table: str, structure: str = "group") -> str:
    """验证代数结构。

    Args:
        elements: 元素列表，例如 '[0, 1, 2, 3]' 或 '[1, -1]'
        operation_table: 运算表（嵌套列表，表项为 elements 中的元素），例如 '[[1, -1], [-1, 1]]'
        structure: 要验证的结构类型: group, abelian_group
    """
    elems = safe_literal_eval(elements)
    table = safe_literal_eval(operation_table)

    if not isinstance(elems, list) or len(elems) == 0:
        return _result("输入错误", error="elements 必须是非空列表")
    n = len(elems)
    if len(set(elems)) != n:
        return _result("输入错误", error="elements 中存在重复元素")
    if not isinstance(table, list) or len(table) != n or any(not isinstance(row, list) or len(row) != n for row in table):
        return _result("输入错误", error=f"运算表维度必须为 {n}×{n}（与元素个数一致）")

    elem_to_idx = {el: idx for idx, el in enumerate(elems)}
    results: dict[str, str] = {"elements": str(elems)}

    # Closure check against actual elements in `elems`
    closure = all(table[i][j] in elem_to_idx for i in range(n) for j in range(n))
    results["封闭性"] = "✓" if closure else "✗"

    if not closure:
        conclusion = "不构成群（不满足封闭性）"
        return _result("代数结构检验", **results, conclusion=conclusion, output=conclusion)

    idx_table = [[elem_to_idx[table[i][j]] for j in range(n)] for i in range(n)]

    # Identity check
    identity = None
    for e in range(n):
        if all(idx_table[e][j] == j for j in range(n)) and all(idx_table[i][e] == i for i in range(n)):
            identity = e
            break
    results["单位元"] = str(elems[identity]) if identity is not None else "✗ 不存在"

    if identity is None:
        conclusion = "不构成群（无单位元）"
        return _result("代数结构检验", **results, conclusion=conclusion, output=conclusion)

    # Inverse check
    has_inverses = True
    inverses = {}
    for i in range(n):
        found = False
        for j in range(n):
            if idx_table[i][j] == identity and idx_table[j][i] == identity:
                inverses[elems[i]] = elems[j]
                found = True
                break
        if not found:
            has_inverses = False
            break
    results["逆元"] = str(inverses) if has_inverses else "✗ 不是所有元素都有逆"

    if not has_inverses:
        conclusion = "不构成群（部分元素无逆元）"
        return _result("代数结构检验", **results, conclusion=conclusion, output=conclusion)

    # Associativity check
    assoc = True
    for i in range(n):
        for j in range(n):
            for k in range(n):
                if idx_table[idx_table[i][j]][k] != idx_table[i][idx_table[j][k]]:
                    assoc = False
                    break
            if not assoc:
                break
        if not assoc:
            break
    results["结合律"] = "✓" if assoc else "✗"

    if not assoc:
        conclusion = "不构成群（不满足结合律）"
        return _result("代数结构检验", **results, conclusion=conclusion, output=conclusion)

    # Commutativity
    commutative = all(idx_table[i][j] == idx_table[j][i] for i in range(n) for j in range(n))
    results["交换律"] = "✓" if commutative else "✗"

    if structure == "abelian_group":
        conclusion = f"✓ 构成 {n} 阶交换群" if commutative else f"构成 {n} 阶群（但不是交换群）"
    else:
        conclusion = f"✓ 构成 {n} 阶{'交换' if commutative else '非交换'}群"
    return _result("代数结构检验", **results, conclusion=conclusion, output=conclusion)


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
