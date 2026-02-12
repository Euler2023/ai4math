"""Advanced mathematics tools powered by SageMath.

Covers: Galois theory, number fields, elliptic curves, Groebner bases,
homological algebra, advanced group theory, combinatorics, number theory, etc.
"""

from __future__ import annotations

import json
from functools import lru_cache

from ai4math.tools.registry import math_tool


def _sage():
    """Lazy import sage.all to avoid slow startup when not needed."""
    import sage.all as sa
    return sa


def _result(title: str, **kwargs) -> str:
    out = {"title": title}
    for k, v in kwargs.items():
        out[k] = str(v)
    out["_display_instruction"] = "你必须在回复中用 $$ LaTeX $$ 展示此工具返回的 latex 字段内容，不得省略"
    return json.dumps(out, ensure_ascii=False)


def _latex(obj) -> str:
    """Get LaTeX representation of a Sage object."""
    sa = _sage()
    try:
        return sa.latex(obj)
    except Exception:
        return str(obj)


# ===========================================================================
# Number Theory
# ===========================================================================

@math_tool(category="sage_number_theory", description="素性检验、因式分解、欧拉函数、模逆等数论运算")
def number_theory_operation(n: str, operation: str = "factor") -> str:
    """数论运算。

    Args:
        n: 整数或数论表达式，例如 '100' 或 '2**127 - 1'
        operation: 运算类型: factor(因式分解), is_prime(素性检验), euler_phi(欧拉函数), divisors(因子列表), next_prime(下一个素数), mod_inverse(模逆, 格式 'a; m'), crt(中国剩余定理, 格式 'r1,r2,...; m1,m2,...')
    """
    sa = _sage()

    if operation == "mod_inverse":
        parts = n.split(";")
        a = sa.ZZ(parts[0].strip())
        m = sa.ZZ(parts[1].strip())
        result = sa.inverse_mod(a, m)
        return _result("模逆元", input=f"{a} mod {m}", result=str(result),
                       latex=f"{a}^{{-1}} \\equiv {result} \\pmod{{{m}}}")

    if operation == "crt":
        parts = n.split(";")
        remainders = [sa.ZZ(x.strip()) for x in parts[0].split(",")]
        moduli = [sa.ZZ(x.strip()) for x in parts[1].split(",")]
        result = sa.crt(remainders, moduli)
        mod_product = sa.prod(moduli)
        return _result("中国剩余定理", remainders=str(remainders), moduli=str(moduli),
                       result=str(result), latex=f"x \\equiv {result} \\pmod{{{mod_product}}}")

    val = sa.ZZ(sa.sage_eval(n))

    if operation == "factor":
        f = val.factor()
        return _result("整数因式分解", input=str(val), factorization=str(f), latex=_latex(f))
    elif operation == "is_prime":
        return _result("素性检验", input=str(val), is_prime=str(val.is_prime()))
    elif operation == "euler_phi":
        phi = sa.euler_phi(val)
        return _result("欧拉函数", input=str(val), euler_phi=str(phi), latex=f"\\varphi({val}) = {phi}")
    elif operation == "divisors":
        divs = val.divisors()
        return _result("因子列表", input=str(val), divisors=str(divs),
                       num_divisors=str(len(divs)))
    elif operation == "next_prime":
        p = sa.next_prime(val)
        return _result("下一个素数", input=str(val), next_prime=str(p))
    else:
        return _result("错误", error=f"未知运算: {operation}")


# ===========================================================================
# Finite Fields & Polynomial Rings (advanced)
# ===========================================================================

