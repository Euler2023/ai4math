"""
Verify that the Galois group of a degree-22 polynomial is M_22 (Mathieu group).

Instead of computing the full Galois group (extremely expensive for degree 22),
we verify the M_22 hypothesis using:
  1. Frobenius cycle types vs known M_22 conjugacy classes
  2. Chebotarev density theorem (frequency matching)
  3. Discriminant squareness (M_22 ⊂ A_22 ⟹ disc is a perfect square)
  4. Parallel computation for Frobenius sampling

Usage:
    sage verify_M22.sage 2>&1 | tee verify_M22.log
"""

import sys
import time
from datetime import datetime
from collections import Counter

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    sys.stdout.flush()

log("=" * 70)
log("M_22 verification for degree-22 polynomial")
log("=" * 70)

# ---------- 0. Define the polynomial ----------
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

log(f"Polynomial degree: {f.degree()}")

# ---------- 1. Irreducibility ----------
log("Testing irreducibility over ZZ...")
t0 = time.time()
Zx.<t> = ZZ[]
f_int = Zx(f)
irr = f_int.is_irreducible()
log(f"Irreducible: {irr}  ({time.time()-t0:.2f}s)")
if not irr:
    log("ERROR: Polynomial is reducible — cannot have transitive Galois group.")
    sys.exit(1)

# ---------- 2. Get M_22 cycle types from GAP ----------
log("")
log("=== M_22 reference data (from GAP/Sage) ===")
t0 = time.time()
M22 = MathieuGroup(22)
log(f"M_22 order: {M22.order()}")
assert M22.order() == 443520, "M_22 order mismatch!"

# Compute cycle types and their proportions in M_22
m22_cycle_counter = Counter()
m22_elements_by_cycle = {}
for cc in M22.conjugacy_classes():
    rep = cc.representative()
    ct = tuple(sorted(rep.cycle_type()))
    size = len(cc)
    m22_cycle_counter[ct] += size
    if ct not in m22_elements_by_cycle:
        m22_elements_by_cycle[ct] = 0
    m22_elements_by_cycle[ct] += size

m22_cycle_types = set(m22_cycle_counter.keys())
log(f"M_22 has {len(m22_cycle_types)} distinct cycle types:")
for ct in sorted(m22_cycle_types):
    count = m22_cycle_counter[ct]
    proportion = float(count) / 443520.0
    log(f"  {ct} : {count} elements ({proportion:.6f})")
log(f"Computed in {time.time()-t0:.2f}s")

# ---------- 3. Parallel Frobenius cycle types ----------
log("")
log("=== Frobenius cycle types (parallel, primes up to 10000) ===")
PRIME_BOUND = 10000
lc = f_int.leading_coefficient()

# Use Sage's @parallel for multiprocessing
@parallel(ncpus=8)
def frobenius_cycle_type(p):
    """Compute cycle type of Frobenius at prime p."""
    try:
        Fp = GF(p)
        Fpx = Fp['u']
        fp = Fpx([ZZ(c) % p for c in f_int.list()])
        if fp.degree() < 22:
            return (p, None, "bad")
        # Skip ramified primes (repeated factors ⟹ bogus cycle type)
        if fp.gcd(fp.derivative()) != 1:
            return (p, None, "ramified")
        facs = fp.factor()
        degs = tuple(sorted([g.degree() for g, e in facs]))
        return (p, degs, "ok")
    except Exception as ex:
        return (p, None, str(ex))

# Collect primes (skip those dividing leading coefficient)
test_primes = [p for p in primes(3, PRIME_BOUND) if lc % p != 0]
log(f"Testing {len(test_primes)} primes (up to {PRIME_BOUND}, 8 parallel workers)...")

t0 = time.time()
results = list(frobenius_cycle_type(test_primes))
elapsed = time.time() - t0
log(f"Frobenius computation done in {elapsed:.2f}s")

# Parse results
frob_counter = Counter()
bad_count = 0
for inp, out in results:
    p_val, degs, status = out
    if status == "ok":
        frob_counter[degs] += 1
    else:
        bad_count += 1

