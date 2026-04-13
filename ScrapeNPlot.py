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



def scrape_fort16_sections(file_path: str | Path, ncols: int | None = None, verbose: bool = True):
    """
    Scrape a FRESCO fort.16/fort.201-style file into separate reaction sections.

    Assumes:
    - numeric rows belong to the current cross section block
    - blocks are separated by lines containing 'END'
    - non-numeric text before a block is treated as that block's header
    - sections
        0: elastic scattering
        1: first transfer (d,p)
        2: other rxns

    Parameters
    ----------
    file_path : str or Path
        Path to the FRESCO output file.
    ncols : int or None
        If set, truncate numeric rows to the first ncols columns.
    verbose : bool
        If True, print section summaries to terminal.

    Returns
    -------
    sections : list of dict
        Each entry contains:
        {
            "header": str,
            "data": pl.DataFrame
        }
    """
    file_path = Path(file_path)

    sections = []
    current_data = []
    current_header_lines = []

    def finalize_section():
        nonlocal current_data, current_header_lines, sections

        if not current_data:
            current_header_lines = []
            return

        # make all rows same length, if needed
        min_len = min(len(row) for row in current_data)
        trimmed_data = [row[:min_len] for row in current_data]

        if ncols is not None:
            trimmed_data = [row[:ncols] for row in trimmed_data]
            min_len = min(min_len, ncols)

        cols = [f"col{i}" for i in range(min_len)]
        df = pl.DataFrame(trimmed_data, schema=cols, orient="row")

        header = " | ".join(current_header_lines).strip()
        sections.append({
            "header": header,
            "data": df
        })

        current_data = []
        current_header_lines = []

    with open(file_path, "r") as f:
        for line in f:
            stripped = line.strip()

            # section separator
            if stripped == "END":
                finalize_section()
                continue

            # try numeric parse
            parts = stripped.split()
            try:
                row = [float(x) for x in parts]
                current_data.append(row)
            except ValueError:
                # only store non-empty text as possible header info
                if stripped:
                    current_header_lines.append(stripped)

    # finalize last section in case file does not end with END
    finalize_section()

    if verbose:
        print(f"\nFound {len(sections)} section(s) in {file_path.name}\n")
        for i, sec in enumerate(sections):
            df = sec["data"]
            header = sec["header"] if sec["header"] else "[no header captured]"

            if df.height > 0:
                theta_min = df["col0"].min()
                theta_max = df["col0"].max()
                print(f"Section {i}:")
                print(f"  Header      : {header}")
                print(f"  Theta range : {theta_min:.2f} -> {theta_max:.2f} deg")
                print(f"  Rows        : {df.height}")
                print(f"  Columns     : {df.width}\n")
            else:
                print(f"Section {i}: empty\n")

    return sections


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