@math_tool(category="sage_algebra", description="有限域 GF(p^n) 上的多项式因式分解与运算")
def finite_field_polynomial(expr: str, p: int, n: int = 1, operation: str = "factor") -> str:
    """有限域上的多项式运算。

    Args:
        expr: 多项式表达式（多个用分号分隔），例如 'x**4 - 1'
        p: 有限域的特征（素数）
        n: 有限域的扩张次数，GF(p^n)，默认 1
        operation: 运算: factor(因式分解), roots(求根), irreducible_check(不可约检验), gcd(最大公因式)
    """
    sa = _sage()
    F = sa.GF(p**n, 'a') if n > 1 else sa.GF(p)
    R = sa.PolynomialRing(F, 'x')
    x = R.gen()

    polys = []
    for s in expr.split(";"):
        polys.append(sa.sage_eval(s.strip(), locals={'x': x}))

    field_name = f"GF({p})" if n == 1 else f"GF({p}^{n})"

    if operation == "factor":
        f = polys[0].factor()
        return _result(f"{field_name} 上因式分解", input=expr, factorization=str(f), latex=_latex(f))
    elif operation == "roots":
        roots = polys[0].roots()
        return _result(f"{field_name} 上求根", input=expr,
                       roots=str([(str(r), m) for r, m in roots]))
    elif operation == "irreducible_check":
        is_irr = polys[0].is_irreducible()
        return _result(f"{field_name} 上不可约检验", input=expr, is_irreducible=str(is_irr))
    elif operation == "gcd":
        if len(polys) < 2:
            return _result("错误", error="GCD 需要两个多项式，用分号分隔")
        g = sa.gcd(polys[0], polys[1])
        return _result(f"{field_name} 上 GCD", input=expr, gcd=str(g), latex=_latex(g))
    else:
        return _result("错误", error=f"未知运算: {operation}")


# ===========================================================================
# Groebner Bases & Ideals
# ===========================================================================

@math_tool(category="sage_algebra", description="计算多项式理想的 Groebner 基、理想成员检验、商环运算")
def groebner_basis(polynomials: str, variables: str = "x,y", ring: str = "QQ", order: str = "degrevlex") -> str:
    """Groebner 基计算。

    Args:
        polynomials: 多项式列表（分号分隔），例如 'x**2 + y**2 - 1; x - y'
        variables: 变量列表（逗号分隔），默认 'x,y'
        ring: 系数环: QQ(有理数), RR(实数), GF(p)(有限域, 如 GF(7))，默认 'QQ'
        order: 单项式序: degrevlex(默认), lex, deglex
    """
    sa = _sage()

    # Build coefficient ring
    if ring == "QQ":
        base = sa.QQ
    elif ring == "RR":
        base = sa.RR
    elif ring.startswith("GF("):
        p = int(ring[3:-1])
        base = sa.GF(p)
    else:
        base = sa.QQ

    var_names = ",".join(v.strip() for v in variables.split(","))
    R = sa.PolynomialRing(base, var_names, order=order)
    gens = R.gens()
    local_vars = {str(g): g for g in gens}

    polys = []
    for s in polynomials.split(";"):
        polys.append(sa.sage_eval(s.strip(), locals=local_vars))

    I = R.ideal(polys)
    gb = I.groebner_basis()

    return _result(
        "Groebner 基",
        ring=f"{ring}[{var_names}]",
        order=order,
        input_generators=str(polys),
        groebner_basis=str(list(gb)),
        latex=_latex(gb),
        dimension=str(I.dimension()),
    )


@math_tool(category="sage_algebra", description="检验多项式是否属于某个理想（理想成员检验）")
def ideal_membership(polynomial: str, generators: str, variables: str = "x,y", ring: str = "QQ") -> str:
    """理想成员检验。

    Args:
        polynomial: 待检验的多项式
        generators: 理想的生成元（分号分隔）
        variables: 变量列表（逗号分隔），默认 'x,y'
        ring: 系数环，默认 'QQ'
    """
    sa = _sage()
    base = sa.QQ if ring == "QQ" else sa.GF(int(ring[3:-1])) if ring.startswith("GF(") else sa.QQ

    var_names = ",".join(v.strip() for v in variables.split(","))
    R = sa.PolynomialRing(base, var_names, order='degrevlex')
    gens = R.gens()
    local_vars = {str(g): g for g in gens}

    f = sa.sage_eval(polynomial.strip(), locals=local_vars)
    gen_polys = [sa.sage_eval(s.strip(), locals=local_vars) for s in generators.split(";")]
    I = R.ideal(gen_polys)

    result = f in I
    return _result("理想成员检验", polynomial=str(f), ideal_generators=str(gen_polys),
                   is_member=str(result))


# ===========================================================================
# Number Fields & Galois Theory
# ===========================================================================