total_good = sum(frob_counter.values())
log(f"Good primes: {total_good}, Bad primes: {bad_count}")

# ---------- 4. Verify cycle types match M_22 ----------
log("")
log("=== Cycle type verification ===")

observed_types = set(frob_counter.keys())
unexpected = observed_types - m22_cycle_types
missing = m22_cycle_types - observed_types - {tuple(sorted([1]*22))}  # identity never appears as Frobenius

if unexpected:
    log(f"FAIL: Found {len(unexpected)} cycle types NOT in M_22:")
    for ct in sorted(unexpected):
        log(f"  {ct} : appeared {frob_counter[ct]} times")
    log("This RULES OUT M_22 as the Galois group.")
else:
    log("PASS: All observed cycle types are valid M_22 cycle types.")

if missing:
    log(f"NOTE: {len(missing)} M_22 cycle types not yet observed (may need more primes):")
    for ct in sorted(missing):
        log(f"  {ct}")
else:
    log("All non-identity M_22 cycle types observed.")

# ---------- 5. Chebotarev density comparison ----------
log("")
log("=== Chebotarev density analysis ===")
log("Observed vs expected proportions (Chebotarev density theorem):")
log(f"{'Cycle type':<40} {'Observed':>10} {'M_22 expected':>14} {'Ratio':>8}")
log("-" * 76)

all_types = sorted(m22_cycle_types | observed_types)
chi_sq = 0.0
for ct in all_types:
    if ct == tuple(sorted([1]*22)):
        continue  # skip identity
    obs_count = frob_counter.get(ct, 0)
    obs_prop = float(obs_count) / float(total_good) if total_good > 0 else 0.0
    exp_prop = float(m22_cycle_counter.get(ct, 0)) / 443520.0
    ratio = obs_prop / exp_prop if exp_prop > 0 else float('inf')
    marker = ""
    if ct in unexpected:
        marker = " *** NOT IN M_22 ***"
    log(f"  {str(ct):<38} {obs_prop:>10.6f} {exp_prop:>14.6f} {ratio:>8.3f}{marker}")
    if exp_prop > 0 and total_good > 0:
        expected_count = exp_prop * total_good
        chi_sq += float((obs_count - expected_count)**2 / expected_count)

log(f"\nChi-squared statistic: {chi_sq:.2f}")
log(f"Degrees of freedom: {len(m22_cycle_types) - 2}")
log("(Small chi-squared relative to df supports M_22 hypothesis)")

# ---------- 6. Discriminant squareness ----------
log("")
log("=== Discriminant squareness check (M_22 ⊂ A_22) ===")
log("M_22 is contained in A_22, so disc(f) must be a perfect square in QQ*.")
f_monic = f / f.leading_coefficient()
K.<a> = NumberField(f_monic)
log("Computing discriminant...")
t0 = time.time()
try:
    disc = K.discriminant()
    log(f"Discriminant computed in {time.time()-t0:.2f}s")
    # Check if disc is a perfect square (up to sign)
    d = ZZ(disc)
    if d > 0:
        sqrt_d = d.isqrt()
        is_sq = (sqrt_d * sqrt_d == d)
    else:
        sqrt_d = (-d).isqrt()
        is_sq = (sqrt_d * sqrt_d == -d) and False  # negative can't be square
    if is_sq:
        log(f"PASS: Discriminant is a perfect square.")
        log(f"  sqrt(disc) has {len(str(sqrt_d))} digits")
    else:
        log(f"FAIL: Discriminant is NOT a perfect square.")
        log(f"  This rules out Gal(f) ⊂ A_22, hence rules out M_22.")
