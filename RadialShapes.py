import numpy as np
import matplotlib.pyplot as plt

# ---------- Woods–Saxon ----------
def woods_saxon(r, R, a):
    return 1.0 / (1.0 + np.exp((r - R) / a))

def d_woods_saxon(r, R, a):
    f = woods_saxon(r, R, a)
    return -(f * (1 - f)) / a

# ---------- radius grid ----------
r = np.linspace(0, 12, 400)

# Example geometry (use your Ni values)
A = 58
R_vol = 1.325 * A**(1/3)
a_vol = 0.786

R_surf = 1.325 * A**(1/3)
a_surf = 0.786

# ---------- compute shapes ----------
f_vol = woods_saxon(r, R_vol, a_vol)
f_surf = d_woods_saxon(r, R_surf, a_surf)

# ---------- plot ----------
plt.figure(figsize=(6,4))

plt.plot(r, f_vol, label="Volume imag ∝ f(r)")
plt.plot(r, f_surf, label="Surface imag ∝ df/dr")

plt.xlabel("r (fm)")
plt.ylabel("Radial form")
plt.title("OMP radial shapes — feel the difference")
plt.legend()
plt.grid(True)

plt.show()
