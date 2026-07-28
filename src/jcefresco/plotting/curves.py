from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def load_experiment_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"angle", "xsec", "xsec_err"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")
    return frame


def load_fresco_curve(
    path: Path,
    *,
    thin: int = 3,
    theta_max: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    if thin < 1:
        raise ValueError("thin must be at least 1")

    data = np.loadtxt(path, usecols=(0, 1), ndmin=2)
    data = data[::thin]
    if theta_max is not None:
        data = data[data[:, 0] <= theta_max]
    if data.size == 0:
        raise ValueError(f"No FRESCO points remain after filtering {path}")
    return data[:, 0], data[:, 1]