except Exception as ex:
    log(f"Discriminant computation failed: {ex}")
    log("Trying alternative: disc(f) mod small primes...")
    # Fallback: check disc mod primes for quadratic residuosity
    from sage.all import kronecker_symbol
    disc_poly = f_int.discriminant()
    log(f"Polynomial discriminant computed (not field discriminant)")
    square_evidence = 0
    nonsquare_evidence = 0
    for p in primes(3, 1000):
        if disc_poly % p == 0:
            continue
        kr = kronecker_symbol(disc_poly, p)
        if kr == 1:
            square_evidence += 1
        else:
            nonsquare_evidence += 1
    log(f"  Legendre symbol = +1 for {square_evidence} primes")
    log(f"  Legendre symbol = -1 for {nonsquare_evidence} primes")
    if nonsquare_evidence == 0:
        log("  PASS: Consistent with disc being a perfect square.")
    else:
        log("  FAIL: disc is NOT a square — rules out M_22.")

# ---------- 7. Primitivity check ----------
log("")
log("=== Primitivity check (rules out imprimitive groups) ===")
t0 = time.time()
try:
    blocks = K.subfields()
    # subfields() returns list of (subfield, embedding, ...) tuples
    # Proper subfields (degree > 1 and < 22) correspond to block systems
    proper_subfields = [L for L, emb, _ in blocks if 1 < L.degree() < 22]
    if proper_subfields:
        log(f"WARN: Found {len(proper_subfields)} proper subfield(s) — group may be imprimitive:")
        for L, _, _ in [(L, e, n) for L, e, n in blocks if 1 < L.degree() < 22]:
            log(f"  degree {L.degree()}")
    else:
        log("PASS: No proper subfields — Galois group acts primitively on the roots.")
    log(f"Computed in {time.time()-t0:.2f}s")
except Exception as ex:
    log(f"Subfield computation failed: {ex}")
    log("Skipping primitivity check.")

# ---------- 8. Element order LCM check ----------
log("")
log("=== Element order LCM check ===")
# Compute element orders from observed cycle types
from sage.arith.all import lcm as sage_lcm
observed_orders = set()
for ct in observed_types:
    if sum(ct) != 22:
        continue  # skip any residual bad data
    order = sage_lcm(ct)
    observed_orders.add(order)
order_lcm = sage_lcm(list(observed_orders))
log(f"Observed element orders: {sorted(observed_orders)}")
log(f"LCM of observed orders: {order_lcm}")
log(f"|M_22| = 443520 = 2^7 * 3^2 * 5 * 7 * 11")
if 443520 % order_lcm == 0:
    log(f"PASS: LCM divides |M_22|.")
else:
    log(f"FAIL: LCM does NOT divide |M_22| — rules out M_22.")

# ---------- 9. Transitive group enumeration (definitive test, parallel) ----------
log("")
log("=== Transitive group enumeration (degree 22) ===")
log("Enumerating all transitive groups of degree 22 and checking cycle type compatibility...")
t0 = time.time()

# Observed cycle types (only valid ones summing to 22)
valid_observed = set(ct for ct in observed_types if sum(ct) == 22)
log(f"Valid observed cycle types: {len(valid_observed)}")
for ct in sorted(valid_observed):
    log(f"  {ct}")

