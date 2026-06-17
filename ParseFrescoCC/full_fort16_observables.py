#!/usr/bin/env python3
"""
plot_fort16_observables.py

Fresh FRESCO fort.16 parser.

Reads raw fort.16 blocks with columns:

theta  sigma  iT11  T20  T21  T22

Then plots either:
  - grid mode: sigma + analyzing powers
  - single mode: one observable
"""

from pathlib import Path
import re

import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# USER SETTINGS
# ============================================================

# user-defiend path to fort.16 file
root_dir = Path("/home/jce18b/Programs/JCEfresco")


# fort16_path = "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/10750keV_short/fort.16"
# fort16_path = "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/10753keV_short2/fort.16"
# state_index = 32


# 12C(d,p) DWBA 
# fort16_path = "/home/jce18b/Programs/JCEfresco/jce/12Cdp/GS/dwba/fort.16"
# state_index = 1

# 12C(d,p) namelist conversion test
# fort16_path = root_dir / "12Cdp" / "namelist_conversion_test" / "fort.16"
# state_index = 1

# 12C(d,p) namelist conversion test
# fort16_path = root_dir / "12Cdp" / "namelist_conversion_test" / "fort.16"
# state_index = 1


# 25Al(d,n) CDCC
fort16_path = root_dir / "exercises" / "25Aldn_CDCC" / "fort.16"
state_index = 9

# user specifies state index to plot (0-based)
# state_index = 1
plot_mode = "grid"        # "grid" or "single"
observable = "sigma"      # "sigma", "iT11", "T20", "T21", "T22"

use_log_for_sigma = True


# ============================================================
# PARSER
# ============================================================

def clean_label(line: str | None, index: int) -> str:
    if line is None:
        return f"distribution {index}"

    match = re.search(r'"(.*?)"', line)
    if match:
        return match.group(1)

    return line.strip()


def find_fort16_blocks(filepath):
    """
    Find all raw FRESCO fort.16 distribution blocks.

    Expected block pattern:

        @legend string N "Partition= ..."
        #  Theta sigma iT11 T20 T21 T22 ...
        data rows with 6 numeric columns
    """
    filepath = Path(filepath)
    lines = filepath.read_text().splitlines()

    blocks = []

    current_label = None
    current_header = None
    current_data = []
    inside_block = False

    for line in lines:
        stripped = line.strip()

        # Save label for the next block
        if stripped.startswith("@legend string"):
            current_label = stripped
            continue

        # Start a data block
        if stripped.startswith("#") and "Theta" in stripped and "sigma" in stripped:
            current_header = stripped
            current_data = []
            inside_block = True
            continue

        # Collect numeric data
        if inside_block:
            # A new xmgrace command or comment means the block ended
            if stripped.startswith("@") or stripped.startswith("#") or stripped == "":
                if current_data:
                    blocks.append(
                        {
                            "label": current_label,
                            "header": current_header,
                            "data_lines": current_data,
                        }
                    )

                current_data = []
                current_header = None
                inside_block = False

                if stripped.startswith("@legend string"):
                    current_label = stripped

                continue

            parts = stripped.split()

            # Raw fort.16 should have at least 6 columns:
            # theta sigma iT11 T20 T21 T22
            if len(parts) >= 6:
                current_data.append(stripped)

    # Catch final block if file ends during data
    if inside_block and current_data:
        blocks.append(
            {
                "label": current_label,
                "header": current_header,
                "data_lines": current_data,
            }
        )

    return blocks


def parse_fort16_block(block):
    """
    Parse one raw fort.16 block.

    Raw FRESCO fort.16 columns:
        0 theta
        1 sigma
        2 iT11
        3 T20
        4 T21
        5 T22
    """
    data = np.loadtxt(block["data_lines"])

    if data.ndim == 1:
        data = data.reshape(1, -1)

    if data.shape[1] < 6:
        raise ValueError(
            f"Expected at least 6 columns, but got shape {data.shape}."
        )

    return {
        "theta_cm": data[:, 0],
        "sigma": data[:, 1],
        "iT11": data[:, 2],
        "T20": data[:, 3],
        "T21": data[:, 4],
        "T22": data[:, 5],
    }


def print_available_distributions(blocks):
    print()
    print(f"Found {len(blocks)} fort.16 distributions")
    print("-" * 70)

    for i, block in enumerate(blocks):
        label = clean_label(block["label"], i)
        n_points = len(block["data_lines"])
        print(f"[{i:3d}] {label}   ({n_points} points)")

    print("-" * 70)
    print()


# ============================================================
# PLOTTING
# ============================================================

def plot_single(parsed, label, observable, use_log_for_sigma=True):
    theta = parsed["theta_cm"]
    y = parsed[observable]

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.plot(theta, y, linewidth=2)

    ax.set_xlabel(r"$\theta_{\mathrm{CM}}$ (deg)", fontsize=14)

    if observable == "sigma":
        ax.set_ylabel(r"$d\sigma/d\Omega$ (mb/sr)", fontsize=14)

        if use_log_for_sigma:
            ax.set_yscale("log")
    else:
        ax.set_ylabel(observable, fontsize=14)

    ax.set_title(label, fontsize=12)
    ax.grid(True)

    plt.tight_layout()
    plt.show()


def plot_grid(parsed, label, use_log_for_sigma=True):
    observables = ["sigma", "iT11", "T20", "T21", "T22"]

    fig, axes = plt.subplots(3, 2, figsize=(11, 10))
    axes = axes.flatten()

    theta = parsed["theta_cm"]

    for ax, obs in zip(axes, observables):
        ax.plot(theta, parsed[obs], linewidth=2)

        ax.set_xlabel(r"$\theta_{\mathrm{CM}}$ (deg)")

        if obs == "sigma":
            ax.set_ylabel(r"$d\sigma/d\Omega$ (mb/sr)")

            if use_log_for_sigma:
                ax.set_yscale("log")
        else:
            ax.set_ylabel(obs)

        ax.grid(True)

    # empty sixth panel
    axes[-1].axis("off")

    fig.suptitle(label, fontsize=14)

    plt.tight_layout()
    plt.show()


# ============================================================
# MAIN
# ============================================================

def main():
    valid_observables = ["sigma", "iT11", "T20", "T21", "T22"]

    blocks = find_fort16_blocks(fort16_path)

    if not blocks:
        raise RuntimeError(
            "No fort.16 distributions found. "
            "Check that this is a raw FRESCO fort.16 file with '# Theta sigma ...' headers."
        )

    print_available_distributions(blocks)

    if state_index < 0 or state_index >= len(blocks):
        raise IndexError(
            f"state_index={state_index} is out of range. "
            f"Valid range: 0 to {len(blocks) - 1}"
        )

    if observable not in valid_observables:
        raise ValueError(
            f"observable='{observable}' is invalid. "
            f"Choose from {valid_observables}."
        )

    selected_block = blocks[state_index]
    label = clean_label(selected_block["label"], state_index)
    parsed = parse_fort16_block(selected_block)

    if plot_mode == "grid":
        plot_grid(parsed, label, use_log_for_sigma)

    elif plot_mode == "single":
        plot_single(parsed, label, observable, use_log_for_sigma)

    else:
        raise ValueError("plot_mode must be 'grid' or 'single'.")


if __name__ == "__main__":
    main()