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
    "/home/jce/Esparza_SPS/13CCampaign/6Lid/output_peak_files/9Be6Lid_6860keV_ang_dist.csv",
    # "/home/jce/Esparza_SPS/13CCampaign/6Lid/output_peak_files/9Be6Lid_7547keV_ang_dist.csv",
    # "/home/jce/Esparza_SPS/13CCampaign/6Lid/output_peak_files/9Be6Lid_7688keV_ang_dist.csv",
    # "/home/jce/Esparza_SPS/13CCampaign/6Lid/output_peak_files/9Be6Lid_8220keV_ang_dist.csv",
    # "/home/jce/Esparza_SPS/13CCampaign/6Lid/output_peak_files/9Be6Lid_8866keV_ang_dist.csv",
    # "/home/jce/Esparza_SPS/13CCampaign/6Lid/output_peak_files/9Be6Lid_9499keV_ang_dist.csv",
    # "/home/jce/Esparza_SPS/13CCampaign/6Lid/output_peak_files/9Be6Lid_9894keV_ang_dist.csv",
    "/home/jce/Esparza_SPS/13CCampaign/6Lid/output_peak_files/9Be6Lid_10753keV_ang_dist.csv",
    # "/home/jce18b/Esparza_SPS/2025_06_13C_campaign/dp/output_peak_files/12Cdp_9500keV_ang_dist.csv",
]


# ==========================================
# FRESCO post-parsed state files
#
# Format:
# ("path/to/state.txt", scale_factor, "plot label")
# ==========================================

states = [
    (
        # (6Li,d) 6.860 MeV DWBA
        "/home/jce/Programs/JCEfresco/jce/9Be6Lid_dwba/6860keV/fresco_dists/state1.txt",
        1.0,
        "DWBA 6860 keV",
    ),
    # (
    #     # (6Li,d) 6.860 MeV CRC
    #     "/home/jce/Programs/JCEfresco/jce/9Be6Lid_crc/6860keV/fresco_dists/state1.txt",
    #     1.0,
    #     "CRC 6860 keV",
    # ),
    # (
    #     # (6Li,d) 6.860 MeV CCBA
    #     "/home/jce/Programs/JCEfresco/jce/9Be6Lid_ccba/6860keV/fresco_dists/state1.txt",
    #     1.0,
    #     "CCBA 6860 keV",
    # ),
    (
        # (6Li,d) 6.860 MeV CDCC
        "/home/jce/Programs/JCEfresco/jce/9Be6Lid_cdcc/6860keV/fresco_dists/state32.txt",
        0.048,
        "CDCC 6860 keV",
    ),

# ~~~~~~~~~~~ #

    # (
    #     # (6Li,d) 7.688 MeV DWBA
    #     "/home/jce/Programs/JCEfresco/jce/9Be6Lid_dwba/7688keV/fresco_dists/state1.txt",
    #     1.0,
    #     "DWBA 7688 keV",
    # ),
    # (
    #     # (6Li,d) 7.688 MeV CRC
    #     "/home/jce/Programs/JCEfresco/jce/9Be6Lid_crc/6860keV/fresco_dists/state1.txt",
    #     1.0,
    #     "CRC 7688 keV",
    # ),
    # (
    #     # (6Li,d) 7.688 MeV CCBA
    #     "/home/jce/Programs/JCEfresco/jce/9Be6Lid_ccba/6860keV/fresco_dists/state1.txt",
    #     1.0,
    #     "CCBA 7688 keV",
    # ),
    # (
    #     # (6Li,d) 7.688 MeV CDCC
    #     "/home/jce/Programs/JCEfresco/jce/9Be6Lid_cdcc/7688keV/fresco_dists/state32.txt",
    #     1.55,
    #     "CDCC 7688 keV (x1.55)",
    # ),

# ~~~~~~~~~~~ #

    (
        # (6Li,d) 10.75 MeV DWBA
        "/home/jce/Programs/JCEfresco/jce/9Be6Lid_dwba/10753keV/fresco_dists/state1.txt",
        1.0,
        "DWBA 10753 keV",
    ),
    # (
    #     # (6Li,d) 10.75 MeV CRC
    #     "/home/jce/Programs/JCEfresco/jce/9Be6Lid_crc/6860keV/fresco_dists/state1.txt",
    #     1.0,
    #     "CRC 6860 keV",
    # ),
    # (
    #     # (6Li,d) 10.75 MeV CCBA
    #     "/home/jce/Programs/JCEfresco/jce/9Be6Lid_ccba/6860keV/fresco_dists/state1.txt",
    #     1.0,
    #     "CCBA 6860 keV",
    # ),
    (
        # (6Li,d) 10.75 MeV CDCC
        "/home/jce/Programs/JCEfresco/jce/9Be6Lid_cdcc/10753keV/fresco_dists/state32.txt",
        0.5,
        "CDCC 10753 keV (x0.5)",
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

