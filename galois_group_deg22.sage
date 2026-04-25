"""
Compute the Galois group of a degree-22 irreducible polynomial over QQ.

Strategy:
  1. Verify irreducibility over ZZ.
  2. Factor mod small primes to collect Frobenius cycle types
     (this reveals conjugacy class information about Gal(f)).
  3. Attempt PARI nfgalois with enlarged stack (8 GB).
  4. If PARI fails, try Sage's NumberField.galois_group() which
     internally calls PARI's galoisinit (different algorithm from polgalois).

Usage:
    sage galois_group_deg22.sage 2>&1 | tee galois_group_deg22.log
"""

import sys
import time
from datetime import datetime

LOG_FILE = "galois_group_deg22.log"

def log(msg, fh=None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    sys.stdout.flush()
    if fh:
        fh.write(line + "\n")
        fh.flush()

fh = open(LOG_FILE, "w")
log("=" * 70, fh)
log("Galois group computation for degree-22 polynomial", fh)
log("=" * 70, fh)

# ---------- 0. Increase PARI stack ----------
log("Allocating 8 GB PARI stack...", fh)
pari.allocatemem(8 * 1024 * 1024 * 1024)  # 8 GB
log("PARI stack allocated.", fh)

# ---------- 1. Define the polynomial ----------
R.<x> = QQ[]
f = (91577378901908524617*x^22
 + 41533927080143901425946*x^21
 - 190497252713697990743571009*x^20
 - 84046772677164727604893501860*x^19
 - 12976462958100115586084715945334*x^18
 - 662968297367174987364534043801038*x^17
 + 30978822117566163694967118803630349*x^16
 + 4298778412818706538504057933230209868*x^15
 + 59331050338342581761957950869713037876*x^14
 - 6956597984473712745962702898680174113632*x^13
 - 174136616352415503133265515742134405908800*x^12
 + 4488305274816423952429435122982161898149888*x^11
 + 84594737483411333644661377617768563002730496*x^10
 - 2023585037955222617522292797744863523963494400*x^9
 - 4561273269542345522611466341140376239951691776*x^8
 + 382621945493671034333873647112669460916458749952*x^7
 - 3769732951938882778462185142961401076411820670976*x^6
 + 17454956205488557922974379829230570929042413846528*x^5
 - 44294489883025041236119844853859480334285628506112*x^4
 + 62981979280464599679100034391419316702394017906688*x^3
 - 47246409914093930471970476329501247739624073199616*x^2
 + 15460264035052758214860149380839102167068685893632*x
 - 1241537967673355857310908864851061583392710590464)

log(f"Polynomial degree: {f.degree()}", fh)
log(f"Leading coefficient: {f.leading_coefficient()}", fh)

# ---------- 2. Irreducibility test ----------
log("Testing irreducibility over ZZ...", fh)
t0 = time.time()
Zx.<t> = ZZ[]
f_int = Zx(f)
irr = f_int.is_irreducible()
log(f"Irreducible: {irr}  (took {time.time()-t0:.2f}s)", fh)

if not irr:
    log("Polynomial is reducible. Factoring over ZZ...", fh)
    fac = f_int.factor()
    for (g, e) in fac:
        log(f"  factor of degree {g.degree()}, multiplicity {e}", fh)
    log("Will compute Galois group for each irreducible factor separately.", fh)

# ---------- 3. Frobenius cycle types (mod-p factorization) ----------
log("", fh)
log("=== Frobenius cycle types (factorization mod primes 3..500) ===", fh)
t0 = time.time()
cycle_types = {}
bad_primes = []

for p in primes(3, 500):
    try:
        Fp = GF(p)
        Fpx.<u> = Fp[]
        fp = Fpx(f_int)
        if fp.degree() < 22:  # leading coeff divisible by p
            bad_primes.append(p)
            continue
        facs = fp.factor()
        degs = sorted([g.degree() for g, e in facs])
        key = tuple(degs)
        if key not in cycle_types:
            cycle_types[key] = []
        cycle_types[key].append(p)
    except Exception:
        bad_primes.append(p)

log(f"Computed in {time.time()-t0:.2f}s", fh)
log(f"Bad primes (divide leading coeff): {bad_primes}", fh)
log(f"Total distinct cycle types: {len(cycle_types)}", fh)
log("", fh)
log("Cycle type (sorted factor degrees) -> count [example primes]:", fh)
for ct in sorted(cycle_types.keys()):
    primes_list = cycle_types[ct]
    examples = str(primes_list[:8])
    log(f"  {ct} : {len(primes_list)} primes, e.g. {examples}", fh)

# ---------- 4. Discriminant ----------
log("", fh)
log("=== Number field construction ===", fh)
f_monic = f / f.leading_coefficient()
log("Constructing number field K = Q[x]/(f_monic)...", fh)
t0 = time.time()
K.<a> = NumberField(f_monic)
log(f"Number field constructed in {time.time()-t0:.2f}s, degree {K.degree()}", fh)

log("Computing discriminant (this may take a while)...", fh)
t0 = time.time()
try:
    disc = K.discriminant()
    log(f"Discriminant computed in {time.time()-t0:.2f}s", fh)
    log(f"Discriminant = {disc}", fh)
    log(f"Discriminant (factored, partial):", fh)
    try:
        disc_fac = disc.factor()
        log(f"  {disc_fac}", fh)
    except Exception as ex:
        log(f"  (factorization failed: {ex})", fh)
except Exception as ex:
    log(f"Discriminant computation failed: {ex}", fh)

# ---------- 5. Galois group via PARI ----------
log("", fh)
log("=== Galois group computation (PARI nfgalois) ===", fh)
t0 = time.time()
try:
    G = K.galois_group()
    elapsed = time.time() - t0
    log(f"Galois group computed in {elapsed:.2f}s", fh)
    log(f"Galois group: {G}", fh)
    try:
        log(f"Order: {G.order()}", fh)
    except Exception:
        pass
    try:
        log(f"Is transitive: {G.is_transitive()}", fh)
    except Exception:
        pass
    try:
        log(f"Generators: {G.gens()}", fh)
    except Exception:
        pass
    try:
        log(f"GAP identifier: {G.gap().IdGroup()}", fh)
    except Exception:
        pass
except Exception as ex:
    log(f"PARI/Sage galois_group() failed after {time.time()-t0:.2f}s: {ex}", fh)
    log("", fh)
    log("=== Fallback: direct PARI galoisinit ===", fh)
    t0 = time.time()
    try:
        f_pari = pari(f_monic)
        log("Running nfinit...", fh)
        nf = f_pari.nfinit()
        log(f"nfinit done in {time.time()-t0:.2f}s", fh)
        log("Running galoisinit...", fh)
        t1 = time.time()
        gi = nf.galoisinit()
        log(f"galoisinit done in {time.time()-t1:.2f}s", fh)
        log(f"galoisinit result: {gi}", fh)
    except Exception as ex2:
        log(f"Direct PARI galoisinit failed: {ex2}", fh)
        log("", fh)
        log("=== Galois group identification from cycle types ===", fh)
        log("The mod-p factorization data above can be used to identify", fh)
        log("the Galois group. Compare cycle types with known transitive", fh)
        log("subgroups of S_22 using GAP's TransitiveGroup database.", fh)

log("", fh)
log("=== DONE ===", fh)
fh.close()
print(f"\nLog written to {LOG_FILE}")
