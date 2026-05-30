from sage.all import *
chi = DirichletGroup(4).0
print(f"chi(-1) = {chi(-1)}")
M = ModularForms(chi, 4)
print(f"Dimension of M_4(chi): {M.dimension()}")
E = EisensteinForms(chi, 4)
print(f"Dimension of E_4(chi): {E.dimension()}")

# What about chi = trivial?
chi0 = DirichletGroup(4)(1)
M0 = ModularForms(chi0, 4)
print(f"Dimension of M_4(1): {M0.dimension()}")

# What about weight 3?
M3 = ModularForms(chi, 3)
print(f"Dimension of M_3(chi): {M3.dimension()}")
