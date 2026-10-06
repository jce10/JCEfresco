from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from ..config import ProjectConfig
from ..reactions import ReactionConfig, parsed_state_path
from .curves import load_experiment_csv, load_fresco_curve


@dataclass(frozen=True)
class FrescoCurve:
    model: str
    state_keV: int
    scale: float = 1.0
    label: str | None = None
    state_file: str | None = None
    linestyle: str = "--"

    def path(self, config: ProjectConfig, reaction: ReactionConfig) -> Path:
        return parsed_state_path(
            config,
            reaction,
            self.model,
            self.state_keV,
            self.state_file,
        )

    def plot_label(self) -> str:
        label = self.label or self.model.upper()
        return f"{label} × {self.scale:g}" if self.scale != 1.0 else label


@dataclass(frozen=True)
class FrescoBand:
    model: str
    state_keV: int
    low_file: str
    high_file: str
    label: str = r"$1\sigma$"
    alpha: float = 0.22

    def paths(self, config: ProjectConfig, reaction: ReactionConfig) -> tuple[Path, Path]:
        low = parsed_state_path(config, reaction, self.model, self.state_keV, self.low_file)
        high = parsed_state_path(config, reaction, self.model, self.state_keV, self.high_file)
        return low, high


def plot_angular_distribution(
    config: ProjectConfig,
    reaction: ReactionConfig,
    state_keV: int,
    curves: list[FrescoCurve],
    exp_paths: list[Path],
    *,
    bands: list[FrescoBand] | None = None,
    exp_labels: list[str] | None = None,
    output: Path | None = None,
    title: str | None = None,
    logy: bool = True,
    thin: int = 3,
    theta_max: float | None = None,
    x_min: float | None = None,
    x_max: float | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 8))

    for i, exp_path in enumerate(exp_paths):
        if not exp_path.is_file():
            print(f"[skip] missing experimental file: {exp_path}")
            continue
        frame = load_experiment_csv(exp_path)
        ax.errorbar(
            frame["angle"],
            frame["xsec"],
            yerr=frame["xsec_err"],
            fmt="o",
            capsize=4,
            markersize=6,
            linestyle="none",
            label=exp_labels[i] if exp_labels and i < len(exp_labels) else exp_path.stem,
        )

    for band in bands or []:
        low_path, high_path = band.paths(config, reaction)
        if not low_path.is_file() or not high_path.is_file():
            print(
                f"[skip] missing uncertainty band file(s): {low_path}, {high_path}"
            )
            continue
        theta_low, xsec_low = load_fresco_curve(
            low_path, thin=thin, theta_max=theta_max
        )
        theta_high, xsec_high = load_fresco_curve(
            high_path, thin=thin, theta_max=theta_max
        )
        if theta_low.shape != theta_high.shape or not np.allclose(theta_low, theta_high):
            # FRESCOX normally writes identical angular grids.  Interpolate the
            # high boundary onto the low grid if a future calculation differs.
            xsec_high = np.interp(theta_low, theta_high, xsec_high)
            theta = theta_low
        else:
            theta = theta_low
        lower = np.minimum(xsec_low, xsec_high)
        upper = np.maximum(xsec_low, xsec_high)
        ax.fill_between(
            theta, lower, upper, alpha=band.alpha, linewidth=0, label=band.label
        )

    for curve in curves:
        path = curve.path(config, reaction)
        if not path.is_file():
            print(f"[skip] missing {curve.model.upper()} file: {path}")
            continue
        theta_cm, xsec = load_fresco_curve(path, thin=thin, theta_max=theta_max)
        ax.plot(
            theta_cm,
            xsec * curve.scale,
            linewidth=2,
            linestyle=curve.linestyle,
            label=curve.plot_label(),
        )

    ax.set_xlabel(r"$\theta_{CM}$ (deg)", fontsize=17)
    ax.set_ylabel(r"$d\sigma/d\Omega$ (mb/sr)", fontsize=17)
    ax.tick_params(axis="both", which="major", labelsize=15)
    # ax.set_title(title or f"{reaction.display}  {state_keV} keV")
    

    if logy:
        ax.set_yscale("log")

    resolved_x_max = x_max if x_max is not None else theta_max
    if x_min is not None or resolved_x_max is not None:
        ax.set_xlim(left=x_min, right=resolved_x_max)
    if y_min is not None or y_max is not None:
        ax.set_ylim(bottom=y_min, top=y_max)

    ax.legend(fontsize=17)
    ax.grid(True)
    fig.tight_layout()

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=300, bbox_inches="tight")
        print(f"[saved] {output}")
        plt.close(fig)
    else:
        plt.show()