@math_tool(category="sage_algebra", description="构造数域扩张并计算其性质：次数、Galois 群、判别式等")
def number_field_info(poly: str, name: str = "a") -> str:
    """构造数域并返回其性质。

    Args:
        poly: 不可约多项式（定义数域的最小多项式），例如 'x**4 - 2' 或 'x**2 + 1'
        name: 原始元素的名字，默认 'a'
    """
    sa = _sage()
    R = sa.PolynomialRing(sa.QQ, 'x')
    x = R.gen()
    f = sa.sage_eval(poly, locals={'x': x})

    K = sa.NumberField(f, name)
    info = {
        "数域": str(K),
        "次数": str(K.degree()),
        "判别式": str(K.discriminant()),
        "签名 (r1, r2)": str(K.signature()),
        "整数环": str(K.ring_of_integers()),
        "类数": str(K.class_number()),
    }

    try:
        G = K.galois_group()
        info["Galois 群"] = str(G)
        info["Galois 群阶"] = str(G.order())
    except Exception as e:
        info["Galois 群"] = f"无法计算: {e}"

    info["latex"] = _latex(K)
    return json.dumps(info, ensure_ascii=False)


@math_tool(category="sage_algebra", description="计算多项式的 Galois 群")
def galois_group(poly: str) -> str:
    """计算有理数域上多项式的 Galois 群。

    Args:
        poly: 有理数域上的多项式，例如 'x**4 - 2' 或 'x**5 - x - 1'
    """
    sa = _sage()
    R = sa.PolynomialRing(sa.QQ, 'x')
    x = R.gen()
    f = sa.sage_eval(poly, locals={'x': x})

    G = f.galois_group(pari_group=True)
    return _result(
        "Galois 群",
        polynomial=poly,
        galois_group=str(G),
        order=str(G.order()),
        latex=_latex(G),
    )


# ===========================================================================
# Elliptic Curves
# ===========================================================================

@math_tool(category="sage_algebra", description="椭圆曲线分析：秩、扭子群、判别式、j-不变量等")
def elliptic_curve_info(a_invariants: str, base_field: str = "QQ") -> str:
    """椭圆曲线分析。

    Args:
        a_invariants: Weierstrass 模型的系数，例如 '[0, -1, 1, 0, 0]' (y^2+y=x^3-x^2) 或短形式 '[0, 1]' (y^2=x^3+x) 或 Cremona label 如 '11a1'
        base_field: 基域，默认 'QQ'
    """
    sa = _sage()
    import ast

    if base_field == "QQ":
        K = sa.QQ
    elif base_field.startswith("GF("):
        p = int(base_field[3:-1])
        K = sa.GF(p)
    else:
        K = sa.QQ

    try:
        # Try Cremona label first
        if a_invariants.replace(" ", "").isalnum():
            E = sa.EllipticCurve(a_invariants.strip())
        else:
            coeffs = ast.literal_eval(a_invariants)
            E = sa.EllipticCurve(K, coeffs)
    except Exception:
        coeffs = ast.literal_eval(a_invariants)
        E = sa.EllipticCurve(K, coeffs)

    info = {
        "椭圆曲线": str(E),
        "判别式": str(E.discriminant()),
        "j-不变量": str(E.j_invariant()),
    }

    if K == sa.QQ:
        try:
            info["秩"] = str(E.rank())
        except Exception:
            info["秩"] = "计算超时"
        try:
            info["扭子群"] = str(E.torsion_subgroup())
        except Exception:
            pass
        try:
            info["导子"] = str(E.conductor())
        except Exception:
            pass
        try:
            info["Cremona label"] = str(E.cremona_label())
        except Exception:
            pass
    else:
        try:
            info["有理点数"] = str(E.cardinality())
        except Exception:
            pass
        try:
            info["是否超奇异"] = str(E.is_supersingular())
        except Exception:
            pass

    info["latex"] = _latex(E)
    return json.dumps(info, ensure_ascii=False)


# ===========================================================================
# Advanced Group Theory
# ===========================================================================

