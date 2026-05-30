"""
Catalan 常数 G 无理性证明的自动搜索

搜索一般二阶 Fuchsian 算子，检测其奇投影与 G 的整数关系。

算子参数化:
  Type A (一阶递推): θ² - z·P(θ), P(θ) = c0 + c1·θ + c2·θ²
    递推: n² u_n = (c0 + c1(n-1) + c2(n-1)²) u_{n-1}

  Type B (二阶递推): θ² - z·(a0+a1·θ) - z²·(b0+b1·θ+b2·θ²)
    递推: n² u_n = (a0+a1(n-1)) u_{n-1} + (b0+b1(n-2)+b2(n-2)²) u_{n-2}

Pipeline: 枚举 → 级数 → 奇投影 → PSLQ → ρ/σ 分析
"""
import mpmath
from mpmath import mpf, mp, pi, catalan, nstr, log
from fractions import Fraction
from math import gcd
from itertools import product
import time
import sys

# ---- 配置 ----
PSLQ_DPS = 200
SERIES_DPS = PSLQ_DPS + 50
N_TERMS = 150
MAXCOEFF_PSLQ = 10**6

G_CAT = None  # lazy init
PI2 = None


def init_mpmath():
    global G_CAT, PI2
    mp.dps = SERIES_DPS
    G_CAT = catalan
    PI2 = pi ** 2


# ---- Type A: θ² - z·P(θ), 一阶递推 ----
def type_a_series(c0, c1, c2, N):
    """n² u_n = P(n-1) u_{n-1}, P(x) = c0 + c1*x + c2*x²"""
    u = [Fraction(1)]
    for n in range(1, N + 1):
        P_val = Fraction(c0 + c1 * (n - 1) + c2 * (n - 1) ** 2)
        u.append(u[-1] * P_val / Fraction(n ** 2))
    return u


# ---- Type B: 二阶递推 ----
def type_b_series(a0, a1, b0, b1, b2, N):
    """n² u_n = (a0+a1(n-1)) u_{n-1} + (b0+b1(n-2)+b2(n-2)²) u_{n-2}"""
    u = [Fraction(1), Fraction(a0)]  # u_0=1, u_1=a0/1
    for n in range(2, N + 1):
        A = Fraction(a0 + a1 * (n - 1))
        B = Fraction(b0 + b1 * (n - 2) + b2 * (n - 2) ** 2)
        u.append((A * u[n - 1] + B * u[n - 2]) / Fraction(n ** 2))
    return u


def odd_projection(u, z0, N):
    """F_odd(z0) = Σ_{n odd} u_n z0^n"""
    s = mpf(0)
    z0_mpf = mpf(z0)
    for n in range(1, min(N + 1, len(u)), 2):
        s += mpf(u[n].numerator) / mpf(u[n].denominator) * z0_mpf ** n
    return s


def even_projection(u, z0, N):
    s = mpf(0)
    z0_mpf = mpf(z0)
    for n in range(0, min(N + 1, len(u)), 2):
        s += mpf(u[n].numerator) / mpf(u[n].denominator) * z0_mpf ** n
    return s


def full_series(u, z0, N):
    s = mpf(0)
    z0_mpf = mpf(z0)
    for n in range(min(N + 1, len(u))):
        s += mpf(u[n].numerator) / mpf(u[n].denominator) * z0_mpf ** n
    return s


def series_diverges(u, N_check=50):
    """检查级数是否发散（系数增长太快）"""
    for n in range(min(N_check, len(u) - 1), 0, -1):
        if u[n] == 0:
            continue
        r = abs(u[n]) / abs(u[n - 1]) if u[n - 1] != 0 else float('inf')
        if float(r) > 1e6:
            return True
    return False


def estimate_rho_sigma(u, c_lead):
    """估计 ρ (解析衰减率) 和 σ (算术增长率)"""
    rho = float(log(abs(c_lead))) if c_lead != 0 else 0.0

    # σ: 分母增长率
    denoms = []
    for n in range(1, min(len(u), 80)):
        d = abs(u[n].denominator)
        if d > 0:
            denoms.append((n, d))

    if len(denoms) < 10:
        return rho, float('inf')

    # lcm(1..n) ~ e^n (素数定理)
    # σ = lim log(denom(u_n)) / n
    last_few = denoms[-20:]
    sigma_vals = []
    for n, d in last_few:
        if d > 1 and n > 0:
            sigma_vals.append(float(log(mpf(d))) / n)

    sigma = max(sigma_vals) if sigma_vals else 0.0
    return rho, sigma


