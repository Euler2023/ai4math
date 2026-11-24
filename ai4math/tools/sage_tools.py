"""Advanced mathematics tools powered by SageMath.

Covers: Galois theory, number fields, elliptic curves, Groebner bases,
homological algebra, advanced group theory, combinatorics, number theory, etc.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import traceback
from typing import Any

from ai4math.tools._shared import format_result, safe_literal_eval, split_top_level
from ai4math.tools.registry import math_tool


def _sage():
    """Lazy import sage.all to avoid slow startup when not needed."""
    import sage.all as sa
    return sa


def _result(title: str, **kwargs) -> str:
    return format_result(title, **kwargs)


def _latex(obj) -> str:
    """Get LaTeX representation of a Sage object."""
    sa = _sage()
    try:
        return sa.latex(obj)
    except Exception:
        return str(obj)


def _short_traceback() -> str:
    lines = [ln.strip() for ln in traceback.format_exc().strip().splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _parse_sage_ring(ring: str):
    """Parse ring spec like 'QQ', 'RR', 'ZZ', 'GF(7)', or 'GF(2^3)'."""
    sa = _sage()
    r = ring.strip()
    if r == "QQ":
        return sa.QQ
    if r == "RR":
        return sa.RR
    if r == "ZZ":
        return sa.ZZ
    if r.startswith("GF(") and r.endswith(")"):
        inner = r[3:-1].strip()
        q = int(sa.sage_eval(inner))
        return sa.GF(q, "a") if not sa.ZZ(q).is_prime() else sa.GF(q)
    return sa.QQ


def _make_sage_namespace(extra_vars: str = "x y z t a b c n m k s p q r theta phi psi alpha delta epsilon mu sigma rho tau omega") -> dict[str, Any]:
    """Create a Sage execution namespace with common symbolic variables pre-declared.

    Note: This is an execution convenience namespace, NOT a security sandbox.
    Process and credential isolation is enforced by ``sage_subprocess.py``.
    """
    sa = _sage()
    namespace = {k: getattr(sa, k) for k in dir(sa) if not k.startswith("_")}
    namespace["sa"] = sa
    skip = {
        "lambda", "gamma", "beta", "sum", "max", "min", "map", "filter",
        "range", "type", "print", "var", "set", "list", "int", "float",
    }
    for vname in extra_vars.split():
        if vname not in skip and (vname not in namespace or not callable(namespace.get(vname))):
            namespace[vname] = sa.var(vname)
    return namespace


def _run_sage_code(code: str, namespace: dict[str, Any], label: str = "<sage_eval>") -> tuple[Any, str]:
    """Preparse and compile a full SageMath code block, returning ``(last_value, captured_stdout)``."""
    sa = _sage()
    stripped = code.strip()
    if not stripped:
        return "Done", ""

    parsed = sa.preparse(stripped)
    tree = ast.parse(parsed, label, mode="exec")
    if not tree.body:
        return "Done", ""

    last_expr = None
    last_assign_target = None
    if isinstance(tree.body[-1], ast.Expr):
        last_expr = ast.Expression(tree.body.pop().value)
    elif (
        isinstance(tree.body[-1], ast.Assign)
        and len(tree.body[-1].targets) == 1
        and isinstance(tree.body[-1].targets[0], ast.Name)
    ):
        last_assign_target = tree.body[-1].targets[0].id

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        if tree.body:
            exec(compile(tree, label, "exec"), namespace)
        if last_expr is not None:
            result = eval(compile(last_expr, label, "eval"), namespace)
        elif last_assign_target is not None:
            result = namespace.get(last_assign_target, "Done")
        else:
            result = "Done"

    return result, captured.getvalue()


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
        return _result("模逆元", input=f"{a} mod {m}", result=str(result), output=str(result),
                       latex=f"{a}^{{-1}} \\equiv {result} \\pmod{{{m}}}")

    if operation == "crt":
        parts = n.split(";")
        remainders = [sa.ZZ(x.strip()) for x in parts[0].split(",")]
        moduli = [sa.ZZ(x.strip()) for x in parts[1].split(",")]
        result = sa.crt(remainders, moduli)
        mod_product = sa.prod(moduli)
        return _result("中国剩余定理", remainders=str(remainders), moduli=str(moduli),
                       result=str(result), output=str(result),
                       latex=f"x \\equiv {result} \\pmod{{{mod_product}}}")

    val = sa.ZZ(sa.sage_eval(n))

    if operation == "factor":
        f = val.factor()
        return _result("整数因式分解", input=str(val), factorization=str(f), output=str(f), latex=_latex(f))
    elif operation == "is_prime":
        ans = str(val.is_prime())
        return _result("素性检验", input=str(val), is_prime=ans, output=ans)
    elif operation == "euler_phi":
        phi = sa.euler_phi(val)
        return _result("欧拉函数", input=str(val), euler_phi=str(phi), output=str(phi),
                       latex=f"\\varphi({val}) = {phi}")
    elif operation == "divisors":
        divs = val.divisors()
        return _result("因子列表", input=str(val), divisors=str(divs),
                       num_divisors=str(len(divs)), output=str(divs))
    elif operation == "next_prime":
        p = sa.next_prime(val)
        return _result("下一个素数", input=str(val), next_prime=str(p), output=str(p))
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
    F = sa.GF(p**n, "a") if n > 1 else sa.GF(p)
    R = sa.PolynomialRing(F, "x")
    x = R.gen()

    polys = [sa.sage_eval(s.strip(), locals={"x": x}) for s in expr.split(";") if s.strip()]
    field_name = f"GF({p})" if n == 1 else f"GF({p}^{n})"

    if operation == "factor":
        f = polys[0].factor()
        return _result(f"{field_name} 上因式分解", input=expr, factorization=str(f), output=str(f), latex=_latex(f))
    elif operation == "roots":
        roots = polys[0].roots()
        roots_str = str([(str(r), int(m)) for r, m in roots])
        return _result(f"{field_name} 上求根", input=expr, roots=roots_str, output=roots_str)
    elif operation == "irreducible_check":
        is_irr = str(polys[0].is_irreducible())
        return _result(f"{field_name} 上不可约检验", input=expr, is_irreducible=is_irr, output=is_irr)
    elif operation == "gcd":
        if len(polys) < 2:
            return _result("错误", error="GCD 需要两个多项式，用分号分隔")
        g = sa.gcd(polys[0], polys[1])
        return _result(f"{field_name} 上 GCD", input=expr, gcd=str(g), output=str(g), latex=_latex(g))
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
    base = _parse_sage_ring(ring)

    var_names = ",".join(v.strip() for v in variables.split(",") if v.strip())
    R = sa.PolynomialRing(base, var_names, order=order)
    gens = R.gens()
    local_vars = {str(g): g for g in gens}

    polys = [sa.sage_eval(s.strip(), locals=local_vars) for s in polynomials.split(";") if s.strip()]
    I = R.ideal(polys)
    gb = list(I.groebner_basis())

    return _result(
        "Groebner 基",
        ring=f"{ring}[{var_names}]",
        order=order,
        input_generators=str(polys),
        groebner_basis=str(gb),
        output=str(gb),
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
    base = _parse_sage_ring(ring)

    var_names = ",".join(v.strip() for v in variables.split(",") if v.strip())
    R = sa.PolynomialRing(base, var_names, order="degrevlex")
    gens = R.gens()
    local_vars = {str(g): g for g in gens}

    f = sa.sage_eval(polynomial.strip(), locals=local_vars)
    gen_polys = [sa.sage_eval(s.strip(), locals=local_vars) for s in generators.split(";") if s.strip()]
    I = R.ideal(gen_polys)

    result = str(f in I)
    return _result("理想成员检验", polynomial=str(f), ideal_generators=str(gen_polys),
                   is_member=result, output=result)


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
    R = sa.PolynomialRing(sa.QQ, "x")
    x = R.gen()
    f = sa.sage_eval(poly, locals={"x": x})

    K = sa.NumberField(f, name)
    info = {
        "title": "数域性质",
        "数域": str(K),
        "次数": str(K.degree()),
        "判别式": str(K.discriminant()),
        "签名 (r1, r2)": str(K.signature()),
        "整数环": str(K.ring_of_integers()),
        "整数环基": str(K.ring_of_integers().basis()),
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
    R = sa.PolynomialRing(sa.QQ, "x")
    x = R.gen()
    f = sa.sage_eval(poly, locals={"x": x})

    G_pari = f.galois_group(pari_group=True)
    order_val = G_pari.order()
    structure_desc = ""
    is_abelian_str = ""
    try:
        if f.is_irreducible() and f.degree() <= 11:
            K = sa.NumberField(f, "a")
            G_perm = K.galois_group()
            structure_desc = G_perm.structure_description()
            is_abelian_str = str(G_perm.is_abelian())
    except Exception:
        pass

    pari_label = ""
    try:
        pari_label = str(G_pari.label())
    except Exception:
        pari_label = str(G_pari)

    group_tex_name = structure_desc or pari_label
    clean_latex = f"\\operatorname{{Gal}}(f) \\cong \\text{{{group_tex_name}}} \\quad (|G| = {order_val})"

    extra = {}
    if structure_desc:
        extra["structure"] = structure_desc
    if is_abelian_str:
        extra["is_abelian"] = is_abelian_str

    return _result(
        "Galois 群",
        polynomial=poly,
        galois_group=str(G_pari),
        order=str(order_val),
        output=f"{structure_desc or G_pari} (order {order_val})",
        latex=clean_latex,
        **extra,
    )


@math_tool(category="sage_algebra", description="多项式的高阶 Galois 群验证（适用于高次 n>11 的多项式）。利用 Chebotarev 密度定理和判别式过滤，突破传统计算瓶颈。")
def galois_group_chebotarev(poly: str, max_primes: int = 10000) -> str:
    """基于 Chebotarev 密度的 Galois 群统计推断。

    Args:
        poly: 待求 Galois 群的多项式（如 'x**22 + x + 1'）
        max_primes: 用于采样的素数上界，默认 10000
    """
    sa = _sage()
    import time
    from collections import Counter

    ncpus = max(1, min(int(os.environ.get("AI4MATH_SAGE_WORKERS", "4")), os.cpu_count() or 2))

    R = sa.PolynomialRing(sa.QQ, "x")
    x = R.gen()
    try:
        f = sa.sage_eval(poly, locals={"x": x})
    except Exception as e:
        return _result("表达式错误", error=str(e))

    degree = f.degree()
    if degree > 30:
        return _result("暂不支持", error="目前实现仅支持较低次数多项式（建议 degree <= 30）的传递群枚举，因为群数量增长过快。")

    Zx = sa.PolynomialRing(sa.ZZ, "t")
    f_int = Zx(f)

    if not f_int.is_irreducible():
        return _result("分析结果", note="多项式在有理数域上可约，伽罗瓦群不是全置换群的传递子群。请先因式分解。")

    lc = f_int.leading_coefficient()

    @sa.parallel(ncpus=ncpus)
    def frobenius_cycle_type(p):
        try:
            Fp = sa.GF(p)
            Fpx = sa.PolynomialRing(Fp, "u")
            fp = Fpx([sa.ZZ(c) % p for c in f_int.list()])
            if fp.degree() < degree:
                return (p, None, "bad")
            if fp.gcd(fp.derivative()) != 1:
                return (p, None, "ramified")
            facs = fp.factor()
            degs = tuple(sorted([g.degree() for g, e in facs]))
            return (p, degs, "ok")
        except Exception as ex:
            return (p, None, str(ex))

    test_primes = [p for p in sa.primes(3, max_primes) if lc % p != 0]

    t0 = time.time()
    results = list(frobenius_cycle_type(test_primes))
    elapsed_frob = time.time() - t0

    frob_counter = Counter()
    for inp, out in results:
        p_val, degs, status = out
        if status == "ok":
            frob_counter[degs] += 1

    observed_types = set(frob_counter.keys())
    valid_observed = set(ct for ct in observed_types if sum(ct) == degree)

    is_sq = False
    try:
        f_monic = f / lc
        K = sa.NumberField(f_monic, "a")
        disc = K.discriminant()
        d = sa.ZZ(disc)
        if d > 0:
            sqrt_d = d.isqrt()
            is_sq = sqrt_d * sqrt_d == d
    except Exception:
        disc_poly = f_int.discriminant()
        kr_signs = [sa.kronecker_symbol(disc_poly, p) for p in sa.primes(3, 1000) if disc_poly % p != 0]
        is_sq = all(k == 1 for k in kr_signs)

    try:
        gap_cmd = sa.gap
        nr = int(gap_cmd.eval(f"NrTransitiveGroups({degree})"))
    except Exception:
        return _result("系统依赖错误", error="未找到对应次数的 GAP 传递群数据库，可能需要安装 'transgrp' package。")

    @sa.parallel(ncpus=ncpus)
    def check_transitive_group(k):
        try:
            G = sa.TransitiveGroup(degree, k)
            g_cycle_types = set()
            for cc in G.conjugacy_classes():
                rep = cc.representative()
                ct = tuple(sorted(rep.cycle_type()))
                g_cycle_types.add(ct)

            is_compat = valid_observed.issubset(g_cycle_types)
            if is_compat:
                return (k, True, G.order(), G.structure_description(), len(g_cycle_types))
            else:
                return (k, False, 0, "", 0)
        except Exception:
            return (k, None, 0, "", 0)

    t1 = time.time()
    enum_results = list(check_transitive_group(list(range(1, nr + 1))))
    elapsed_enum = time.time() - t1

    compatible_groups = []
    for inp, out in enum_results:
        k, is_compat, g_order, g_name, n_ct = out
        if is_compat:
            try:
                G_temp = sa.TransitiveGroup(degree, k)
                in_A = G_temp.is_subgroup(sa.AlternatingGroup(degree))
                if is_sq and not in_A:
                    continue
                if not is_sq and in_A:
                    continue
            except Exception:
                pass
            compatible_groups.append({"id": int(k), "name": str(g_name), "order": int(g_order), "cycle_types_count": int(n_ct)})

    compatible_groups.sort(key=lambda g: abs(g["cycle_types_count"] - len(valid_observed)))

    return _result(
        "Galois 群统计推断结果",
        degree=degree,
        is_discriminant_square=is_sq,
        primes_tested=sum(frob_counter.values()),
        observed_cycle_types_count=len(valid_observed),
        compatible_groups_found=len(compatible_groups),
        top_candidates=json.dumps(compatible_groups[:5], ensure_ascii=False, default=str),
        time_frobenius=f"{elapsed_frob:.2f}s",
        time_enum=f"{elapsed_enum:.2f}s",
        note="返回了最符合观测分布的候选群列表（按循环型数量的贴合度排序），排在最前的通常是真实的 Galois 群。",
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
    K = _parse_sage_ring(base_field)

    try:
        if a_invariants.replace(" ", "").isalnum():
            E = sa.EllipticCurve(a_invariants.strip())
        else:
            coeffs = safe_literal_eval(a_invariants)
            E = sa.EllipticCurve(K, coeffs)
    except Exception:
        coeffs = safe_literal_eval(a_invariants)
        E = sa.EllipticCurve(K, coeffs)

    info: dict[str, str] = {
        "title": "椭圆曲线性质",
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
        operation: 运算: info(基本信息), center(中心), commutator(换位子群), sylow(Sylow子群), normal_subgroups(正规子群), conjugacy_classes(共轭类), character_table(特征标表)
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
                       center_generators=str(Z.gens()), output=f"{Z} (order {Z.order()})")
    elif operation == "commutator":
        D = G.commutator()
        return _result("换位子群 [G,G]", group=str(G), commutator=str(D),
                       order=str(D.order()), index=str(G.order() // D.order()),
                       output=f"{D} (order {D.order()})")
    elif operation == "sylow":
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
                       normal_subgroups=str(ns_info), output=str(ns_info))
    elif operation == "conjugacy_classes":
        cc = G.conjugacy_classes()
        cc_info = [f"代表元 {c.representative()}, 大小 {c.cardinality()}" for c in cc]
        return _result("共轭类", group=str(G), num_classes=str(len(cc)),
                       classes=str(cc_info), output=f"共 {len(cc)} 个共轭类")
    elif operation == "character_table":
        ct = G.character_table()
        return _result("特征标表", group=str(G), character_table=str(ct),
                       output=str(ct), latex=_latex(ct))
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
        return _result("整数分拆数", n=str(val), p_n=str(count), output=str(count),
                       latex=f"p({val}) = {count}")
    elif operation == "partition_list":
        val = sa.ZZ(parts[0])
        ps = list(sa.Partitions(val))
        return _result("整数分拆列表", n=str(val), count=str(len(ps)),
                       partitions=str(ps[:50]) + ("..." if len(ps) > 50 else ""),
                       output=f"count={len(ps)}")
    elif operation == "catalan":
        val = sa.ZZ(parts[0])
        c = sa.catalan_number(val)
        return _result("Catalan 数", n=str(val), catalan=str(c), output=str(c),
                       latex=f"C_{{{val}}} = {c}")
    elif operation == "stirling1":
        nn, k = sa.ZZ(parts[0]), sa.ZZ(parts[1])
        s = sa.stirling_number1(nn, k)
        return _result("第一类 Stirling 数", n=str(nn), k=str(k), result=str(s), output=str(s),
                       latex=f"s({nn},{k}) = {s}")
    elif operation == "stirling2":
        nn, k = sa.ZZ(parts[0]), sa.ZZ(parts[1])
        s = sa.stirling_number2(nn, k)
        return _result("第二类 Stirling 数", n=str(nn), k=str(k), result=str(s), output=str(s),
                       latex=f"S({nn},{k}) = {s}")
    elif operation == "bell":
        val = sa.ZZ(parts[0])
        b = sa.bell_number(val)
        return _result("Bell 数", n=str(val), bell=str(b), output=str(b),
                       latex=f"B_{{{val}}} = {b}")
    elif operation == "binomial":
        nn, k = sa.ZZ(parts[0]), sa.ZZ(parts[1])
        b = sa.binomial(nn, k)
        return _result("二项式系数", n=str(nn), k=str(k), result=str(b), output=str(b),
                       latex=f"\\binom{{{nn}}}{{{k}}} = {b}")
    elif operation == "fibonacci":
        val = sa.ZZ(parts[0])
        f = sa.fibonacci(val)
        return _result("Fibonacci 数", n=str(val), fibonacci=str(f), output=str(f),
                       latex=f"F_{{{val}}} = {f}")
    elif operation == "bernoulli":
        val = sa.ZZ(parts[0])
        b = sa.bernoulli(val)
        return _result("Bernoulli 数", n=str(val), bernoulli=str(b), output=str(b),
                       latex=f"B_{{{val}}} = {_latex(b)}")
    elif operation == "generating_function":
        val = sa.ZZ(parts[0])
        R = sa.PowerSeriesRing(sa.ZZ, "q", default_prec=val + 1)
        q = R.gen()
        gf = sa.prod(1 / (1 - q**i) for i in range(1, val + 1))
        return _result("分拆生成函数", precision=str(val),
                       series=str(gf), output=str(gf),
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
    data = safe_literal_eval(matrix)
    M = sa.matrix(sa.ZZ, data)

    if operation == "smith_form":
        D, U, V = M.smith_form()
        return _result("Smith 标准形", input=str(M), smith_form=str(D),
                       invariant_factors=str(D.diagonal()), output=str(D),
                       latex=_latex(D))
    elif operation == "hermite_form":
        H = M.hermite_form()
        return _result("Hermite 标准形", input=str(M), hermite_form=str(H), output=str(H),
                       latex=_latex(H))
    elif operation == "lll":
        L = M.LLL()
        return _result("LLL 格基约化", input=str(M), reduced_basis=str(L), output=str(L),
                       latex=_latex(L))
    elif operation == "det":
        d = M.det()
        return _result("行列式", input=str(M), det=str(d), output=str(d), latex=_latex(d))
    elif operation == "kernel":
        K = M.kernel()
        return _result("核", input=str(M), kernel_basis=str(K.basis()),
                       dimension=str(K.dimension()), output=str(K.basis()))
    else:
        return _result("错误", error=f"未知运算: {operation}")


# ===========================================================================
# Symbolic Integration (SageMath-powered)
# ===========================================================================

@math_tool(category="sage_analysis", description="SageMath 符号积分，支持含参数的复杂积分、assumptions（整数/正数/偶数等）。当 SymPy 的 integrate 无法处理时使用此工具")
def sage_integrate(expr: str, variable: str = "x", lower: str = "", upper: str = "",
                   assumptions: str = "", timeout: int = 30) -> str:
    """使用 SageMath 计算积分，支持符号参数和 assumptions。

    Args:
        expr: 被积函数表达式，例如 'sin(theta)**(2*s-1) * cos(n*theta)'
        variable: 积分变量，默认 'x'
        lower: 定积分下限（留空=不定积分），例如 '0'
        upper: 定积分上限，例如 'pi/2'
        assumptions: 变量的假设条件，用分号分隔，例如 's: integer, positive; n: integer, even'
        timeout: 符号积分超时秒数，默认 30
    """
    has_lo = bool(lower.strip())
    has_hi = bool(upper.strip())
    if has_lo != has_hi:
        return _result("参数错误", error="定积分必须同时提供下限 lower 和上限 upper；不定积分请将两者均留空")

    sa = _sage()
    import signal

    all_vars = {variable: sa.var(variable)}
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
                elif attr in ("even", "odd"):
                    sa.assume(v, "integer")
                elif attr == "real":
                    sa.assume(v, "real")

    try:
        integrand = sa.sage_eval(expr, locals=all_vars)
    except Exception as e:
        try:
            sa.forget()
        except Exception:
            pass
        return _result("表达式解析错误", expr=expr, error=str(e))

    var_sym = all_vars[variable]
    symbolic_result = None

    class _IntegralTimeout(Exception):
        pass

    def _timeout_handler(signum, frame):
        raise _IntegralTimeout("超时")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    try:
        signal.alarm(max(1, int(timeout)))
        if has_lo and has_hi:
            lo = sa.sage_eval(lower, locals=all_vars)
            hi = sa.sage_eval(upper, locals=all_vars)
            symbolic_result = sa.integrate(integrand, var_sym, lo, hi)
        else:
            symbolic_result = sa.integrate(integrand, var_sym)
        signal.alarm(0)
    except _IntegralTimeout:
        symbolic_result = None
    except Exception:
        symbolic_result = None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    if symbolic_result is not None:
        try:
            sa.forget()
        except Exception:
            pass
        simplified = sa.simplify(symbolic_result)
        return _result(
            "SageMath 符号积分",
            input=expr,
            variable=variable,
            bounds=f"[{lower}, {upper}]" if has_lo else "不定积分",
            assumptions=assumptions,
            output=str(simplified),
            latex=_latex(simplified),
        )

    free_params = sorted(set(all_vars.keys()) - {variable})
    if not free_params or not (has_lo and has_hi):
        try:
            sa.forget()
        except Exception:
            pass
        return _result("积分计算", input=expr, error="符号积分超时且无自由参数可枚举",
                       hint="请尝试使用 sage_eval 手动编写计算代码，或代入具体数值")

    def _param_range(pname):
        attrs = assumption_map.get(pname, [])
        if "even" in attrs:
            return [0, 2, 4, 6, 8]
        elif "odd" in attrs:
            return [1, 3, 5, 7, 9]
        elif "positive" in attrs:
            return [1, 2, 3, 4, 5, 6]
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
        try:
            sa.forget()
        except Exception:
            pass
        return _result("积分计算", input=expr,
                       error="参数过多，请减少自由参数或使用 sage_eval 手动计算")

    try:
        sa.forget()
    except Exception:
        pass

    summary_lines = [
        ", ".join(f"{k}={v}" for k, v in row.items() if k != "latex")
        for row in results_table
    ]
    return _result(
        "符号积分（枚举参数值）",
        input=expr,
        variable=variable,
        bounds=f"[{lower}, {upper}]",
        assumptions=assumptions,
        note="一般符号积分超时，已自动枚举具体参数值。请根据这些数据推导一般公式。",
        enumeration=json.dumps(results_table, ensure_ascii=False, default=str),
        output="\n".join(summary_lines),
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
    for vname in "x y z t a b c n m k s p q r theta phi psi alpha delta epsilon mu sigma rho tau omega".split():
        all_vars[vname] = sa.var(vname)

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
        "simplify": lambda: e.simplify_full() if hasattr(e, "simplify_full") else sa.simplify(e),
        "expand": lambda: e.expand(),
        "factor": lambda: e.factor(),
        "full_simplify": lambda: e.simplify_full() if hasattr(e, "simplify_full") else e.full_simplify(),
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

@math_tool(category="sage_general", description="直接执行 SageMath 代码，用于上述工具未覆盖的高级运算（万能工具）。支持多行代码，最后一个表达式作为返回值")
def sage_eval(code: str) -> str:
    """直接执行一段 SageMath 代码并返回结果。

    Args:
        code: SageMath 代码。支持完整多行控制流（for/if/def）、Sage 语法糖（^, 1/3, R.<x>=QQ[]）和 print 输出，最后一个表达式的值作为结果返回。例如: 'var("n"); assume(n, "integer"); sum(1/factorial(n), n, 0, 10)' 或 'E = EllipticCurve("11a1"); E.rank()'
    """
    namespace = _make_sage_namespace()

    try:
        result, stdout_text = _run_sage_code(code, namespace, label="<sage_eval>")
        stdout_clean = stdout_text.strip()

        if result is None:
            result_str = stdout_clean or "Done"
        elif result == "Done" and stdout_clean:
            result_str = stdout_clean
        else:
            result_str = str(result)

        latex_str = ""
        if result is not None and result != "Done":
            try:
                latex_str = _latex(result)
            except Exception:
                pass

        extra = {}
        if stdout_clean:
            extra["stdout"] = stdout_clean

        return _result("SageMath 执行结果", code=code, output=result_str, latex=latex_str, **extra)

    except Exception as e:
        return _result("SageMath 执行错误", code=code, error=str(e), traceback=_short_traceback())


# ===========================================================================
# Proof-support tools
# ===========================================================================

@math_tool(category="sage_proof", description="批量验证数学猜想：给定 SageMath 谓词代码和参数范围，测试所有情况并返回通过/反例")
def verify_conjecture(predicate_code: str, param_name: str = "p", param_range: str = "prime_range(3, 200)") -> str:
    """批量验证一个数学猜想。

    Args:
        predicate_code: 返回 True/False 的 SageMath 代码片段，可引用参数变量。例如 'is_prime(p) and pow(2, p-1, p) == 1'
        param_name: 迭代变量名，默认 'p'
        param_range: 参数范围的 SageMath 表达式，默认 'prime_range(3, 200)'。也可以是 'range(1, 100)' 或 '[2,3,5,7,11]'
    """
    sa = _sage()
    namespace = _make_sage_namespace("")

    try:
        param_values = list(eval(compile(sa.preparse(param_range.strip()), "<verify_range>", "eval"), namespace))
        compiled_pred = compile(sa.preparse(predicate_code.strip()), "<verify_pred>", "eval")
    except Exception as e:
        return _result("验证错误", error=f"无法解析参数范围或谓词表达式: {e}")

    passed = []
    failed = []
    errors = []

    for val in param_values:
        namespace[param_name] = val
        try:
            ok = bool(eval(compiled_pred, namespace))
            if ok:
                passed.append(val)
            else:
                failed.append(val)
        except Exception as e:
            errors.append({"value": str(val), "error": str(e)})

    total = len(param_values)
    if total > 0 and len(errors) == total:
        return _result(
            "验证错误",
            error=f"全部 {total} 个测试值在求值谓词时均出错（示例: {errors[0]['error']}）",
            tested_range=f"{param_name} ∈ {param_range} ({total} values)",
            predicate=predicate_code,
        )

    summary = f"共测试 {total} 个值: {len(passed)} 通过, {len(failed)} 失败"
    if errors:
        summary += f", {len(errors)} 出错"

    info: dict[str, Any] = {"title": "猜想验证", "summary": summary, "output": summary}
    if failed:
        info["counterexamples"] = str(failed[:20])
        info["conclusion"] = f"发现 {len(failed)} 个反例: {failed[:10]}"
    elif errors:
        info["conclusion"] = f"已通过 {len(passed)}/{total} 个值，另有 {len(errors)} 个值求值出错"
    else:
        info["conclusion"] = "所有测试值均满足猜想"
    if errors:
        info["errors"] = json.dumps(errors[:5], ensure_ascii=False, default=str)
    info["tested_range"] = f"{param_name} ∈ {param_range} ({total} values)"
    info["predicate"] = predicate_code
    info["_display_instruction"] = "你必须在回复中展示验证结果，包括测试范围、通过数、反例（如有）"
    return json.dumps(info, ensure_ascii=False, default=str)


@math_tool(category="sage_proof", description="探索与证明相关的代数结构：群结构、类群、分裂类型、二次/高次剩余等，帮助发现证明线索")
def explore_structure(topic: str, params: str = "") -> str:
    """探索与数学证明相关的代数结构。

    Args:
        topic: 探索主题。可选: 'multiplicative_group' (模p乘法群结构), 'quadratic_residues' (二次剩余), 'power_residues' (高次幂剩余), 'class_group' (数域类群), 'splitting' (素数在数域中的分裂), 'representation' (素数表示为二次型)
        params: 参数，格式取决于 topic。例如 topic='multiplicative_group' 时 params='p=17'; topic='power_residues' 时 params='p=17, k=4, a=2'; topic='class_group' 时 params='poly=x^2+1'; topic='splitting' 时 params='poly=x^4-2, primes=[2,3,5,7,11,13,17,19,23]'; topic='representation' 时 params='form=a^2+64*b^2, bound=200'
    """
    sa = _sage()
    namespace = _make_sage_namespace("x y z a b c p q n m k")

    kw: dict[str, Any] = {}
    raw_kw: dict[str, str] = {}
    try:
        if params.strip():
            for part in split_top_level(params, ","):
                if "=" in part:
                    key, val = part.split("=", 1)
                    k_clean = key.strip()
                    v_clean = val.strip()
                    raw_kw[k_clean] = v_clean
                    kw[k_clean] = eval(compile(sa.preparse(v_clean), "<explore>", "eval"), namespace)

        if topic == "multiplicative_group":
            p = int(kw.get("p", 17))
            G = sa.Integers(p)
            gen = G.multiplicative_generator()
            order = int(sa.euler_phi(p))
            subgroups_info = []
            for d in sa.divisors(order):
                d_int = int(d)
                elems = sorted([int(gen ** ((order // d_int) * i)) for i in range(d_int)])
                subgroups_info.append({"order": d_int, "elements": elems[:16]})
            return _result(
                "乘法群结构",
                group=f"(Z/{p}Z)*",
                order=str(order),
                generator=str(gen),
                cyclic="是",
                subgroups=json.dumps(subgroups_info[:12], ensure_ascii=False, default=str),
                latex=f"(\\mathbb{{Z}}/{p}\\mathbb{{Z}})^* \\cong C_{{{order}}}, \\text{{generator}} = {gen}",
            )

        elif topic == "quadratic_residues":
            p = int(kw.get("p", 17))
            qr = sorted(set(int(sa.power_mod(i, 2, p)) for i in range(1, p)))
            qnr = sorted(set(range(1, p)) - set(qr))
            return _result(
                "二次剩余",
                p=str(p),
                quadratic_residues=str(qr),
                quadratic_nonresidues=str(qnr),
                count_qr=str(len(qr)),
                count_qnr=str(len(qnr)),
                output=f"QR({p}) = {qr}",
            )

        elif topic == "power_residues":
            p = int(kw.get("p", 17))
            k_val = int(kw.get("k", 4))
            a_val = int(kw.get("a", 2))
            residues = sorted(set(int(sa.power_mod(i, k_val, p)) for i in range(1, p)))
            is_residue = a_val % p in residues
            solutions = [i for i in range(p) if sa.power_mod(i, k_val, p) == a_val % p]
            order_of_a = sa.Mod(a_val, p).multiplicative_order()
            return _result(
                f"{k_val}次幂剩余分析",
                p=str(p),
                k=str(k_val),
                a=str(a_val),
                is_kth_power_residue=str(is_residue),
                solutions=str(solutions),
                all_kth_power_residues=str(residues),
                count_residues=str(len(residues)),
                order_of_a_mod_p=str(order_of_a),
                group_order=str(p - 1),
                latex=f"x^{{{k_val}}} \\equiv {a_val} \\pmod{{{p}}} \\text{{ solutions: }} {solutions}",
            )

        elif topic == "class_group":
            poly_str = raw_kw.get("poly", str(kw.get("poly", "x^2+1")))
            x_var = sa.polygen(sa.QQ, "x")
            poly = sa.sage_eval(poly_str, locals={"x": x_var})
            K = sa.NumberField(poly, "a")
            cl = K.class_group()
            return _result(
                "类群",
                polynomial=poly_str,
                degree=str(K.degree()),
                discriminant=str(K.discriminant()),
                class_number=str(K.class_number()),
                class_group=str(cl),
                unit_group=str(K.unit_group()),
                ring_of_integers_basis=str(K.ring_of_integers().basis()),
                output=f"disc={K.discriminant()}, h={K.class_number()}, Cl={cl}",
            )

        elif topic == "splitting":
            poly_str = raw_kw.get("poly", str(kw.get("poly", "x^4-2")))
            primes = kw.get("primes", [2, 3, 5, 7, 11, 13, 17, 19, 23])
            if isinstance(primes, (int, sa.Integer)):
                primes = [int(primes)]
            x_var = sa.polygen(sa.QQ, "x")
            poly = sa.sage_eval(poly_str, locals={"x": x_var})
            K = sa.NumberField(poly, "a")
            OK = K.ring_of_integers()
            results_table = []
            for p_val in primes:
                p_val = int(p_val)
                try:
                    factorization = sa.ideal(OK, p_val).factor()
                    types = [(int(P.norm()), int(e)) for P, e in factorization]
                    if any(e > 1 for _, e in types):
                        split_type = "ramified"
                    elif len(types) == 1:
                        split_type = "inert"
                    else:
                        split_type = "split" if all(n_norm == p_val for n_norm, _ in types) else "partial split"
                    results_table.append({"p": p_val, "type": split_type, "factorization": str(factorization)})
                except Exception as e:
                    results_table.append({"p": p_val, "type": "error", "error": str(e)})
            return _result(
                "素数分裂类型",
                polynomial=poly_str,
                field_degree=str(K.degree()),
                splitting_data=json.dumps(results_table, ensure_ascii=False, default=str),
                output="; ".join(f"p={r['p']}: {r['type']}" for r in results_table),
            )

        elif topic == "representation":
            form_str = raw_kw.get("form", str(kw.get("form", "a^2+64*b^2")))
            bound = int(kw.get("bound", 200))
            compiled_form = compile(sa.preparse(form_str), "<repr>", "eval")
            eval_ns = {"Integer": int, "sa": sa}
            representable = []
            not_representable = []
            for p_val in sa.prime_range(3, bound):
                p_int = int(p_val)
                found = False
                limit = int(sa.isqrt(p_int)) + 1
                for a_val in range(0, limit + 1):
                    for b_val in range(1 if a_val == 0 else 0, limit + 1):
                        eval_ns["a"] = a_val
                        eval_ns["b"] = b_val
                        val = int(eval(compiled_form, eval_ns))
                        if val == p_int:
                            representable.append({"p": p_int, "a": a_val, "b": b_val})
                            found = True
                            break
                    if found:
                        break
                if not found:
                    not_representable.append(p_int)
            return _result(
                "素数二次型表示",
                form=form_str,
                bound=str(bound),
                representable=json.dumps(representable[:30], ensure_ascii=False, default=str),
                not_representable=str(not_representable[:30]),
                count_representable=str(len(representable)),
                count_not_representable=str(len(not_representable)),
                output=f"可表示素数 {len(representable)} 个, 不可表示 {len(not_representable)} 个",
            )

        else:
            return _result(
                "探索错误",
                error=f"未知主题: {topic}。可选: multiplicative_group, quadratic_residues, power_residues, class_group, splitting, representation",
            )

    except Exception as e:
        return _result("探索错误", topic=topic, params=params, error=str(e), traceback=_short_traceback())


@math_tool(category="sage_proof", description="系统性搜索数学命题的反例，找到立即返回")
def search_counterexample(predicate_code: str, param_name: str = "n", search_range: str = "range(1, 10000)") -> str:
    """搜索数学命题的反例。

    Args:
        predicate_code: 返回 True/False 的 SageMath 代码片段。搜索使该谓词为 False 的值。例如 'is_prime(2*n+1)' 会搜索使 2n+1 不是素数的 n
        param_name: 迭代变量名，默认 'n'
        search_range: 搜索范围的 SageMath 表达式，默认 'range(1, 10000)'
    """
    sa = _sage()
    namespace = _make_sage_namespace("")

    try:
        param_values = eval(compile(sa.preparse(search_range.strip()), "<search_range>", "eval"), namespace)
        compiled_pred = compile(sa.preparse(predicate_code.strip()), "<search_pred>", "eval")
    except Exception as e:
        return _result("搜索错误", error=f"无法解析搜索范围或谓词表达式: {e}")

    tested = 0
    error_count = 0
    sample_errors: list[str] = []

    for val in param_values:
        namespace[param_name] = val
        tested += 1
        try:
            ok = bool(eval(compiled_pred, namespace))
            if not ok:
                msg = f"{param_name} = {val}"
                return _result(
                    "找到反例",
                    counterexample=msg,
                    tested=str(tested),
                    predicate=predicate_code,
                    output=f"找到反例: {msg}（测试 {tested} 个值）",
                )
        except Exception as e:
            error_count += 1
            if len(sample_errors) < 3:
                sample_errors.append(f"{param_name}={val}: {e}")

    if tested > 0 and error_count == tested:
        return _result(
            "搜索错误",
            error=f"全部 {tested} 个候选值求值谓词时均出错（示例: {sample_errors[0]}）",
            tested=str(tested),
            errors=json.dumps(sample_errors, ensure_ascii=False),
        )

    valid_tested = tested - error_count
    conclusion = f"在 {valid_tested} 个有效测试值中未找到反例"
    if error_count > 0:
        conclusion += f"（另有 {error_count} 个值求值出错，如 {sample_errors[0]}）"

    return _result(
        "未找到反例",
        tested=str(tested),
        valid_tested=str(valid_tested),
        errors_count=str(error_count),
        search_range=search_range,
        predicate=predicate_code,
        conclusion=conclusion,
        output=conclusion,
    )


@math_tool(category="sage_proof", description="构造证明：执行 setup 代码建立代数环境，然后逐步执行证明步骤并收集计算结果，返回结构化证明骨架")
def construct_proof(setup_code: str, steps: str, example_params: str = "") -> str:
    """构造数学证明的计算骨架。

    Args:
        setup_code: SageMath 代码，定义证明中需要的代数对象。多行用换行分隔。例如 'R.<x> = QQ[]\\nK.<a> = NumberField(x^4 - 2)\\nOK = K.ring_of_integers()'
        steps: JSON 格式的证明步骤列表。每步包含 "desc"（步骤描述）和 "code"（SageMath 验证代码，最后一个表达式的值作为该步结果）
        example_params: 可选，用于具体化的参数赋值代码。例如 'p = 17' 或 'p = 17\\nn = 5'。会在 setup 之后、steps 之前执行
    """
    namespace = _make_sage_namespace("x y z t a b c n m k s p q r w alpha delta epsilon mu sigma rho tau omega")
    proof_result: dict[str, Any] = {"title": "证明构造", "steps": []}

    try:
        if setup_code.strip():
            _run_sage_code(setup_code, namespace, label="<proof_setup>")
        proof_result["setup"] = "OK"
    except Exception as e:
        return _result("证明构造错误", phase="setup", error=str(e), setup_code=setup_code)

    if example_params.strip():
        try:
            _run_sage_code(example_params, namespace, label="<proof_params>")
            proof_result["example_params"] = example_params.strip()
        except Exception as e:
            return _result("证明构造错误", phase="example_params", error=str(e))

    try:
        step_list = json.loads(steps)
        if not isinstance(step_list, list):
            return _result("证明构造错误", phase="parse_steps", error="steps 必须是 JSON 数组")
    except json.JSONDecodeError as e:
        return _result("证明构造错误", phase="parse_steps", error=f"steps JSON 解析失败: {e}")

    for i, step in enumerate(step_list):
        if not isinstance(step, dict):
            continue
        desc = step.get("desc", f"步骤 {i + 1}")
        code = step.get("code", "")
        step_info: dict[str, Any] = {"step": i + 1, "desc": desc}

        if not str(code).strip():
            step_info["result"] = "(无代码)"
            proof_result["steps"].append(step_info)
            continue

        try:
            result, stdout_text = _run_sage_code(str(code), namespace, label="<proof_step>")
            stdout_clean = stdout_text.strip()
            if result is None:
                res_str = stdout_clean or "Done"
            elif result == "Done" and stdout_clean:
                res_str = stdout_clean
            else:
                res_str = str(result)

            step_info["result"] = res_str
            if stdout_clean:
                step_info["stdout"] = stdout_clean
            if result is not None and result != "Done":
                try:
                    step_info["latex"] = _latex(result)
                except Exception:
                    pass
        except Exception as e:
            step_info["error"] = str(e)

        proof_result["steps"].append(step_info)

    steps_summary = []
    for s in proof_result["steps"]:
        tag = "✓" if "result" in s and "error" not in s else "✗"
        steps_summary.append(f"{tag} {s['desc']}: {s.get('result', s.get('error', ''))}"[:120])

    summary_text = "\n".join(steps_summary)
    info = {
        "title": "证明构造",
        "setup": proof_result.get("setup", ""),
        "total_steps": str(len(proof_result["steps"])),
        "successful_steps": str(sum(1 for s in proof_result["steps"] if "error" not in s)),
        "steps_detail": json.dumps(proof_result["steps"], ensure_ascii=False, default=str),
        "summary": summary_text,
        "output": summary_text,
        "_display_instruction": "基于以下计算结果构造严格的数学证明。每步的计算结果已由 SageMath 验证，你需要填充逻辑推理和数学论证",
    }
    if example_params.strip():
        info["example"] = example_params.strip()
    return json.dumps(info, ensure_ascii=False, default=str)
