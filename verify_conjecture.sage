from sage.all import *

def solve():
    prec = 2000
    R = RealField(prec)
    
    pi_val = R(pi)
    G_val = R(catalan)
    
    chi = DirichletGroup(4).0
    
    q_val = R(exp(-2*pi_val))
    
    def compute_M_plus(b_func, n_terms=1500):
        val = R(0)
        qn = q_val
        for n in range(1, n_terms):
            bn = b_func(n)
            if bn != 0:
                val += R(bn) / R(n**3) * qn
            qn *= q_val
        return val

    # Candidate 1: E4(chi, 1) -> sum_{d|n} chi(n/d) d^3
    def b1(n):
        return sum(chi(n//d) * d**3 for d in divisors(n))

    # Candidate 2: Twisted E4 -> chi(n) sigma_3(n)
    def b2(n):
        return chi(n) * sigma(n, 3)

    # Candidate 3: E4(1, chi) -> sum_{d|n} chi(d) d^3
    def b3(n):
        return sum(chi(d) * d**3 for d in divisors(n))

    candidates = [
        ("Candidate 1 (E4(chi, 1))", b1),
        ("Candidate 2 (Twisted E4)", b2),
        ("Candidate 3 (E4(1, chi))", b3)
    ]
    
    for name, b_func in candidates:
        print(f"Testing {name} with c0=0...")
        M_val = compute_M_plus(b_func, n_terms=1500)
        
        basis = [M_val, R(1), G_val / pi_val**2, pi_val, pi_val**2, pi_val**3]
        
        try:
            rel = list(pari(basis).lindep())
            if rel:
                rel = [int(x) for x in rel]
                max_c = max(abs(x) for x in rel)
                print(f"Max coeff: {max_c}")
                if max_c < 10**15:
                    print(f"\nSUCCESS with {name}")
                    print(f"Relation: {rel}")
                    k1, k2, k3 = rel[0], rel[1], rel[2]
                    # Format output
                    print(f"k1*M + k2 + k3*G/pi^2 + k4*pi + k5*pi^2 + k6*pi^3 = 0")
        except Exception as e:
            print(f"Error: {e}")

solve()