def run_pslq(vec, maxcoeff=MAXCOEFF_PSLQ):
    old_dps = mp.dps
    mp.dps = PSLQ_DPS
    try:
        rel = mpmath.pslq(vec, maxcoeff=maxcoeff)
    finally:
        mp.dps = old_dps
    if rel is None:
        return None
    dot = sum(mpf(r) * v for r, v in zip(rel, vec))
    if abs(dot) < mpf(10) ** (-(PSLQ_DPS // 3)):
        return rel
    return None


# ---- 主搜索 ----
def search_type_a(M, z_points, verbose=True):
    """搜索 Type A: θ² - z·(c0 + c1·θ + c2·θ²), |ci| ≤ M, c2 ≠ 0"""
    hits = []
    total = 0
    tested = 0
    t0 = time.time()

    for c2 in range(-M, M + 1):
        if c2 == 0:
            continue
        for c1 in range(-M, M + 1):
            for c0 in range(-M, M + 1):
                total += 1
                try:
                    u = type_a_series(c0, c1, c2, N_TERMS)
                except (ZeroDivisionError, OverflowError):
                    continue

                if series_diverges(u):
                    continue

                tested += 1
                for z0 in z_points:
                    try:
                        F_odd = odd_projection(u, z0, N_TERMS)
                        if abs(F_odd) < mpf(10) ** (-50):
                            continue

                        # PSLQ: F_odd vs G
                        rel = run_pslq([F_odd, G_CAT, mpf(1)])
                        if rel and rel[1] != 0:
                            rho, sigma = estimate_rho_sigma(u, c2)
                            hit = {
                                'type': 'A', 'params': (c0, c1, c2),
                                'z0': z0, 'rel': rel,
                                'F_odd': F_odd, 'rho': rho, 'sigma': sigma,
                            }
                            hits.append(hit)
                            if verbose:
                                print(f"\n  ** HIT ** c=({c0},{c1},{c2}) z0={z0}")
                                print(f"     rel: {rel[0]}*F_odd + {rel[1]}*G + {rel[2]} = 0")
                                print(f"     rho={rho:.4f}, sigma={sigma:.4f}")

                        # PSLQ: F_odd vs G, pi^2
                        rel2 = run_pslq([F_odd, G_CAT, PI2, mpf(1)])
                        if rel2 and rel2[1] != 0:
                            rho, sigma = estimate_rho_sigma(u, c2)
                            hit = {
                                'type': 'A', 'params': (c0, c1, c2),
                                'z0': z0, 'rel': rel2, 'rel_type': '4-term',
                                'F_odd': F_odd, 'rho': rho, 'sigma': sigma,
                            }
                            hits.append(hit)
                            if verbose:
                                print(f"\n  ** HIT(4) ** c=({c0},{c1},{c2}) z0={z0}")
                                print(f"     rel: {rel2}")
                                print(f"     rho={rho:.4f}, sigma={sigma:.4f}")

                    except Exception:
                        continue

    elapsed = time.time() - t0
    if verbose:
        print(f"\n  Type A: {total} candidates, {tested} tested, "
              f"{len(hits)} hits, {elapsed:.1f}s")
    return hits


def search_type_b(M, z_points, verbose=True):
    """搜索 Type B: 二阶递推, |coeffs| ≤ M"""
    hits = []
    total = 0
    tested = 0
    t0 = time.time()

    for a0 in range(-M, M + 1):
        if a0 == 0:
            continue
        for a1 in range(-M, M + 1):
            for b0 in range(-M, M + 1):
                for b2 in range(-M, M + 1):
                    # b1=0 先搜（减少维度）
                    for b1 in [0]:
                        if b0 == 0 and b1 == 0 and b2 == 0:
                            continue
                        total += 1
                        try:
                            u = type_b_series(a0, a1, b0, b1, b2, N_TERMS)
                        except (ZeroDivisionError, OverflowError):
                            continue

                        if series_diverges(u):
                            continue

                        tested += 1
                        for z0 in z_points:
                            try:
                                F_odd = odd_projection(u, z0, N_TERMS)
                                if abs(F_odd) < mpf(10) ** (-50):
                                    continue

                                rel = run_pslq([F_odd, G_CAT, mpf(1)])
                                if rel and rel[1] != 0:
                                    rho, sigma = estimate_rho_sigma(u, max(abs(b2), abs(a0), 1))
                                    hit = {
                                        'type': 'B',
                                        'params': (a0, a1, b0, b1, b2),
                                        'z0': z0, 'rel': rel,
                                        'F_odd': F_odd,
                                        'rho': rho, 'sigma': sigma,
                                    }
                                    hits.append(hit)
                                    if verbose:
                                        print(f"\n  ** HIT ** ({a0},{a1},{b0},{b1},{b2}) z0={z0}")
                                        print(f"     rel: {rel}")
                                        print(f"     rho={rho:.4f}, sigma={sigma:.4f}")
                            except Exception:
                                continue

    elapsed = time.time() - t0
    if verbose:
        print(f"\n  Type B: {total} candidates, {tested} tested, "
              f"{len(hits)} hits, {elapsed:.1f}s")
    return hits


def analyze_hit(hit):
    """对命中的算子做详细分析"""
    print(f"\n{'=' * 60}")
    print(f"  Detailed analysis: Type {hit['type']}, params={hit['params']}")
    print(f"{'=' * 60}")

    if hit['type'] == 'A':
        c0, c1, c2 = hit['params']
        u = type_a_series(c0, c1, c2, N_TERMS)
    else:
        a0, a1, b0, b1, b2 = hit['params']
        u = type_b_series(a0, a1, b0, b1, b2, N_TERMS)

    # 打印前几个系数
    print(f"  u[0..10] = {[str(u[i]) for i in range(min(11, len(u)))]}")

    # 检查是否全为整数
    all_int = all(u[i].denominator == 1 for i in range(min(80, len(u))))
    print(f"  All integer (n≤80): {all_int}")

    # 分母增长
    for n in [10, 20, 50, 100]:
        if n < len(u):
            d = u[n].denominator
            print(f"  denom(u_{n}) = {d} ({len(str(d))} digits)")

    # 多点验证
    print(f"\n  Multi-point PSLQ verification:")
    for z0 in [Fraction(1, 4), Fraction(1, 8), Fraction(1, 16),
               Fraction(1, 32), Fraction(1, 64)]:
        F_odd = odd_projection(u, z0, N_TERMS)
        F_even = even_projection(u, z0, N_TERMS)
        F_full = full_series(u, z0, N_TERMS)

        for label, val in [("F_odd", F_odd), ("F_even", F_even), ("F", F_full)]:
            if abs(val) < mpf(10) ** (-50):
                continue
            rel = run_pslq([val, G_CAT, mpf(1)])
            if rel and (rel[1] != 0):
                print(f"    z0={z0}: {label} -> {rel}")
            rel2 = run_pslq([val, G_CAT, PI2, mpf(1)])
            if rel2 and (rel2[1] != 0):
                print(f"    z0={z0}: {label}(4-term) -> {rel2}")

    # ρ, σ
    rho, sigma = hit['rho'], hit['sigma']
    print(f"\n  rho = {rho:.6f}, sigma = {sigma:.6f}")
    if sigma < rho:
        print(f"  *** HALTING CONDITION MET: sigma < rho ***")
        print(f"  *** margin = {rho - sigma:.6f} ***")
    else:
        print(f"  Halting condition NOT met (sigma >= rho)")


def main():
    init_mpmath()

    print("Catalan G irrationality search")
    print(f"PSLQ precision: {PSLQ_DPS} digits, series terms: {N_TERMS}")
    print()

    z_points = [Fraction(1, 4), Fraction(1, 8), Fraction(1, 16)]

    # ---- Type A 搜索 ----
    print("=" * 60)
    print("  Type A: θ² - z·(c0 + c1·θ + c2·θ²), M=20")
    print("=" * 60)
    hits_a = search_type_a(M=20, z_points=z_points)

    # ---- Type B 搜索 (小范围) ----
    print()
    print("=" * 60)
    print("  Type B: 二阶递推, M=5")
    print("=" * 60)
    hits_b = search_type_b(M=5, z_points=z_points)

    # ---- 分析所有命中 ----
    all_hits = hits_a + hits_b
    if all_hits:
        print(f"\n\n{'#' * 60}")
        print(f"  TOTAL HITS: {len(all_hits)}")
        print(f"{'#' * 60}")
        for hit in all_hits:
            analyze_hit(hit)
    else:
        print("\n  No hits found.")

    # ---- 基准验证: 已知的 C(2n,n)^2 / 16^n 算子 ----
    print()
    print("=" * 60)
    print("  Benchmark: known operator for 4G/pi")
    print("  θ² - z·(2θ+1)² = θ² - z·(1 + 4θ + 4θ²)")
    print("  c = (1, 4, 4), u_n = C(2n,n)²/16^n")
    print("=" * 60)
    u_bench = type_a_series(1, 4, 4, N_TERMS)
    print(f"  u[0..5] = {[str(u_bench[i]) for i in range(6)]}")
    from math import comb
    print(f"  C(2n,n)^2/16^n [0..5] = {[Fraction(comb(2*n,n)**2, 16**n) for n in range(6)]}")
    match = all(u_bench[n] == Fraction(comb(2*n, n) ** 2, 16 ** n) for n in range(50))
    print(f"  Match with C(2n,n)^2/16^n: {match}")

    # PSLQ on this benchmark
    for z0 in [Fraction(1, 4), Fraction(1, 2)]:
        F_odd = odd_projection(u_bench, z0, N_TERMS)
        print(f"\n  z0={z0}: F_odd = {nstr(F_odd, 30)}")
        rel = run_pslq([F_odd, G_CAT, mpf(1)])
        print(f"    PSLQ [F_odd, G, 1] = {rel}")
        rel2 = run_pslq([F_odd, G_CAT, PI2, mpf(1)])
        print(f"    PSLQ [F_odd, G, pi^2, 1] = {rel2}")
        rel3 = run_pslq([F_odd, G_CAT / pi, mpf(1)])
        print(f"    PSLQ [F_odd, G/pi, 1] = {rel3}")


if __name__ == "__main__":
    main()
