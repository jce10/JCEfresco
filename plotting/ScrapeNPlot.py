"""

Functions to scrape and plot fort.XXX files from FRESCO calculations.
Created to complete the exercises provided by Nick Keeley (I think) for his 
FRESCO workshop at the National Centre for Nuclear Research. Swierk, Poland.

J. C. Esparza 2026

"""


import polars as pl
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np
import re

# scrape Elastic Scattering
def scrape_fort(file_path: str | Path, ncols=None):
    data = []
    with open(file_path, "r") as f:
        for line in f:
            try:
                row = [float(x) for x in line.split()]
                if ncols:
                    row = row[:ncols]
                data.append(row)
            except ValueError:
                continue

    cols = [f"col{i}" for i in range(len(data[0]))]
    return pl.DataFrame(data, schema=cols, orient="row")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #

def scrape_fort16_sections(
    file_path: str | Path,
    ncols: int | None = 2,
    verbose: bool = True,
    output_file: str | Path | None = None,
):
    """
    Scrape a FRESCO fort.16 style file into separate reaction sections
    and optionally write all sections to one CSV file.

    Output format:
    section,angle,xsec
    @s0,0.01,1.0
    @s0,0.5,1.004
    ...
    """

    file_path = Path(file_path)

    if output_file is not None:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

    sections = []
    current_data = []
    current_header_lines = []
    section_idx = 0

    def finalize_section():
        nonlocal current_data, current_header_lines, sections, section_idx

        if not current_data:
            current_header_lines = []
            return

        min_len = min(len(row) for row in current_data)
        trimmed_data = [row[:min_len] for row in current_data]

        if ncols is not None:
            trimmed_data = [row[:ncols] for row in trimmed_data]
            min_len = min(min_len, ncols)

        cols = [f"col{i}" for i in range(min_len)]
        df = pl.DataFrame(trimmed_data, schema=cols, orient="row")

        header = " | ".join(current_header_lines).strip()

        match = re.search(r"@s\d+", header)
        if match:
            section_tag = match.group(0)
        else:
            section_tag = f"@s{section_idx}"

        sections.append({
            "section_tag": section_tag,
            "header": header,
            "data": df
        })

        section_idx += 1
        current_data = []
        current_header_lines = []

    with open(file_path, "r") as f:
        for line in f:
            stripped = line.strip()

            if stripped == "END":
                finalize_section()
                continue

            parts = stripped.split()
            try:
                row = [float(x) for x in parts]
                current_data.append(row)
            except ValueError:
                if stripped:
                    current_header_lines.append(stripped)

    finalize_section()

    # 🔥 WRITE ONE BIG CSV FILE
    if output_file is not None:
        rows = []

        for sec in sections:
            tag = sec["section_tag"]
            df = sec["data"]

            for row in df.iter_rows():
                if len(row) >= 2:
                    rows.append({
                        "section": tag,
                        "angle": row[0],
                        "xsec": row[1],
                    })

        out_df = pl.DataFrame(rows)
        out_df.write_csv(output_file)

        if verbose:
            print(f"  → Saved CSV file: {output_file.name}")

    if verbose:
        print(f"\nFound {len(sections)} section(s) in {file_path.name}\n")
        for i, sec in enumerate(sections):
            df = sec["data"]

            if df.height > 0:
                theta_min = df["col0"].min()
                theta_max = df["col0"].max()
                print(f"Section {i}:")
                print(f"  Tag         : {sec['section_tag']}")
                print(f"  Theta range : {theta_min:.2f} -> {theta_max:.2f} deg")
                print(f"  Rows        : {df.height}\n")
            else:
                print(f"Section {i}: empty\n")

    return sections


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #

# plot the distribution
def plot_distribution(df, xcol="col0", ycol="col1",
                      skip=0, label=None, title=None):
    x = df[xcol].to_numpy()[skip:]
    y = df[ycol].to_numpy()[skip:]

    plt.plot(x, y, "o-", label=label)
    plt.yscale("log")
    plt.xlabel(r"$\Theta_{\mathrm{C.M.}}$ (degrees)")
    plt.ylabel(r"$d\sigma/d\Omega$ (mb/sr)")
    if title:
        plt.title(title)
    if label:
        plt.legend()
    plt.grid(True)



    # plot the distribution
def plot_distribution_16(df, xcol="col0", ycol="col1",
                      skip=0, label=None, title=None, ax=None):

    if ax is None:
        ax = plt.gca()

    x = df[xcol].to_numpy()[skip:]
    y = df[ycol].to_numpy()[skip:]

    ax.plot(x, y, "o-", label=label)
    ax.set_yscale("log")
    ax.set_xlabel(r"$\Theta_{\mathrm{C.M.}}$ (degrees)")
    ax.set_ylabel(r"$d\sigma/d\Omega$ (mb/sr)")

    if title:
        ax.set_title(title)

    if label:
        ax.legend()

    ax.grid(True)

    return ax


def plot_sections_individually(sections, xcol="col0", ycol="col1", skip=0,
                               use_headers=False):
    for i, sec in enumerate(sections):
        df = sec["data"]

        if df.height == 0:
            print(f"Skipping Section {i}: empty")
            continue

        x = df[xcol].to_numpy()[skip:]
        y = df[ycol].to_numpy()[skip:]
        y = np.where(y <= 0, np.nan, y)

        if use_headers and sec["header"].strip():
            label = sec["header"]
            title = sec["header"]
        else:
            label = f"Section {i}"
            title = f"FRESCO Section {i}"

        plt.figure(figsize=(8, 6))
        plt.plot(x, y, "o-", label=label)
        plt.yscale("log")
        plt.xlabel(r"$\Theta_{\mathrm{C.M.}}$ (degrees)")
        plt.ylabel(r"$d\sigma/d\Omega$ (mb/sr)")
        plt.title(title)
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()

        print(
            f"Displayed Section {i}: "
            f"{len(x)} points, theta = {np.nanmin(x):.2f} -> {np.nanmax(x):.2f}"
        )

def plot_section_from_csv_dir(
    csv_dir,
    section_tag="@s1",
    pattern="*.csv",
    sort_angles=True,
):
    """
    Plot angle vs xsec for a given section (default @s1)
    from all CSV files in a directory.

    Parameters
    ----------
    csv_dir : str or Path
        Directory containing CSV files.
    section_tag : str
        Section to filter (e.g. "@s1").
    pattern : str
        Glob pattern for CSV files (default "*.csv").
    sort_angles : bool
        If True, sort data by angle before plotting.
    """

    csv_dir = Path(csv_dir)
    csv_files = csv_dir.glob(pattern)

    for file in csv_files:
        df = pl.read_csv(file)

        sub = df.filter(pl.col("section") == section_tag)

        if sub.is_empty():
            continue

        if sort_angles:
            sub = sub.sort("angle")

        plt.plot(
            sub["angle"],
            sub["xsec"],
            "o",
            label=file.stem
        )

    plt.yscale("log")
    plt.legend()
    plt.xlabel("Angle")
    plt.ylabel("Cross section")
    plt.grid(True, which="both", ls="--", alpha=0.5)
    plt.show()