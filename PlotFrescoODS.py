import pandas as pd
import matplotlib.pyplot as plt
import re

# ---- load ODS ----
file_path = "/home/jce18b/Programs/JCEfresco/Exercises/fresconamelist/56Fedp/56Fedp.ods"
# file_path = "/home/jce18b/Programs/JCEfresco/Exercises/fresconamelist/56Fedp/56Fedp.ods"
# file_path = "/home/jce18b/Programs/JCEfresco/Exercises/fresconamelist/56Fedp/56Fedp.ods"

# read ODS "raw" with all the header and title info, then we'll clean it up later
raw = pd.read_excel(file_path, engine="odf", header=None)

# ---- Jpi value of state ----
ex_energy = str(raw.iloc[0, 0])  # Excitation energy (keV)
jpi = str(raw.iloc[0, 1])  # Jπ value as string, e.g. "5/2+"

match = re.match(r"(.+?)([+-])$", jpi)

if match:
    spin = match.group(1)        # spin "5/2"
    parity = match.group(2)   # parity "+/-"
else:
    raise ValueError(f"Could not parse Jπ from '{jpi}'")

print(f"Excitation energy: {ex_energy}")
print(r'$J^{\pi}$ = ' + spin + parity)


# ---- promote header row ----
df = raw.iloc[2:].copy()      # data starts at row 2
df.columns = raw.iloc[1]      # row 1 becomes column names
df = df.reset_index(drop=True)

# clean column names (just in case)
df.columns = df.columns.astype(str).str.strip()

print(df.columns.tolist())  # should now include "angle"

# ---- pick columns to plot ----
x = df["angle"]

for col in df.columns:
    if col.startswith("xsec"):
        ell = col.replace("xsec", "")

        if len(ell) > 1:
            label = r"$\ell = " + " + ".join(list(ell)) + "$"
        else:
            label = rf"$\ell = {ell}$"

        plt.plot(x, df[col], "o-", label=label)

plt.yscale("log")
plt.legend(title="Transfer ℓ")
plt.xlabel(r"$\Theta_{\mathrm{CM}}$ (deg)")
plt.ylabel(r"$\frac{d\sigma}{d\Omega}$ (mb/sr)")
plt.title(rf"${ex_energy}\ \mathrm{{keV}},\ {spin}^{{{parity}}}$")
plt.grid(True)
plt.show()