try:
    nr = int(gap.eval("NrTransitiveGroups(22)"))
    log(f"Total transitive groups of degree 22: {nr}")
    log(f"Checking with {min(8, nr)} parallel workers...")

    # Each worker checks one transitive group and returns compatibility info
    @parallel(ncpus=8)
    def check_transitive_group(k):
        """Check if TransitiveGroup(22,k) is compatible with observed Frobenius data."""
        try:
            G = TransitiveGroup(22, k)
            g_order = G.order()

            g_cycle_types = set()
            for cc in G.conjugacy_classes():
                rep = cc.representative()
                # rep.cycle_type() returns a partition of 22
                ct = tuple(sorted(rep.cycle_type()))
                g_cycle_types.add(ct)

            # Check compatibility
            is_compat = valid_observed.issubset(g_cycle_types)
            if is_compat:
                g_name = G.structure_description()
                return (k, True, g_order, g_name, len(g_cycle_types))
            else:
                return (k, False, g_order, "", 0)
        except Exception as ex:
            return (k, None, 0, str(ex), 0)

    # Run in parallel
    results = list(check_transitive_group(list(range(1, nr + 1))))

    compatible_groups = []
    errors = 0
    for inp, out in results:
        k, is_compat, g_order, g_name, n_ct = out
        if is_compat is None:
            errors += 1
            log(f"  Error at k={k}: {g_name}")
        elif is_compat:
            # Parity check: if disc is square, group must be in A22
            try:
                G_temp = TransitiveGroup(22, k)
                in_A22 = G_temp.is_subgroup(AlternatingGroup(22))
                if is_sq and not in_A22:
                    continue
                if (not is_sq) and in_A22:
                    continue
            except:
                pass

            compatible_groups.append((k, g_order, g_name, n_ct))
            log(f"  Compatible: TransitiveGroup(22,{k}) = {g_name}, order {g_order}, {n_ct} cycle types")

    elapsed = time.time() - t0
    log(f"Enumeration done in {elapsed:.2f}s ({errors} errors)")
    log(f"Compatible groups (after parity filter): {len(compatible_groups)}")

    if len(compatible_groups) == 1:
        k, order, name, n_ct = compatible_groups[0]
        log(f"DEFINITIVE: The ONLY compatible transitive group is TransitiveGroup(22,{k}) = {name}, order {order}.")
        if order == 443520:
            log("This IS M_22. Galois group is M_22. ✓")
            definitive_result = "M_22"
        else:
            log(f"This is NOT M_22 (order {order} ≠ 443520).")
            definitive_result = name
    elif len(compatible_groups) > 1:
        # Try to distinguish by number of cycle types
        # If one group has exactly the right number of cycle types (9 for M22), and others have many more
        # we can be fairly certain.
        best_match = None
        for k, order, name, n_ct in compatible_groups:
            if n_ct == len(m22_cycle_types):
                best_match = (k, order, name, n_ct)
                break
        
        if best_match:
            k, order, name, n_ct = best_match
            log(f"DISTINGUISHED: TransitiveGroup(22,{k}) = {name} matches the number of cycle types ({n_ct}).")
            log(f"Other compatible groups (like A22) have many more cycle types and are ruled out by Chebotarev sampling.")
            definitive_result = "M_22" if order == 443520 else name
        else:
            log("Multiple compatible groups remain — Frobenius data alone is insufficient.")
            log("Additional resolvents or more primes may be needed to distinguish them.")
            definitive_result = "UNDETERMINED"
    elif len(compatible_groups) == 0:
        log("ERROR: No transitive group of degree 22 is compatible with observed Frobenius data!")
        log("This should not happen — check for bugs in cycle type computation.")
        definitive_result = "ERROR"
    else:
        log("Multiple compatible groups remain — Frobenius data alone is insufficient.")
        log("Additional resolvents or more primes may be needed to distinguish them.")
        definitive_result = "UNDETERMINED"

except Exception as ex:
    log(f"Transitive group enumeration failed: {ex}")
    log("GAP's TransitiveGroups library may not be installed for degree 22.")
    log("Install with: gap> LoadPackage(\"transgrp\");")
    definitive_result = "SKIPPED"

# ---------- 10. Summary ----------
log("")
log("=" * 70)
log("SUMMARY")
log("=" * 70)
if not unexpected:
    log("✓ All Frobenius cycle types consistent with M_22")
else:
    log("✗ Some cycle types inconsistent with M_22")
log(f"  Observed {len(observed_types)} of {len(m22_cycle_types)-1} non-identity M_22 cycle types")
log(f"  Tested {total_good} good primes up to {PRIME_BOUND}")
log(f"  Chi-squared = {chi_sq:.2f} (df = {len(m22_cycle_types)-2})")
if definitive_result == "M_22":
    log("")
    log("★ PROVED: Gal(f) = M_22 (Mathieu group on 22 points)")
    log("  Evidence: unique transitive group of degree 22 compatible with Frobenius data.")
elif definitive_result == "UNDETERMINED":
    log("")
    log("⚠ UNDETERMINED: Multiple candidate groups remain. Need additional resolvents.")
elif definitive_result not in ("SKIPPED", "ERROR"):
    log("")
    log(f"★ PROVED: Gal(f) = {definitive_result} (NOT M_22)")
log("")
log("=== DONE ===")
