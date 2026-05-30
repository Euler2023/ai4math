from sage.all import *

# Define the character chi_{-4}
chi = DirichletGroup(4).0
print(f"Character chi: {chi.values_on_gens()}")

# Define Eisenstein forms of weight 4 with character chi
# There are multiple Eisenstein series. 
# The one satisfying L(g, 2) ~ G.
# L(E_k(chi_1, chi_2), s) = L(chi_1, s) * L(chi_2, s-k+1)
# We want L(g, 2) to involve G = L(chi_{-4}, 2).
# So chi_1 = chi_{-4} and s=2. 
# Then L(chi_1, 2) = G.
# L(chi_2, 2-4+1) = L(chi_2, -1).
# If chi_2 is the trivial character 1, then L(1, -1) = zeta(-1) = -1/12.
# So g = E_4(chi_{-4}, 1) should work.

# In Sage, Eisenstein series can be constructed:
E4_chi_1 = eisenstein_series_lseries(4, chi, DirichletGroup(4)(1))
print(f"g = E_4(chi, 1)")
print(f"Coefficients of g: {E4_chi_1.coefficients(10)}")

# Check L(g, 2)
# L(g, s) = L(chi, s) * zeta(s-3)
# L(g, 2) = L(chi, 2) * zeta(-1) = G * (-1/12)
G_val = float(RR(catalan))
L_g_2 = float(RR(chi.lfunction(2) * zeta(-1)))
print(f"L(g, 2) = {L_g_2}")
print(f"G * (-1/12) = {G_val * (-1/12)}")

