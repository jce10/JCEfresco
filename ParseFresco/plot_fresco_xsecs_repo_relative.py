#!/usr/bin/env python3
"""
Repo-relative FRESCO angular-distribution plotter.

This version assumes your repo can contain a local experimental data folder:

    JCEfresco/
    ├── workdir/
    │   ├── 9Be6Lid_dwba/
    │   ├── 9Be6Lid_ccba/
    │   ├── 9Be6Lid_crc/
    │   ├── 9Be6Lid_cdcc/
    │   ├── 12Cdp_dwba/
    │   └── 12Cdp_cc/
    │   └── ...
    │
    ├── data/                  # add this to .gitignore
    │   ├── 6Lid/
    │   │   └── 9Be6Lid_10753keV_ang_dist.csv
    │   └── dp/
    │       └── 12Cdp_9500keV_ang_dist.csv
    │
    └── scripts/
        └── plot_fresco_xsecs_repo_relative.py

Example .gitignore entries:

    data/
    *.root
    *.parquet

Examples
--------
Plot 6Li,d DWBA + CDCC with automatically discovered experimental data:

    python scripts/plot_fresco_xsecs_repo_relative.py \
        --reaction 6Lid \
        --state 10753 \
        --models dwba cdcc \
        --scales cdcc=0.5

Plot all available 6Li,d models:

    python scripts/plot_fresco_xsecs_repo_relative.py \
        --reaction 6Lid \
        --state 8220 \
        --models dwba ccba crc cdcc

Plot 12C(d,p) DWBA + coupled-channels calculation:

    python scripts/plot_fresco_xsecs_repo_relative.py \
        --reaction dp \
        --state 9500 \
        --models dwba cc

Save instead of displaying:

    python scripts/plot_fresco_xsecs_repo_relative.py \
        --reaction 6Lid \
        --state 10753 \
        --models dwba cdcc \
        --out figures/9Be6Lid_10753keV.png
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Repo/root handling
# -----------------------------------------------------------------------------
REPO_MARKERS = (".git", "workdir")


def find_repo_root(start: Path | None = None) -> Path:
    """Find the repository root by walking upward from this script location."""
    if start is None:
        start = Path(__file__).resolve()

    start = start.resolve()
    candidates = [start] if start.is_dir() else list(start.parents)

    for directory in candidates:
        has_marker = any((directory / marker).exists() for marker in REPO_MARKERS)
        has_fresco_dirs = (directory / "workdir").exists()
        if has_marker and has_fresco_dirs:
            return directory

    raise FileNotFoundError(
        "Could not find repo root. Put this script inside the JCEfresco repo, "
        "or pass --repo /path/to/JCEfresco."
    )


def resolve_path(path: str | Path, repo: Path) -> Path:
    """Resolve absolute paths, cwd-relative paths, then repo-relative paths."""
    path = Path(path).expanduser()

    if path.is_absolute():
        return path

    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path.resolve()

    return (repo / path).resolve()


# -----------------------------------------------------------------------------
# Reaction metadata
# -----------------------------------------------------------------------------

REACTIONS = {
    "6lid": {
        "display": r"$^{9}$Be($^{6}$Li,d)$^{13}$C",
        "data_subdir": "6Lid",
        "exp_prefix": "9Be6Lid",
        "model_dirs": {
            "dwba": "9Be6Lid_dwba",
            "ccba": "9Be6Lid_ccba",
            "crc": "9Be6Lid_crc",
            "cdcc": "9Be6Lid_cdcc",
            "cdcc2": "9Be6Lid_cdcc2",
        },
        "default_state_files": {
            "dwba": "state1.txt",
            "ccba": "state1.txt",
            "crc": "state1.txt",
            "cdcc": "state32.txt",
            "cdcc2": "state34.txt",
        },
    },
    "dp": {
        "display": r"$^{12}$C(d,p)$^{13}$C",
        "data_subdir": "dp",
        "exp_prefix": "12Cdp",
        "model_dirs": {
            "dwba": "12Cdp_dwba",
            "cc": "12Cdp_cc",
        },
        "default_state_files": {
            "dwba": "state1.txt",
            "cc": "state1.txt",
        },
    },
}

REACTION_ALIASES = {
    "6lid": "6lid",
    "6li,d": "6lid",
    "9be6lid": "6lid",
    "9be(6li,d)": "6lid",
    "dp": "dp",
    "d,p": "dp",
    "12cdp": "dp",
    "12c(d,p)": "dp",
}

MODEL_ALIASES = {
    "coupled": "cc",
    "ccba_dp": "cc",
}


def normalize_reaction(reaction: str) -> str:
    key = reaction.strip().lower()
    try:
        return REACTION_ALIASES[key]
    except KeyError as exc:
        allowed = ", ".join(sorted(REACTIONS))
        raise ValueError(f"Unknown reaction {reaction!r}. Allowed reactions: {allowed}") from exc


def normalize_model(model: str, reaction: str) -> str:
    model_key = MODEL_ALIASES.get(model.strip().lower(), model.strip().lower())
    if model_key not in REACTIONS[reaction]["model_dirs"]:
        allowed = ", ".join(sorted(REACTIONS[reaction]["model_dirs"]))
        raise ValueError(
            f"Model {model!r} is not configured for reaction {reaction!r}. "
            f"Allowed models: {allowed}"
        )
    return model_key



def get_workdir_root(repo: Path) -> Path:
    return repo / "workdir"


def get_data_root(repo: Path) -> Path:
    return repo / "data"


def get_exp_path(repo: Path, reaction: str, state_keV: int) -> Path:
    """Return the default repo-local experimental angular-distribution path."""
    meta = REACTIONS[reaction]
    return (
        get_data_root(repo)
        / meta["data_subdir"]
        / f"{meta['exp_prefix']}_{state_keV}keV_ang_dist.csv"
    )


def get_fresco_path(
    repo: Path,
    reaction: str,
    model: str,
    state_keV: int,
    state_file: str | None = None,
) -> Path:
    """Return the default repo-relative parsed FRESCO state-file path."""
    meta = REACTIONS[reaction]
    model_dir = meta["model_dirs"][model]
    file_name = state_file or meta["default_state_files"][model]

    return get_workdir_root(repo) / model_dir / f"{state_keV}keV" / "fresco_dists" / file_name


# -----------------------------------------------------------------------------
# CLI parsing helpers
# -----------------------------------------------------------------------------


def parse_key_value_floats(items: Iterable[str] | None) -> dict[str, float]:
    result: dict[str, float] = {}
    if not items:
        return result

    for item in items:
        key, value = item.split("=", maxsplit=1)
        result[key.strip().lower()] = float(value)

    return result


def parse_key_value_strings(items: Iterable[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if not items:
        return result

    for item in items:
        key, value = item.split("=", maxsplit=1)
        result[key.strip().lower()] = value.strip()

    return result


# -----------------------------------------------------------------------------
# Data containers/loaders
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class FrescoCurve:
    reaction: str
    model: str
    state_keV: int
    scale: float = 1.0
    label: str | None = None
    state_file: str | None = None

    def path(self, repo: Path) -> Path:
        return get_fresco_path(
            repo=repo,
            reaction=self.reaction,
            model=self.model,
            state_keV=self.state_keV,
            state_file=self.state_file,
        )

    def plot_label(self) -> str:
        label = self.label or self.model.upper()
        if self.scale != 1.0:
            label += f" × {self.scale:g}"
        return label


def load_experiment_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"angle", "xsec", "xsec_err"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")
    return df


def load_fresco_curve(path: Path, thin: int = 3, theta_max: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, usecols=(0, 1))
    if thin > 1:
        data = data[::thin, :]
    if theta_max is not None:
        data = data[data[:, 0] <= theta_max]
    return data[:, 0], data[:, 1]


# -----------------------------------------------------------------------------
# Plotting
# -----------------------------------------------------------------------------


def plot_curves(
    repo: Path,
    reaction: str,
    state_keV: int,
    curves: list[FrescoCurve],
    exp_paths: list[Path],
    output: Path | None = None,
    title: str | None = None,
    logy: bool = True,
    thin: int = 3,
    theta_max: float | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 8))

    # Experimental angular distributions
    for exp_path in exp_paths:
        if not exp_path.exists():
            print(f"[skip] Missing experimental file: {exp_path}")
            continue

        df = load_experiment_csv(exp_path)
        ax.errorbar(
            df["angle"],
            df["xsec"],
            yerr=df["xsec_err"],
            fmt="o",
            capsize=4,
            markersize=6,
            linestyle="none",
            label=exp_path.stem,
        )

    # FRESCO calculations
    for curve in curves:
        path = curve.path(repo)
        if not path.exists():
            print(f"[skip] Missing {curve.model.upper()} file: {path}")
            continue

        theta_cm, xsec = load_fresco_curve(path, thin=thin, theta_max=theta_max)
        ax.plot(theta_cm, xsec * curve.scale, linewidth=2, label=curve.plot_label())

    ax.set_xlabel(r"$\theta_{CM}$ (deg)", fontsize=14)
    ax.set_ylabel(r"$d\sigma/d\Omega$", fontsize=14)

    if title:
        ax.set_title(title)
    else:
        ax.set_title(f"{REACTIONS[reaction]['display']}  {state_keV} keV")

    if logy:
        ax.set_yscale("log")

    # Set x-axis limits if theta_max is specified
    if theta_max is not None:
        ax.set_xlim(left=0, right=theta_max)

    ax.legend()
    ax.grid(True)
    plt.tight_layout()

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=300)
        print(f"[saved] {output}")
    else:
        plt.show()


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot experimental angular distributions with repo-relative FRESCO curves."
    )

    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Path to JCEfresco repo. Optional if script lives inside the repo.",
    )
    parser.add_argument(
        "--reaction",
        default="6Lid",
        help="Reaction to plot. Aliases in the form of A(a,b) with no \"(,)\". Examples: 12Cdp or 9Be6Lid .",
    )
    parser.add_argument(
        "--state",
        type=int,
        required=True,
        help="State energy in keV, e.g. 10753.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help=(
            "Models to plot. For 6Lid: dwba ccba crc cdcc. "
            "For dp: dwba cc. Defaults to all models for the chosen reaction."
        ),
    )
    parser.add_argument(
        "--scales",
        nargs="*",
        default=None,
        help="Optional model scale factors, e.g. dwba=1 cdcc=0.5 cc=2.0.",
    )
    parser.add_argument(
        "--state-files",
        nargs="*",
        default=None,
        help="Optional model state-file overrides, e.g. cdcc=state31.txt dwba=state2.txt.",
    )
    parser.add_argument(
        "--exp",
        nargs="*",
        default=None,
        help=(
            "Optional experimental CSV path(s). If omitted, the script tries "
            "data/<reaction>/<prefix>_<state>keV_ang_dist.csv automatically."
        ),
    )
    parser.add_argument(
        "--no-exp",
        action="store_true",
        help="Do not plot experimental data, even if the default data file exists.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Save figure to this path instead of showing it.",
    )
    parser.add_argument("--title", default=None, help="Optional plot title.")
    parser.add_argument(
        "--linear-y",
        action="store_true",
        help="Use linear y-axis instead of log scale.",
    )
    parser.add_argument(
        "--thin",
        type=int,
        default=3,
        help="Keep every Nth FRESCO point. Use --thin 1 to plot all points.",
    )
    parser.add_argument(
        "--theta-max",
        type=float,
        default=None,
        help="Maximum theta_cm to plot (degrees). Default is no limit.",
    )

    args = parser.parse_args()

    repo = args.repo.expanduser().resolve() if args.repo else find_repo_root()
    reaction = normalize_reaction(args.reaction)

    model_list = args.models
    if model_list is None:
        model_list = list(REACTIONS[reaction]["model_dirs"])

    models = [normalize_model(model, reaction) for model in model_list]
    scales = parse_key_value_floats(args.scales)
    state_files = parse_key_value_strings(args.state_files)

    curves = [
        FrescoCurve(
            reaction=reaction,
            model=model,
            state_keV=args.state,
            scale=scales.get(model, 1.0),
            state_file=state_files.get(model),
        )
        for model in models
    ]

    if args.no_exp:
        exp_paths: list[Path] = []
    elif args.exp is None:
        exp_paths = [get_exp_path(repo, reaction, args.state)]
    else:
        exp_paths = [resolve_path(path, repo) for path in args.exp]

    output = resolve_path(args.out, repo) if args.out else None

    print(f"[repo] {repo}")
    print(f"[reaction] {reaction}")
    print(f"[state] {args.state} keV")
    print(f"[models] {' '.join(models)}")
    for exp_path in exp_paths:
        print(f"[exp] {exp_path}")
    for curve in curves:
        print(f"[{curve.model}] {curve.path(repo)}  scale={curve.scale:g}")

    plot_curves(
        repo=repo,
        reaction=reaction,
        state_keV=args.state,
        curves=curves,
        exp_paths=exp_paths,
        output=output,
        title=args.title,
        logy=not args.linear_y,
        thin=args.thin,
        theta_max=args.theta_max,
    )


if __name__ == "__main__":
    main()