@math_tool(category="sage_algebra", description="高级群论：子群格、正规子群、中心、换位子群、Sylow 子群等")
def advanced_group_theory(group_type: str, n: int, operation: str = "info") -> str:
    """高级群论运算。

    Args:
        group_type: 群类型: symmetric(S_n), alternating(A_n), dihedral(D_n), cyclic(Z_n)
        n: 群的参数
        operation: 运算: info(基本信息), center(中心), commutator(换位子群), sylow(Sylow子群, 用于 S_n), normal_subgroups(正规子群), conjugacy_classes(共轭类), character_table(特征标表)
    """
    sa = _sage()

    constructors = {
        "symmetric": sa.SymmetricGroup,
        "alternating": sa.AlternatingGroup,
        "dihedral": sa.DihedralGroup,
        "cyclic": sa.CyclicPermutationGroup,
    }

    if group_type not in constructors:
        return _result("错误", error=f"未知群类型: {group_type}")

    G = constructors[group_type](n)

    if operation == "info":
        return _result(
            f"{group_type}({n}) 详细信息",
            order=str(G.order()),
            is_abelian=str(G.is_abelian()),
            is_cyclic=str(G.is_cyclic()),
            is_solvable=str(G.is_solvable()),
            is_nilpotent=str(G.is_nilpotent()),
            is_simple=str(G.is_simple()),
            exponent=str(G.exponent()),
            center_order=str(G.center().order()),
            derived_series_lengths=str(len(G.derived_series())),
        )
    elif operation == "center":
        Z = G.center()
        return _result("中心", group=str(G), center=str(Z), center_order=str(Z.order()),
                       center_generators=str(Z.gens()))
    elif operation == "commutator":
        D = G.commutator()
        return _result("换位子群 [G,G]", group=str(G), commutator=str(D),
                       order=str(D.order()), index=str(G.order() // D.order()))
    elif operation == "sylow":
        # Find all Sylow p-subgroups for each prime dividing |G|
        order = G.order()
        primes = sa.prime_factors(order)
        results = {}
        for p in primes:
            S = G.sylow_subgroup(p)
            results[f"Sylow {p}-子群"] = f"阶 = {S.order()}"
        return _result("Sylow 子群", group=str(G), order=str(order), **results)
    elif operation == "normal_subgroups":
        ns = G.normal_subgroups()
        ns_info = [f"阶 {H.order()}" for H in ns]
        return _result("正规子群", group=str(G), count=str(len(ns)),
                       normal_subgroups=str(ns_info))
    elif operation == "conjugacy_classes":
        cc = G.conjugacy_classes()
        cc_info = [f"代表元 {c.representative()}, 大小 {c.cardinality()}" for c in cc]
        return _result("共轭类", group=str(G), num_classes=str(len(cc)),
                       classes=str(cc_info))
    elif operation == "character_table":
        ct = G.character_table()
        return _result("特征标表", group=str(G), character_table=str(ct),
                       latex=_latex(ct))
    else:
        return _result("错误", error=f"未知运算: {operation}")


# ===========================================================================
# Combinatorics
# ===========================================================================

@math_tool(category="sage_combinatorics", description="组合数学：分拆数、Catalan数、Stirling数、Bell数、生成函数等")
def combinatorics_operation(n: str, operation: str = "partitions") -> str:
    """组合数学运算。

    Args:
        n: 参数（整数），某些运算需要两个参数用分号分隔，例如 '10' 或 '10; 3'
        operation: 运算: partitions(整数分拆数), partition_list(列出分拆), catalan(Catalan数), stirling1(第一类Stirling数, 需n;k), stirling2(第二类Stirling数, 需n;k), bell(Bell数), binomial(二项式系数, 需n;k), fibonacci(Fibonacci数), bernoulli(Bernoulli数), generating_function(分拆生成函数)
    """
    sa = _sage()
    parts = [s.strip() for s in n.split(";")]

    if operation == "partitions":
        val = sa.ZZ(parts[0])
        count = sa.Partitions(val).cardinality()
        return _result("整数分拆数", n=str(val), p_n=str(count),
                       latex=f"p({val}) = {count}")
    elif operation == "partition_list":
        val = sa.ZZ(parts[0])
        ps = list(sa.Partitions(val))
        return _result("整数分拆列表", n=str(val), count=str(len(ps)),
                       partitions=str(ps[:50]) + ("..." if len(ps) > 50 else ""))
    elif operation == "catalan":
        val = sa.ZZ(parts[0])
        c = sa.catalan_number(val)
        return _result("Catalan 数", n=str(val), catalan=str(c),
                       latex=f"C_{{{val}}} = {c}")
    elif operation == "stirling1":
        nn, k = sa.ZZ(parts[0]), sa.ZZ(parts[1])
        s = sa.stirling_number1(nn, k)
        return _result("第一类 Stirling 数", n=str(nn), k=str(k), result=str(s),
                       latex=f"s({nn},{k}) = {s}")
    elif operation == "stirling2":
        nn, k = sa.ZZ(parts[0]), sa.ZZ(parts[1])
        s = sa.stirling_number2(nn, k)
        return _result("第二类 Stirling 数", n=str(nn), k=str(k), result=str(s),
                       latex=f"S({nn},{k}) = {s}")
    elif operation == "bell":
        val = sa.ZZ(parts[0])
        b = sa.bell_number(val)
        return _result("Bell 数", n=str(val), bell=str(b),
                       latex=f"B_{{{val}}} = {b}")
    elif operation == "binomial":
        nn, k = sa.ZZ(parts[0]), sa.ZZ(parts[1])
        b = sa.binomial(nn, k)
        return _result("二项式系数", n=str(nn), k=str(k), result=str(b),
                       latex=f"\\binom{{{nn}}}{{{k}}} = {b}")
    elif operation == "fibonacci":
        val = sa.ZZ(parts[0])
        f = sa.fibonacci(val)
        return _result("Fibonacci 数", n=str(val), fibonacci=str(f),
                       latex=f"F_{{{val}}} = {f}")
    elif operation == "bernoulli":
        val = sa.ZZ(parts[0])
        b = sa.bernoulli(val)
        return _result("Bernoulli 数", n=str(val), bernoulli=str(b),
                       latex=f"B_{{{val}}} = {_latex(b)}")
    elif operation == "generating_function":
        val = sa.ZZ(parts[0])
        R = sa.PowerSeriesRing(sa.ZZ, 'q', default_prec=val + 1)
        q = R.gen()
        gf = sa.prod(1 / (1 - q**i) for i in range(1, val + 1))
        return _result("分拆生成函数", precision=str(val),
                       series=str(gf),
                       latex=_latex(gf))
    else:
        return _result("错误", error=f"未知运算: {operation}")


# ===========================================================================
# Lattice & Module Theory
# ===========================================================================

@math_tool(category="sage_algebra", description="格 (Lattice) 运算：Smith 标准形、Hermite 标准形、格基约化 (LLL)")
def lattice_operation(matrix: str, operation: str = "smith_form") -> str:
    """格与模运算。

    Args:
        matrix: 整数矩阵，例如 '[[1,2,3],[4,5,6],[7,8,9]]'
        operation: 运算: smith_form(Smith 标准形), hermite_form(Hermite 标准形), lll(LLL 格基约化), det(行列式), kernel(核)
    """
    sa = _sage()
    import ast
    data = ast.literal_eval(matrix)
    M = sa.matrix(sa.ZZ, data)

    if operation == "smith_form":
        D, U, V = M.smith_form()
        return _result("Smith 标准形", input=str(M), smith_form=str(D),
                       invariant_factors=str(D.diagonal()),
                       latex=_latex(D))
    elif operation == "hermite_form":
        H = M.hermite_form()
        return _result("Hermite 标准形", input=str(M), hermite_form=str(H),
                       latex=_latex(H))
    elif operation == "lll":
        L = M.LLL()
        return _result("LLL 格基约化", input=str(M), reduced_basis=str(L),
                       latex=_latex(L))
    elif operation == "det":
        d = M.det()
        return _result("行列式", input=str(M), det=str(d), latex=_latex(d))
    elif operation == "kernel":
        K = M.kernel()
        return _result("核", input=str(M), kernel_basis=str(K.basis()),
                       dimension=str(K.dimension()))
    else:
        return _result("错误", error=f"未知运算: {operation}")


# ===========================================================================
# Symbolic Integration (SageMath-powered)
# ===========================================================================

@math_tool(category="sage_analysis", description="SageMath 符号积分，支持含参数的复杂积分、assumptions（整数/正数/偶数等）。当 SymPy 的 integrate 无法处理时使用此工具")
def sage_integrate(expr: str, variable: str = "x", lower: str = "", upper: str = "",
                   assumptions: str = "", timeout: int = 30) -> str:
    """使用 SageMath 计算积分，支持符号参数和 assumptions。

    当 SymPy 的 integrate 工具无法处理含符号参数的复杂积分时，使用此工具。
    如果一般符号积分不可行，会自动尝试枚举具体参数值来发现规律。

    Args:
        expr: 被积函数表达式，例如 'sin(theta)**(2*s-1) * cos(n*theta)'
        variable: 积分变量，默认 'x'
        lower: 定积分下限（留空=不定积分），例如 '0'
        upper: 定积分上限，例如 'pi/2'
        assumptions: 变量的假设条件，用分号分隔，例如 's: integer, positive; n: integer, even'。支持的属性: integer, positive, negative, even, odd, real, nonnegative
        timeout: 符号积分超时秒数，默认 30
    """
    sa = _sage()
    import signal

    # Parse assumptions and declare variables
    all_vars = {}

    # Always declare the integration variable
    all_vars[variable] = sa.var(variable)

    # Parse assumption string
    assumption_map = {}
    if assumptions:
        for part in assumptions.split(";"):
            part = part.strip()
            if ":" not in part:
                continue
            var_name, attrs = part.split(":", 1)
            var_name = var_name.strip()
            attr_list = [a.strip() for a in attrs.split(",")]
            v = sa.var(var_name)
            all_vars[var_name] = v
            assumption_map[var_name] = attr_list

            for attr in attr_list:
                if attr == "integer":
                    sa.assume(v, "integer")
                elif attr == "positive":
                    sa.assume(v > 0)
                elif attr == "negative":
                    sa.assume(v < 0)
                elif attr == "nonnegative":
                    sa.assume(v >= 0)
                elif attr == "even":
                    sa.assume(v, "integer")
                    # Sage doesn't have direct "even" — we note it for enumeration
                elif attr == "odd":
                    sa.assume(v, "integer")
                elif attr == "real":
                    sa.assume(v, "real")

    # Parse expression in Sage
    try:
        integrand = sa.sage_eval(expr, locals=all_vars)
    except Exception as e:
        return _result("表达式解析错误", expr=expr, error=str(e))

    var_sym = all_vars[variable]

    # --- Attempt 1: Direct symbolic integration with timeout ---
    symbolic_result = None

    class TimeoutError(Exception):
        pass

    def _timeout_handler(signum, frame):
        raise TimeoutError("超时")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    try:
        signal.alarm(timeout)
        if lower and upper:
            lo = sa.sage_eval(lower, locals=all_vars)
            hi = sa.sage_eval(upper, locals=all_vars)
            symbolic_result = sa.integrate(integrand, var_sym, lo, hi)
        else:
            symbolic_result = sa.integrate(integrand, var_sym)
        signal.alarm(0)
    except TimeoutError:
        symbolic_result = None
    except Exception:
        symbolic_result = None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    if symbolic_result is not None:
        # Clean up assumptions
        try:
            sa.forget()
        except Exception:
            pass
        simplified = sa.simplify(symbolic_result)
        return _result(
            "SageMath 符号积分",
            input=expr,
            variable=variable,
            bounds=f"[{lower}, {upper}]" if lower else "不定积分",
            assumptions=assumptions,
            output=str(simplified),
            latex=_latex(simplified),
        )

    # --- Attempt 2: Enumerate specific parameter values to find pattern ---
    # Identify free parameters (variables other than the integration variable)
    free_params = sorted(set(all_vars.keys()) - {variable})

    if not free_params or not (lower and upper):
        try:
            sa.forget()
        except Exception:
            pass
        return _result("积分计算", input=expr, error="符号积分超时且无自由参数可枚举",
                       hint="请尝试使用 sage_eval 手动编写计算代码，或代入具体数值")

    # Build enumeration ranges based on assumptions
    def _param_range(pname):
        attrs = assumption_map.get(pname, [])
        if "even" in attrs:
            return [0, 2, 4, 6, 8]
        elif "odd" in attrs:
            return [1, 3, 5, 7, 9]
        elif "positive" in attrs:
            return [1, 2, 3, 4, 5, 6]
        elif "nonnegative" in attrs:
            return [0, 1, 2, 3, 4, 5]
        else:
            return [0, 1, 2, 3, 4, 5]

    results_table = []
    lo = sa.sage_eval(lower, locals=all_vars)
    hi = sa.sage_eval(upper, locals=all_vars)

    if len(free_params) == 1:
        p = free_params[0]
        for pval in _param_range(p):
            try:
                f_sub = integrand.subs({all_vars[p]: pval})
                r = sa.integrate(f_sub, var_sym, lo, hi)
                r_simplified = sa.simplify(r)
                results_table.append({p: pval, "result": str(r_simplified), "latex": _latex(r_simplified)})
            except Exception:
                results_table.append({p: pval, "result": "计算失败"})

    elif len(free_params) == 2:
        p1, p2 = free_params
        for pval1 in _param_range(p1)[:5]:
            for pval2 in _param_range(p2)[:5]:
                # Skip invalid combinations (e.g. s must be > n/2 for convergence)
                try:
                    f_sub = integrand.subs({all_vars[p1]: pval1, all_vars[p2]: pval2})
                    r = sa.integrate(f_sub, var_sym, lo, hi)
                    r_simplified = sa.simplify(r)
                    results_table.append({
                        p1: pval1, p2: pval2,
                        "result": str(r_simplified),
                        "latex": _latex(r_simplified),
                    })
                except Exception:
                    results_table.append({p1: pval1, p2: pval2, "result": "计算失败/发散"})
    else:
        # 3+ parameters: just give first param range
        try:
            sa.forget()
        except Exception:
            pass
        return _result("积分计算", input=expr,
                       error="参数过多，请减少自由参数或使用 sage_eval 手动计算")

    # Clean up assumptions
    try:
        sa.forget()
    except Exception:
        pass

    return _result(
        "符号积分（枚举参数值）",
        input=expr,
        variable=variable,
        bounds=f"[{lower}, {upper}]",
        assumptions=assumptions,
        note="一般符号积分超时，已自动枚举具体参数值。请根据这些数据推导一般公式。",
        enumeration=json.dumps(results_table, ensure_ascii=False, default=str),
    )


# ===========================================================================
# Symbolic Simplify / Manipulation (SageMath-powered)
# ===========================================================================

@math_tool(category="sage_analysis", description="SageMath 符号化简/展开/因式分解，支持 assumptions 和高级化简策略")
def sage_simplify(expr: str, operation: str = "simplify", assumptions: str = "") -> str:
    """使用 SageMath 进行符号运算。

    Args:
        expr: 数学表达式，例如 'gamma(n+1)/gamma(n)' 或 'binomial(2*n, n)'
        operation: 运算: simplify(化简), expand(展开), factor(分解), full_simplify(深度化简), canonicalize_radical(根式标准化)
        assumptions: 变量假设，例如 'n: integer, positive'
    """
    sa = _sage()
    all_vars = {}

    if assumptions:
        for part in assumptions.split(";"):
            part = part.strip()
            if ":" not in part:
                continue
            var_name, attrs = part.split(":", 1)
            var_name = var_name.strip()
            v = sa.var(var_name)
            all_vars[var_name] = v
            for attr in [a.strip() for a in attrs.split(",")]:
                if attr == "integer":
                    sa.assume(v, "integer")
                elif attr == "positive":
                    sa.assume(v > 0)
                elif attr == "nonnegative":
                    sa.assume(v >= 0)
                elif attr == "real":
                    sa.assume(v, "real")

    try:
        e = sa.sage_eval(expr, locals=all_vars)
    except Exception as ex:
        try:
            sa.forget()
        except Exception:
            pass
        return _result("表达式解析错误", expr=expr, error=str(ex))

    ops = {
        "simplify": lambda: sa.simplify(e),
        "expand": lambda: e.expand(),
        "factor": lambda: e.factor(),
        "full_simplify": lambda: e.full_simplify(),
        "canonicalize_radical": lambda: e.canonicalize_radical(),
    }

    if operation not in ops:
        try:
            sa.forget()
        except Exception:
            pass
        return _result("错误", error=f"未知运算: {operation}")

    result = ops[operation]()

    try:
        sa.forget()
    except Exception:
        pass

    return _result(
        f"SageMath {operation}",
        input=expr,
        assumptions=assumptions,
        output=str(result),
        latex=_latex(result),
    )


# ===========================================================================
# General Sage Evaluator (power tool)
# ===========================================================================

@math_tool(category="sage_general", description="直接执行 SageMath 代码，用于上述工具未覆盖的高级运算（万能工具）。支持多行代码，最后一行作为返回值")
def sage_eval(code: str) -> str:
    """直接执行一段 SageMath 代码并返回结果。

    Args:
        code: SageMath 代码。多行代码中最后一行的值作为结果返回。可以使用 var() 声明变量，assume() 添加假设。例如: 'var("n"); assume(n, "integer"); sum(1/factorial(n), n, 0, 10)' 或 'E = EllipticCurve("11a1"); E.rank()'
    """
    sa = _sage()

    # Build a safe namespace with common Sage objects
    namespace = {k: getattr(sa, k) for k in dir(sa) if not k.startswith('_')}
    namespace['sa'] = sa
    # Pre-declare common variable names (skip Python keywords and Sage builtins)
    _python_keywords = {"lambda", "gamma", "beta", "sum", "max", "min", "map", "filter", "range", "type", "print", "var", "set", "list", "int", "float"}
    for vname in "x y z t a b c n m k s p q r theta phi psi alpha delta epsilon mu sigma rho tau omega".split():
        if vname not in _python_keywords and (vname not in namespace or not callable(namespace.get(vname))):
            namespace[vname] = sa.var(vname)

    try:
        lines = code.strip().split("\n")
        # Execute all lines
        if len(lines) == 1:
            # Single line — try eval first
            stripped = code.strip()
            # Check if it's an assignment
            first_eq = None
            depth = 0
            for i, ch in enumerate(stripped):
                if ch in '([{':
                    depth += 1
                elif ch in ')]}':
                    depth -= 1
                elif ch == '=' and depth == 0 and i > 0 and stripped[i-1] not in '<>!=' and (i+1 >= len(stripped) or stripped[i+1] != '='):
                    first_eq = i
                    break

            if first_eq is None:
                result = eval(compile(stripped, '<sage_eval>', 'eval'), namespace)
            else:
                exec(compile(stripped, '<sage_eval>', 'exec'), namespace)
                var_name = stripped[:first_eq].strip()
                result = namespace.get(var_name, "Done")
        else:
            # Multi-line: exec all but last, eval last
            for line in lines[:-1]:
                line_s = line.strip()
                if line_s and not line_s.startswith("#"):
                    exec(compile(line_s, '<sage_eval>', 'exec'), namespace)

            eval_line = lines[-1].strip()
            if not eval_line or eval_line.startswith("#"):
                result = "Done"
            else:
                # Check if last line is assignment
                first_eq = None
                depth = 0
                for i, ch in enumerate(eval_line):
                    if ch in '([{':
                        depth += 1
                    elif ch in ')]}':
                        depth -= 1
                    elif ch == '=' and depth == 0 and i > 0 and eval_line[i-1] not in '<>!=' and (i+1 >= len(eval_line) or eval_line[i+1] != '='):
                        first_eq = i
                        break

                if first_eq is not None:
                    exec(compile(eval_line, '<sage_eval>', 'exec'), namespace)
                    var_name = eval_line[:first_eq].strip()
                    result = namespace.get(var_name, "Done")
                else:
                    result = eval(compile(eval_line, '<sage_eval>', 'eval'), namespace)

        result_str = str(result)
        latex_str = ""
        try:
            latex_str = _latex(result)
        except Exception:
            pass

        return _result("SageMath 执行结果", code=code, output=result_str, latex=latex_str)

    except Exception as e:
        import traceback
        return _result("SageMath 执行错误", code=code, error=str(e),
                       traceback=traceback.format_exc().split('\n')[-3])
