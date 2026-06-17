# WITH scaling

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd


# ==========================================
# Experimental / calculated angular distributions
# CSV columns expected:
# angle, xsec, xsec_err
# ==========================================

ang_dists = [
    "/home/jce18b/Esparza_SPS/2025_06_13C_campaign/6Lid/output_peak_files/9Be6Lid_6860keV_ang_dist.csv",
    # "/home/jce18b/Esparza_SPS/2025_06_13C_campaign/6Lid/output_peak_files/9Be6Lid_10753keV_ang_dist.csv",
    # "/home/jce18b/Esparza_SPS/2025_06_13C_campaign/dp/output_peak_files/12Cdp_9500keV_ang_dist.csv",
]


# ==========================================
# FRESCO post-parsed state files
#
# Format:
# ("path/to/state.txt", scale_factor, "plot label")
# ==========================================

# states = [
#     (
#         # (6Li,d) 10.75 MeV DWBA
#         "/home/jce18b/Esparza_SPS/2025_06_13C_campaign/6Lid/9Be6Lid_fresco/10753keV/fresco_dists/state1.txt",
#         1.0,
#         "DWBA state1",
#     ),
#     (
#         # (6Li,d) 10.75 MeV CDCC
#         # "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/10750keV_short/fresco_dists/state32.txt",
#         # 100.0,
#         # "CDCC state32 x100",

#         "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/10753keV_short2/fresco_dists/state32.txt",
#         1.0,
#         "CDCC state32",
#     ),
# ]

# states = [
#     (
#         # (6Li,d) 10.75 MeV DWBA
#         "/home/jce18b/Esparza_SPS/2025_06_13C_campaign/6Lid/9Be6Lid_fresco/10753keV/fresco_dists/state1.txt",
#         1.0,
#         "DWBA state1",
#     ),
#     (
#         # (6Li,d) 10.75 MeV CDCC
#         "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/10753keV/fresco_dists/state32.txt",
#         50.0,
#         "CDCC state32 x100",

#         # "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/10753keV/fresco_dists/state32.txt",
#         # 1.0,
#         # "CDCC state32",
#     ),
# ]

states = [
    (
        # (6Li,d) 6.860 MeV DWBA
        "/home/jce18b/Esparza_SPS/2025_06_13C_campaign/6Lid/9Be6Lid_fresco/6860keV/fresco_dists/state1.txt",
        10.0,
        "DWBA 6860 keV",
    ),
    (
        # (6Li,d) 10.75 MeV CDCC
        "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/6860keV/fresco_dists/state32.txt",
        10.0,
        "CDCC 6860 keV(x10)",

        # "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/10753keV/fresco_dists/state32.txt",
        # 1.0,
        # "CDCC state32",
    ),
]


# ==========================================
# Create figure
# ==========================================

fig, ax = plt.subplots(figsize=(10, 8))


# ==========================================
# Plot angular distribution CSVs
# ==========================================

for filepath in ang_dists:
    filepath = Path(filepath)

    df = pd.read_csv(filepath)

    theta_cm = df["angle"]
    xsec = df["xsec"]
    xsec_err = df["xsec_err"]

    label = filepath.stem

    ax.errorbar(
        theta_cm,
        xsec,
        yerr=xsec_err,
        fmt="o",
        capsize=4,
        markersize=6,
        linestyle="none",
        label=label,
    )


# ==========================================
# Plot FRESCO curves
# ==========================================

for filepath, scale, label in states:
    filepath = Path(filepath)

    data = np.loadtxt(filepath, usecols=(0, 1))

    # For post-parsed 2-column FRESCO observable files
    data = data[::3, :]

    theta_cm = data[:, 0]
    xsec = data[:, 1] * scale

    ax.plot(
        theta_cm,
        xsec,
        linewidth=2,
        label=label,
    )


# ==========================================
# Plot formatting
# ==========================================

ax.set_xlabel(r"$\theta_{CM}$ (deg)", fontsize=14)
ax.set_ylabel(r"$d\sigma/d\Omega$", fontsize=14)

ax.set_yscale("log")

ax.legend()
ax.grid(True)

plt.tight_layout()
plt.show()



# NO scaling

# from pathlib import Path

# import numpy as np
# import matplotlib.pyplot as plt
# import pandas as pd



# # ==========================================
# # Experimental / calculated angular distributions
# # CSV columns expected:
# # angle, xsec, xsec_err
# # ==========================================
# ang_dists = [
#     "/home/jce18b/Esparza_SPS/2025_06_13C_campaign/6Lid/output_peak_files/9Be6Lid_10753keV_ang_dist.csv",
# ]

# # ==========================================
# # List your state files here
# # ==========================================

# states = [
#     # "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/10750keV_short/fresco_dists/state31.txt",
#     "/home/jce18b/Esparza_SPS/2025_06_13C_campaign/6Lid/9Be6Lid_fresco/10753keV/fresco_dists/state1.txt",
#     "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/10750keV_short/fresco_dists/state32.txt"
# ]


# # ==========================================
# # Create figure
# # ==========================================

# fig, ax = plt.subplots(figsize=(8, 6))


# # ==========================================
# # Plot angular distribution CSVs
# # ==========================================

# for filepath in ang_dists:
#     filepath = Path(filepath)

#     df = pd.read_csv(filepath)

#     theta_cm = df["angle"]
#     xsec = df["xsec"]
#     xsec_err = df["xsec_err"]

#     label = filepath.stem

#     ax.errorbar(
#         theta_cm,
#         xsec,
#         yerr=xsec_err,
#         fmt="o",
#         capsize=4,
#         markersize=6,
#         linestyle="none",
#         label=label,
#     )


# # ==========================================
# # Plot FRESCO curves
# # ==========================================

# for filepath in states:
#     filepath = Path(filepath)

#     data = np.loadtxt(filepath, usecols=(0, 1))

#     # For post-parsed 2-column FRESCO observable files
#     data = data[::3, :]

#     theta_cm = data[:, 0]
#     xsec = data[:, 1]

#     label = filepath.stem

#     ax.plot(
#         theta_cm,
#         xsec,
#         linewidth=2,
#         label=label,
#     )


# # ==========================================
# # Plot formatting
# # ==========================================

# ax.set_xlabel(r"$\theta_{CM}$ (deg)", fontsize=14)
# ax.set_ylabel(r"$d\sigma/d\Omega$", fontsize=14)

# ax.set_yscale("log")

# ax.legend()
# ax.grid(True)

# plt.tight_layout()
# plt.show()