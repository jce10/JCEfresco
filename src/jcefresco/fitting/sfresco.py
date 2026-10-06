from __future__ import annotations

"""SFRESCOX spectroscopic-amplitude fitting for JCEfresco.

The fitting layer is intentionally additive: it imports JCEfresco's existing
configuration, plotting-data loader, fort.16 splitter, and fort.3/fort.16
bookkeeping parsers without changing their public behavior.

The native SFRESCOX ``kind=2`` variable is used to vary one ordered ``&CFP``
spectroscopic amplitude (``nafrac`` / ``afrac``).  After the minimization, an
ordinary best-fit FRESCOX input is written and, unless disabled, run once in an
isolated fit directory.  Its ``fort.16`` is then split by JCEfresco's existing
``split_fort16`` function and the selected best-fit curve is copied into the
normal calculation's ``fresco_dists`` directory under a non-destructive name.
"""

from dataclasses import dataclass
from pathlib import Path
import json
import math
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from typing import Callable, Iterable, Sequence

import numpy as np

from ..parser.fort16 import split_fort16
from ..parser.xsec_map_parser import CFPInfo, CurveInfo, build_cross_section_map, parse_fort3, parse_fort16
from ..plotting.curves import load_experiment_csv, load_fresco_curve


_FLOAT_RE_TEXT = r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[EeDd][+-]?\d+)?"
_FLOAT_RE = re.compile(_FLOAT_RE_TEXT)
_STATE_FILE_RE = re.compile(r"^state(?P<number>\d+)\.txt$", re.IGNORECASE)


@dataclass(frozen=True)
class ExperimentalPoint:
    angle: float
    xsec: float
    xsec_err: float


@dataclass(frozen=True)
class NumberedCFP:
    """A fort.3 CFP entry plus its 1-based SFRESCOX ``nafrac`` number."""

    number: int
    info: CFPInfo

    @property
    def physical_in(self) -> int:
        # FRESCOX convention: IN<0 marks the final &cfp, while abs(IN) retains
        # the projectile/target meaning.  Thus IN=-2 is still the target CFP.
        return abs(self.info.partition)

    def short_label(self) -> str:
        return (
            f"CFP #{self.number}: IN={self.info.partition} "
            f"IB={self.info.final_state} IA={self.info.core_state} "
            f"KN={self.info.overlap_kn} A={self.info.amplitude:g}"
        )


@dataclass(frozen=True)
class ScanPoint:
    amplitude: float
    reduced_chisq: float


@dataclass(frozen=True)
class ScanEstimate:
    """Continuous best-fit estimate from a local SFRESCOX scan."""

    amplitude: float
    amplitude_error: float | None
    reduced_chisq_estimate: float
    discrete_best: ScanPoint
    points_used: tuple[ScanPoint, ...]


@dataclass(frozen=True)
class CurveChiSquare:
    chisq: float
    reduced_chisq: float
    n_points: int
    max_abs_pull: float


@dataclass(frozen=True)
class AmplitudeScalingCheck:
    """Diagnostic for the single-amplitude ``sigma proportional A^2`` rule.

    The comparison rescales a reference FRESCOX curve from ``A_ref`` to
    ``A_best`` and compares it with the independently calculated best-fit
    curve. Small differences are expected from solver/interpolation noise;
    large or angle-dependent differences mean a constant-fractional
    uncertainty band is not justified.
    """

    passed: bool
    rms_relative_difference: float
    max_relative_difference: float
    expected_cross_section_ratio: float
    points_compared: int


@dataclass(frozen=True)
class ProfileInterval:
    """One-parameter profile-chi-square confidence interval.

    ``lower`` and ``upper`` are amplitudes where the sampled/interpolated
    profile reaches ``chi2_min + delta_chisq``.  For a single fitted
    parameter, ``delta_chisq=1`` is the conventional 68.3% (1-sigma)
    profile interval.
    """

    best_amplitude: float
    lower_amplitude: float
    upper_amplitude: float
    chi2_min: float
    chi2_threshold: float
    delta_chisq: float
    dof: int

    @property
    def minus(self) -> float:
        return self.best_amplitude - self.lower_amplitude

    @property
    def plus(self) -> float:
        return self.upper_amplitude - self.best_amplitude


@dataclass(frozen=True)
class SfrescoFitResult:
    variable_number: int
    name: str
    amplitude: float
    amplitude_error: float | None
    sfresco_chisq: float | None
    sfresco_reduced_chisq: float | None
    dof: int
    n_points: int
    plot_file: Path
    log_file: Path
    method: str = "migrad"
    converged: bool = True

    @property
    def spectroscopic_factor(self) -> float:
        return self.amplitude**2

    @property
    def spectroscopic_factor_error(self) -> float | None:
        if self.amplitude_error is None:
            return None
        return 2.0 * abs(self.amplitude) * self.amplitude_error

    @property
    def chisq(self) -> float | None:
        return self.sfresco_chisq

    @property
    def reduced_chisq(self) -> float | None:
        return self.sfresco_reduced_chisq

    @property
    def chisq_per_point(self) -> float | None:
        # Backward-compatible convenience; SFRESCOX itself reports both total
        # chi-square and chi-square per degree of freedom via the CHI command.
        if self.sfresco_chisq is None or self.n_points <= 0:
            return None
        return self.sfresco_chisq / self.n_points


@dataclass(frozen=True)
class FitArtifacts:
    fit_dir: Path
    search_file: Path
    command_file: Path
    sfresco_log: Path
    search_plot: Path
    best_input: Path | None = None
    fresco_log: Path | None = None
    local_curve: Path | None = None
    published_curve: Path | None = None
    summary_json: Path | None = None


# ---------------------------------------------------------------------------
# Existing JCEfresco bookkeeping/data integration
# ---------------------------------------------------------------------------


def load_experimental_points(
    path: str | Path,
    *,
    theta_min: float | None = None,
    theta_max: float | None = None,
) -> list[ExperimentalPoint]:
    """Load the same ``angle,xsec,xsec_err`` contract used by plot.py."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Experimental CSV not found: {path}")

    frame = load_experiment_csv(path)
    points: list[ExperimentalPoint] = []

    for row_number, row in enumerate(frame.itertuples(index=False), start=2):
        try:
            angle = float(getattr(row, "angle"))
            xsec = float(getattr(row, "xsec"))
            error = float(getattr(row, "xsec_err"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid numeric data in {path}, row {row_number}") from exc

        if not all(math.isfinite(value) for value in (angle, xsec, error)):
            raise ValueError(f"Non-finite data in {path}, row {row_number}")
        if error <= 0.0:
            raise ValueError(
                f"xsec_err must be positive in {path}, row {row_number}; got {error}"
            )
        if theta_min is not None and angle < theta_min:
            continue
        if theta_max is not None and angle > theta_max:
            continue

        points.append(ExperimentalPoint(angle=angle, xsec=xsec, xsec_err=error))

    if not points:
        raise ValueError("No experimental points remain after angular cuts")
    return points


def state_number_from_filename(filename: str | Path) -> int:
    name = Path(filename).name
    if name.lower() == "elastic.txt":
        return 0
    match = _STATE_FILE_RE.match(name)
    if not match:
        raise ValueError(
            f"Cannot infer FRESCOX curve from {name!r}; expected elastic.txt or stateN.txt"
        )
    return int(match.group("number"))


def channel_for_state_file(fort16: str | Path, state_file: str | Path) -> CurveInfo:
    """Map ``stateN.txt`` to the same ordered fort.16 curve used by split.py."""

    fort16 = Path(fort16)
    if not fort16.is_file():
        raise FileNotFoundError(f"fort.16 not found: {fort16}")

    state_number = state_number_from_filename(state_file)
    curves = parse_fort16(fort16)
    for curve in curves:
        if curve.state_number == state_number:
            return curve

    raise ValueError(
        f"{Path(state_file).name} requests curve #{state_number}, but {fort16} "
        f"contains {len(curves)} parsed curve legend(s)"
    )


def beam_energy_for_channel(fort3: str | Path, channel: CurveInfo) -> float:
    """Return the incident lab energy used by a type=0 SFRESCOX dataset."""

    if channel.lab_energy is not None and math.isfinite(channel.lab_energy):
        return float(channel.lab_energy)

    fort3 = Path(fort3)
    _title, _partitions, _overlaps, _cfps, _couplings, fresco = parse_fort3(fort3)
    value = fresco.get("ELAB")
    if isinstance(value, list):
        value = value[0] if value else None
    try:
        energy = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"Could not determine the incident lab energy from {fort3} or fort.16"
        )
    if not math.isfinite(energy):
        raise ValueError(f"Invalid FRESCOX ELAB value in {fort3}: {value!r}")
    return energy


def numbered_cfps_from_fort3(fort3: str | Path) -> list[NumberedCFP]:
    fort3 = Path(fort3)
    if not fort3.is_file():
        raise FileNotFoundError(f"fort.3 not found: {fort3}")
    _title, _partitions, _overlaps, cfps, _couplings, _fresco = parse_fort3(fort3)
    if not cfps:
        raise ValueError(f"No &CFP entries were parsed from {fort3}")
    return [NumberedCFP(number=i, info=cfp) for i, cfp in enumerate(cfps, start=1)]


def relevant_cfps(cfps: Iterable[NumberedCFP], channel: CurveInfo) -> list[NumberedCFP]:
    """Return CFPs belonging to the selected outgoing partition/state.

    ``IN<0`` in a final ``&cfp`` is a FRESCOX terminator convention; its
    physical projectile/target index is ``abs(IN)``.  This is important for the
    user's standard transfer cards, where the target CFP commonly appears as
    ``IN=-2``.
    """

    return [
        cfp
        for cfp in cfps
        if cfp.physical_in == channel.partition
        and cfp.info.final_state == channel.excitation
    ]


def choose_fresco_input(calc_dir: str | Path) -> Path:
    """Auto-discover a namelist FRESCOX input without relying on its suffix."""

    calc_dir = Path(calc_dir)
    candidates: list[Path] = []
    if not calc_dir.is_dir():
        raise FileNotFoundError(f"Calculation directory not found: {calc_dir}")

    excluded_suffixes = {".out", ".fro", ".log", ".txt", ".csv", ".plot", ".json"}
    for path in sorted(calc_dir.iterdir()):
        if not path.is_file() or path.name.startswith("fort."):
            continue
        if path.suffix.lower() in excluded_suffixes:
            continue
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:50000]
        except OSError:
            continue
        upper = head.upper()
        if "NAMELIST" in upper and "&FRESCO" in upper:
            candidates.append(path)

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError(
            f"Could not auto-discover a namelist FRESCOX input in {calc_dir}; use --input"
        )

    joined = "\n  ".join(str(path) for path in candidates)
    raise ValueError(
        "More than one possible FRESCOX input was found; choose one with --input:\n  "
        + joined
    )


# ---------------------------------------------------------------------------
# Input-card safety: keep SFRESCOX nafrac aligned with the real &CFP order
# ---------------------------------------------------------------------------


def _fortran_float(text: str) -> float:
    return float(text.replace("D", "E").replace("d", "e"))


def _strip_fortran_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        quote: str | None = None
        kept: list[str] = []
        for char in line:
            if quote is not None:
                kept.append(char)
                if char == quote:
                    quote = None
                continue
            if char in {"'", '"'}:
                quote = char
                kept.append(char)
            elif char == "!":
                break
            else:
                kept.append(char)
        lines.append("".join(kept))
    return "\n".join(lines)


def _namelist_blocks(text: str, name: str) -> list[tuple[int, int, str]]:
    """Find non-empty ``&NAME ... /`` blocks, quote-aware."""

    clean = _strip_fortran_comments(text)
    start_re = re.compile(rf"(?i)&\s*{re.escape(name)}\b")
    blocks: list[tuple[int, int, str]] = []
    pos = 0

    while True:
        match = start_re.search(clean, pos)
        if not match:
            break

        quote: str | None = None
        end: int | None = None
        for index in range(match.end(), len(clean)):
            char = clean[index]
            if quote is not None:
                if char == quote:
                    quote = None
                continue
            if char in {"'", '"'}:
                quote = char
            elif char == "/":
                end = index + 1
                break

        if end is None:
            raise ValueError(f"Unterminated &{name} namelist in FRESCOX input")

        block = clean[match.start():end]
        if "=" in block:
            blocks.append((match.start(), end, block))
        pos = end

    return blocks


def _scalar_assignment(block: str, name: str) -> str | None:
    match = re.search(
        rf"(?i)(?<![A-Za-z0-9_]){re.escape(name)}\s*=\s*({_FLOAT_RE_TEXT})",
        block,
    )
    return match.group(1) if match else None


def _input_cfp_signature(block: str) -> tuple[int | None, int | None, int | None, int | None, float | None]:
    def as_int(name: str) -> int | None:
        value = _scalar_assignment(block, name)
        return int(round(_fortran_float(value))) if value is not None else None

    a_value = _scalar_assignment(block, "A")
    return (
        as_int("IN"),
        as_int("IB"),
        as_int("IA"),
        as_int("KN"),
        _fortran_float(a_value) if a_value is not None else None,
    )


def _is_cfp_terminator(
    signature: tuple[int | None, int | None, int | None, int | None, float | None]
) -> bool:
    """Return True for converter-style ``IN=IB=IA=KN=0`` CFP terminators.

    Some FRESCOX namelist cards terminate a CFP list with an explicit zeroed
    ``&CFP`` block.  FRESCOX does not retain that record as a physical CFP in
    ``fort.3``, so it must not consume an SFRESCOX ``nafrac`` index.
    """

    in_, ib, ia, kn, _amp = signature
    return (in_, ib, ia, kn) == (0, 0, 0, 0)


def _physical_input_cfp_blocks(text: str) -> list[tuple[int, int, str]]:
    """Return only physical CFP blocks, preserving their input-card order."""

    physical: list[tuple[int, int, str]] = []
    for block_info in _namelist_blocks(text, "CFP"):
        signature = _input_cfp_signature(block_info[2])
        if _is_cfp_terminator(signature):
            continue
        physical.append(block_info)
    return physical


def validate_input_cfp_order(fresco_input: str | Path, fort3_cfps: Sequence[NumberedCFP]) -> None:
    """Validate the physical input-card CFP order against expanded ``fort.3``.

    Explicit zeroed CFP terminators are ignored.  The sign of ``IN`` is also
    ignored for identity matching because FRESCO/FRESCOX may use a negative
    final ``IN`` as an end-of-list marker while the physical partition remains
    ``abs(IN)``.
    """

    fresco_input = Path(fresco_input)
    text = fresco_input.read_text(encoding="utf-8", errors="replace")
    blocks = _physical_input_cfp_blocks(text)

    if len(blocks) != len(fort3_cfps):
        raise ValueError(
            f"CFP bookkeeping mismatch: {fresco_input} contains {len(blocks)} physical "
            f"&CFP blocks but fort.3 contains {len(fort3_cfps)}. Refusing to guess nafrac."
        )

    for numbered, (_start, _end, block) in zip(fort3_cfps, blocks):
        in_, ib, ia, kn, amp = _input_cfp_signature(block)
        info = numbered.info
        expected = (abs(info.partition), info.final_state, info.core_state, info.overlap_kn)
        observed = (abs(in_) if in_ is not None else None, ib, ia, kn)
        if observed != expected:
            raise ValueError(
                f"CFP #{numbered.number} differs between input and fort.3: "
                f"input |IN|/IB/IA/KN={observed}, fort.3={expected}. Refusing to vary nafrac."
            )
        if amp is None or not math.isclose(amp, info.amplitude, rel_tol=1e-6, abs_tol=1e-8):
            raise ValueError(
                f"CFP #{numbered.number} amplitude differs between input ({amp}) and "
                f"fort.3 ({info.amplitude}). Refusing to start from inconsistent bookkeeping."
            )


# ---------------------------------------------------------------------------
# SFRESCOX search generation / execution / parsing
# ---------------------------------------------------------------------------


def _quoted_path(path: str | Path) -> str:
    text = str(path)
    if "'" in text:
        raise ValueError("Paths containing apostrophes are not supported by this SFRESCOX writer")
    return f"'{text}'"


def write_search_file(
    path: str | Path,
    *,
    fresco_input: str | Path,
    fresco_output: str | Path,
    cfp: NumberedCFP,
    points: Iterable[ExperimentalPoint],
    partition: int,
    excitation: int,
    variable_name: str | None = None,
    step: float = 0.01,
    valmin: float | None = None,
    valmax: float | None = None,
    lab: bool = False,
    iscale: int = 2,
    energy: float | None = None,
) -> Path:
    path = Path(path)
    points = list(points)

    if step <= 0.0:
        raise ValueError("SFRESCOX step must be positive")
    if valmin is not None and valmax is not None and valmin >= valmax:
        raise ValueError("--min must be smaller than --max")
    if iscale not in {-1, 0, 1, 2, 3}:
        raise ValueError("iscale must be one of -1, 0, 1, 2, 3")

    name = (variable_name or f"A{cfp.number}")[:10]
    variable = (
        f"&variable kind=2 name='{name}' nafrac={cfp.number} "
        f"afrac={cfp.info.amplitude:.12g} step={step:.12g}"
    )
    if valmin is not None:
        variable += f" valmin={valmin:.12g}"
    if valmax is not None:
        variable += f" valmax={valmax:.12g}"
    variable += " /"

    lines = [
        f"{_quoted_path(fresco_input)} {_quoted_path(fresco_output)} 1 1",
        variable,
        (
            f"&data type=0 data_file='=' points={len(points)} delta=0 "
            f"lab={'T' if lab else 'F'} idir=0 iscale={iscale} abserr=T "
            + (f"energy={energy:.12g} " if energy is not None else "")
            + f"ic={partition} ia={excitation} k=0 q=0 /"
        ),
    ]
    lines.extend(f"{p.angle:.12g} {p.xsec:.12g} {p.xsec_err:.12g}" for p in points)
    lines.append("&")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_scan_command_file(
    path: str | Path,
    *,
    search_file: str | Path,
    variable_number: int,
    scan_min: float,
    scan_max: float,
    scan_step: float,
) -> Path:
    """Write a coarse native SFRESCOX SCAN command stream."""

    if scan_step <= 0.0:
        raise ValueError("scan step must be positive")
    if scan_min >= scan_max:
        raise ValueError("scan minimum must be smaller than scan maximum")
    path = Path(path)
    lines = [
        str(search_file),
        f"scan {variable_number} {scan_min:.12g} {scan_max:.12g} {scan_step:.12g}",
        "ex",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_command_file(
    path: str | Path,
    *,
    search_file: str | Path,
    plot_file: str | Path = "search.plot",
    initial_value: float | None = None,
    variable_number: int = 1,
) -> Path:
    """Write the SFRESCOX -> MINUIT -> MIGRAD stream used for the final fit.

    ``CHI`` is deliberately requested before and after MINUIT.  The final CHI
    output is the authoritative SFRESCOX chi-square record; SHOW is retained as
    a human-readable diagnostic only.
    """

    path = Path(path)
    lines = [str(search_file)]
    if initial_value is not None:
        lines.append(f"set {variable_number} {initial_value:.12g}")
    lines.extend(
        [
            "chi",
            "min",
            "migrad",
            "end",
            "q",
            "chi",
            "show",
            f"plot {plot_file}",
            "ex",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path



def write_final_scan_command_file(
    path: str | Path,
    *,
    search_file: str | Path,
    plot_file: str | Path,
    amplitude: float,
    variable_number: int = 1,
) -> Path:
    """Write a derivative-free final SFRESCOX evaluation at a chosen amplitude."""

    path = Path(path)
    lines = [
        str(search_file),
        f"set {variable_number} {amplitude:.12g}",
        "q",
        "chi",
        "show",
        f"plot {plot_file}",
        "ex",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def automatic_scan_range(
    amplitude: float,
    *,
    scan_min: float | None = None,
    scan_max: float | None = None,
    scan_step: float | None = None,
    valmin: float | None = None,
    valmax: float | None = None,
) -> tuple[float, float, float]:
    """Choose a conservative coarse scan around the supplied CFP amplitude.

    By default the interval is A0 +/- |A0|, i.e. [0,2*A0] for a positive
    amplitude and [2*A0,0] for a negative amplitude.  Near zero, [-1,1] is
    used.  Explicit scan bounds always win; variable bounds clip the automatic
    interval.  The default step gives roughly 20 scan intervals.
    """

    if (scan_min is None) ^ (scan_max is None):
        raise ValueError("--scan-min and --scan-max must be supplied together")

    if scan_min is None:
        half_width = abs(amplitude) if abs(amplitude) > 1.0e-8 else 1.0
        lo = amplitude - half_width
        hi = amplitude + half_width
        if valmin is not None:
            lo = max(lo, valmin)
        if valmax is not None:
            hi = min(hi, valmax)
    else:
        lo = float(scan_min)
        hi = float(scan_max)

    if lo >= hi:
        raise ValueError(f"Invalid scan interval: {lo:g} to {hi:g}")

    step = float(scan_step) if scan_step is not None else (hi - lo) / 20.0
    if step <= 0.0:
        raise ValueError("--scan-step must be positive")
    return lo, hi, step



def scan_point_count(scan_min: float, scan_max: float, scan_step: float) -> int:
    """Return the number of points produced by an inclusive SFRESCOX scan."""

    if scan_step <= 0.0:
        raise ValueError("scan step must be positive")
    if scan_min >= scan_max:
        raise ValueError("scan minimum must be smaller than scan maximum")
    intervals = int(math.floor((scan_max - scan_min) / scan_step + 1.0e-9))
    return intervals + 1


def refinement_scan_range(
    points: Sequence[ScanPoint],
    *,
    factor: int = 5,
) -> tuple[float, float, float]:
    """Bracket the discrete minimum with its neighbors and reduce the step.

    A derivative-free refinement is much more robust than MIGRAD for the
    one-parameter spectroscopic-amplitude problem because a full FRESCOX solve
    can have small numerical jitter at the tiny parameter displacements used by
    finite-difference derivatives.
    """

    if factor < 2:
        raise ValueError("refinement factor must be at least 2")
    ordered = sorted(points, key=lambda point: point.amplitude)
    if len(ordered) < 3:
        raise ValueError("At least three scan points are required for refinement")
    best_index = min(range(len(ordered)), key=lambda i: ordered[i].reduced_chisq)
    if best_index == 0 or best_index == len(ordered) - 1:
        best = ordered[best_index]
        raise ValueError(
            "SFRESCOX scan minimum lies on the scan boundary at "
            f"A={best.amplitude:g}. Widen --scan-min/--scan-max before refining."
        )

    lo = ordered[best_index - 1].amplitude
    hi = ordered[best_index + 1].amplitude
    step = (hi - lo) / (2.0 * factor)
    if step <= 0.0:
        raise ValueError("Could not construct a positive refinement step")
    return lo, hi, step


def parabolic_scan_estimate(
    points: Sequence[ScanPoint],
    *,
    dof: int,
    max_points: int = 3,
) -> ScanEstimate:
    """Estimate the continuous minimum and 1-sigma error from a local scan.

    SFRESCOX reports ``ChiSq/df`` for SCAN points.  For one fitted parameter,
    the usual 68% one-parameter interval is Delta chi-square = 1, i.e.
    Delta(chi-square/df) = 1/dof.  The local quadratic curvature therefore
    gives sigma_A = sqrt(1 / (dof * curvature)).

    If the local quadratic is not well behaved, the discrete scan minimum is
    returned with no formal uncertainty rather than inventing one.
    """

    finite = sorted(
        (point for point in points if math.isfinite(point.reduced_chisq)),
        key=lambda point: point.amplitude,
    )
    if not finite:
        raise ValueError("No finite scan points are available")
    discrete = min(finite, key=lambda point: point.reduced_chisq)
    if len(finite) < 3 or dof <= 0:
        return ScanEstimate(
            amplitude=discrete.amplitude,
            amplitude_error=None,
            reduced_chisq_estimate=discrete.reduced_chisq,
            discrete_best=discrete,
            points_used=(discrete,),
        )

    best_index = finite.index(discrete)
    half = max_points // 2
    start = max(0, best_index - half)
    end = min(len(finite), start + max_points)
    start = max(0, end - max_points)
    selected = finite[start:end]
    if len(selected) < 3:
        selected = finite[max(0, best_index - 1) : min(len(finite), best_index + 2)]

    x = np.asarray([point.amplitude for point in selected], dtype=float)
    y = np.asarray([point.reduced_chisq for point in selected], dtype=float)
    try:
        curvature, linear, constant = np.polyfit(x, y, 2)
    except (TypeError, ValueError, np.linalg.LinAlgError):
        curvature = math.nan
        linear = math.nan
        constant = math.nan

    if not math.isfinite(curvature) or curvature <= 0.0:
        return ScanEstimate(
            amplitude=discrete.amplitude,
            amplitude_error=None,
            reduced_chisq_estimate=discrete.reduced_chisq,
            discrete_best=discrete,
            points_used=tuple(selected),
        )

    vertex = -linear / (2.0 * curvature)
    local_lo = min(x)
    local_hi = max(x)
    if not math.isfinite(vertex) or vertex < local_lo or vertex > local_hi:
        return ScanEstimate(
            amplitude=discrete.amplitude,
            amplitude_error=None,
            reduced_chisq_estimate=discrete.reduced_chisq,
            discrete_best=discrete,
            points_used=tuple(selected),
        )

    estimate = float(curvature * vertex**2 + linear * vertex + constant)
    sigma = math.sqrt(1.0 / (dof * curvature))
    if not math.isfinite(sigma) or sigma <= 0.0:
        sigma = None

    return ScanEstimate(
        amplitude=float(vertex),
        amplitude_error=sigma,
        reduced_chisq_estimate=estimate,
        discrete_best=discrete,
        points_used=tuple(selected),
    )


def _deduplicate_scan_points(points: Sequence[ScanPoint]) -> list[ScanPoint]:
    """Return scan points sorted by amplitude, keeping the lowest chi-square duplicate."""

    by_amp: dict[float, ScanPoint] = {}
    for point in points:
        if not (math.isfinite(point.amplitude) and math.isfinite(point.reduced_chisq)):
            continue
        previous = by_amp.get(point.amplitude)
        if previous is None or point.reduced_chisq < previous.reduced_chisq:
            by_amp[point.amplitude] = point
    return sorted(by_amp.values(), key=lambda point: point.amplitude)


def _linear_threshold_crossing(
    inner: ScanPoint,
    outer: ScanPoint,
    *,
    target_chisq: float,
    dof: int,
) -> float:
    """Linearly interpolate A where absolute chi-square reaches target."""

    x1, x2 = inner.amplitude, outer.amplitude
    y1 = inner.reduced_chisq * dof
    y2 = outer.reduced_chisq * dof
    if y1 == y2:
        return 0.5 * (x1 + x2)
    fraction = (target_chisq - y1) / (y2 - y1)
    fraction = min(1.0, max(0.0, fraction))
    return x1 + fraction * (x2 - x1)


def profile_interval_from_scan(
    points: Sequence[ScanPoint],
    *,
    dof: int,
    delta_chisq: float = 1.0,
) -> ProfileInterval:
    """Find a one-parameter profile-chi-square interval from SFRESCOX scans.

    The discrete sampled minimum is the source of truth. Moving outward on
    each side, the first bracket that crosses ``chi2_min + delta_chisq`` is
    linearly interpolated.  This intentionally uses actual SFRESCOX-evaluated
    points rather than the quadratic diagnostic used only for curvature.
    """

    if dof <= 0:
        raise ValueError('Degrees of freedom must be positive')
    if delta_chisq <= 0.0:
        raise ValueError('delta_chisq must be positive')

    ordered = _deduplicate_scan_points(points)
    if len(ordered) < 3:
        raise ValueError('At least three finite scan points are required for a profile interval')

    best_index = min(range(len(ordered)), key=lambda i: ordered[i].reduced_chisq)
    if best_index == 0 or best_index == len(ordered) - 1:
        raise ValueError('Profile minimum lies on the scan boundary; widen the scan range')

    best = ordered[best_index]
    chi2_min = best.reduced_chisq * dof
    target = chi2_min + delta_chisq

    lower = None
    inner = best
    for idx in range(best_index - 1, -1, -1):
        outer = ordered[idx]
        if outer.reduced_chisq * dof >= target:
            lower = _linear_threshold_crossing(
                inner, outer, target_chisq=target, dof=dof
            )
            break
        inner = outer

    upper = None
    inner = best
    for idx in range(best_index + 1, len(ordered)):
        outer = ordered[idx]
        if outer.reduced_chisq * dof >= target:
            upper = _linear_threshold_crossing(
                inner, outer, target_chisq=target, dof=dof
            )
            break
        inner = outer

    if lower is None or upper is None:
        missing = []
        if lower is None:
            missing.append('lower')
        if upper is None:
            missing.append('upper')
        raise ValueError(
            'Could not bracket the ' + '/'.join(missing) +
            ' Delta-chi-square crossing. Widen the scan range or refine more densely.'
        )

    return ProfileInterval(
        best_amplitude=best.amplitude,
        lower_amplitude=float(lower),
        upper_amplitude=float(upper),
        chi2_min=float(chi2_min),
        chi2_threshold=float(target),
        delta_chisq=float(delta_chisq),
        dof=int(dof),
    )


def write_chisq_profile_csv(
    path: str | Path,
    points: Sequence[ScanPoint],
    *,
    dof: int,
    interval: ProfileInterval | None = None,
) -> Path:
    """Write a machine- and human-readable chi-square profile table."""

    path = Path(path)
    ordered = _deduplicate_scan_points(points)
    if not ordered:
        raise ValueError('No scan points available for chi-square profile CSV')
    min_chi2 = min(point.reduced_chisq * dof for point in ordered)
    lines = ['amplitude,reduced_chisq,chisq,delta_chisq']
    for point in ordered:
        chisq = point.reduced_chisq * dof
        lines.append(
            f'{point.amplitude:.12g},{point.reduced_chisq:.12g},'
            f'{chisq:.12g},{chisq - min_chi2:.12g}'
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def plot_chisq_profile(
    path: str | Path,
    points: Sequence[ScanPoint],
    *,
    dof: int,
    interval: ProfileInterval | None = None,
    xlabel: str = r'Spectroscopic amplitude $A$',
) -> Path:
    """Save a compact chi-square-versus-amplitude diagnostic plot."""

    import matplotlib.pyplot as plt

    path = Path(path)
    ordered = _deduplicate_scan_points(points)
    if not ordered:
        raise ValueError('No scan points available for chi-square profile plot')
    x = np.asarray([p.amplitude for p in ordered], dtype=float)
    y = np.asarray([p.reduced_chisq * dof for p in ordered], dtype=float)

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    ax.plot(x, y, marker='o')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(r'$\chi^2$')
    ax.grid(True)

    if interval is not None:
        ax.axhline(interval.chi2_threshold, linestyle='--', linewidth=1.5, label=r'$\chi^2_{\min}+1$')
        ax.axvline(interval.best_amplitude, linestyle='-', linewidth=1.5, label='Best fit')
        ax.axvspan(interval.lower_amplitude, interval.upper_amplitude, alpha=0.18, label=r'$1\sigma$ interval')
        ax.legend()

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return path


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h{minutes:02d}m{sec:02d}s"
    if minutes:
        return f"{minutes:d}m{sec:02d}s"
    return f"{sec:d}s"


def _progress_bar(done: int, total: int, *, width: int = 18) -> str:
    if total <= 0:
        return "[?]"
    fraction = min(max(done / total, 0.0), 1.0)
    filled = int(round(width * fraction))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _run_streaming_process(
    *,
    command: list[str],
    input_text: str,
    cwd: Path,
    log_file: Path,
    timeout: float | None,
    line_handler: Callable[[str], None] | None = None,
    heartbeat_label: str | None = None,
    heartbeat_seconds: float = 15.0,
) -> int:
    """Run a Fortran executable while teeing output to disk in real time."""

    env = os.environ.copy()
    # gfortran otherwise tends to block-buffer output when stdout is a pipe.
    env.setdefault("GFORTRAN_UNBUFFERED_ALL", "y")

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=cwd,
        env=env,
    )
    assert process.stdin is not None
    assert process.stdout is not None

    output_queue: queue.Queue[str | None] = queue.Queue()

    def _reader() -> None:
        try:
            for line in process.stdout:
                output_queue.put(line)
        finally:
            output_queue.put(None)

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()

    process.stdin.write(input_text)
    process.stdin.flush()
    process.stdin.close()

    start = time.monotonic()
    last_heartbeat = start
    reader_finished = False
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with log_file.open("w", encoding="utf-8") as stream:
        while not reader_finished:
            now = time.monotonic()
            if timeout is not None and now - start > timeout:
                process.kill()
                reader.join(timeout=2.0)
                raise subprocess.TimeoutExpired(command, timeout)

            try:
                item = output_queue.get(timeout=0.5)
            except queue.Empty:
                item = ""

            if item is None:
                reader_finished = True
            elif item:
                stream.write(item)
                stream.flush()
                if line_handler is not None:
                    line_handler(item)

            now = time.monotonic()
            if (
                heartbeat_label is not None
                and heartbeat_seconds > 0.0
                and now - last_heartbeat >= heartbeat_seconds
            ):
                print(
                    f"[{heartbeat_label}] still running... elapsed "
                    f"{_format_duration(now - start)}",
                    flush=True,
                )
                last_heartbeat = now

    return process.wait()


def resolve_executable(executable: str | Path) -> str:
    text = str(executable)
    resolved = shutil.which(text)
    if resolved is not None:
        return resolved
    candidate = Path(text).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    raise FileNotFoundError(
        f"Could not find executable {text!r} on PATH or as a file path"
    )


def run_sfrescox(
    *,
    executable: str | Path,
    command_file: str | Path,
    cwd: str | Path,
    log_file: str | Path,
    timeout: float | None = None,
    stage: str = "sfrescox",
    expected_scan_points: int | None = None,
    show_progress: bool = True,
    verbose: bool = False,
) -> Path:
    """Run SFRESCOX with live, concise terminal progress.

    When a SCAN is being run, each completed scan point is printed immediately
    with its amplitude and chi-square/dof.  A heartbeat is also printed every
    ~15 s so a long FRESCOX evaluation never looks frozen.  The complete raw
    stdout is always preserved in ``log_file``; ``verbose=True`` additionally
    mirrors every raw line to the terminal.
    """

    cwd = Path(cwd)
    command_file = Path(command_file)
    log_file = Path(log_file)
    resolved = resolve_executable(executable)
    commands = command_file.read_text(encoding="utf-8")

    completed_points = 0
    start = time.monotonic()

    def _handle(line: str) -> None:
        nonlocal completed_points
        if verbose:
            print(f"[{stage}:raw] {line.rstrip()}", flush=True)
        if not show_progress:
            return
        match = _SCAN_LINE_RE.search(line)
        if match is None:
            return
        completed_points += 1
        amplitude = _fortran_float(match.group("value"))
        chisq = _fortran_float(match.group("chi"))
        elapsed = time.monotonic() - start
        if expected_scan_points is not None and expected_scan_points > 0:
            avg = elapsed / max(completed_points, 1)
            remaining = max(expected_scan_points - completed_points, 0)
            eta = avg * remaining
            bar = _progress_bar(completed_points, expected_scan_points)
            print(
                f"[{stage}] {bar} {completed_points:>2}/{expected_scan_points:<2} "
                f"A={amplitude:.8g}  chi2/dof={chisq:.6g}  "
                f"elapsed={_format_duration(elapsed)}  ETA~{_format_duration(eta)}",
                flush=True,
            )
        else:
            print(
                f"[{stage}] point {completed_points}: A={amplitude:.8g} "
                f"chi2/dof={chisq:.6g} elapsed={_format_duration(elapsed)}",
                flush=True,
            )

    if show_progress:
        detail = (
            f" ({expected_scan_points} scan points)"
            if expected_scan_points is not None
            else ""
        )
        print(f"[{stage}] starting SFRESCOX{detail}...", flush=True)

    returncode = _run_streaming_process(
        command=[resolved],
        input_text=commands,
        cwd=cwd,
        log_file=log_file,
        timeout=timeout,
        line_handler=_handle,
        heartbeat_label=stage if show_progress else None,
    )
    if returncode != 0:
        raise RuntimeError(
            f"SFRESCOX exited with status {returncode}. See {log_file}"
        )
    if show_progress:
        print(
            f"[{stage}] finished in {_format_duration(time.monotonic() - start)}",
            flush=True,
        )
    return log_file


_VAR_LINE_RE = re.compile(
    rf"^\s*#?\s*Var\s+(?P<number>\d+)\s*=\s*(?P<name>\S+)\s+value\s+"
    rf"(?P<value>{_FLOAT_RE_TEXT})"
    rf"(?:\s*,?\s*step\s+(?P<step>{_FLOAT_RE_TEXT})\s*,?\s*error\s+"
    rf"(?P<error>{_FLOAT_RE_TEXT}))?",
    re.IGNORECASE,
)
_SCAN_LINE_RE = re.compile(
    rf"Variable\s+(?P<number>\d+)\s*:\s*(?P<name>\S+)\s*=\s*"
    rf"(?P<value>{_FLOAT_RE_TEXT})\s*:\s*ChiSq/df\s*=\s*(?P<chi>{_FLOAT_RE_TEXT})",
    re.IGNORECASE,
)
_TOTAL_CHI_RE = re.compile(
    rf"Total\s+ChiSq\s*=\s*(?P<chi>{_FLOAT_RE_TEXT})"
    rf"(?:\s*:\s*(?P<red>{_FLOAT_RE_TEXT})\s+per\s+dof\s+from\s+dof\s*=\s*(?P<dof>\d+))?",
    re.IGNORECASE,
)


def parse_scan_results(text: str) -> list[ScanPoint]:
    points: list[ScanPoint] = []
    for line in text.splitlines():
        match = _SCAN_LINE_RE.search(line)
        if match:
            points.append(
                ScanPoint(
                    amplitude=_fortran_float(match.group("value")),
                    reduced_chisq=_fortran_float(match.group("chi")),
                )
            )
    return points


def best_scan_point(text: str) -> ScanPoint:
    points = parse_scan_results(text)
    if not points:
        raise ValueError("Could not parse any SFRESCOX SCAN points")
    finite = [p for p in points if math.isfinite(p.reduced_chisq)]
    if not finite:
        raise ValueError("SFRESCOX SCAN produced no finite chi-square values")
    return min(finite, key=lambda point: point.reduced_chisq)


def _parse_variable(text: str) -> tuple[int, str, float, float | None] | None:
    variables: list[tuple[int, str, float, float | None]] = []
    for line in text.splitlines():
        match = _VAR_LINE_RE.search(line)
        if not match:
            continue
        error_text = match.group("error")
        variables.append(
            (
                int(match.group("number")),
                match.group("name").strip(),
                _fortran_float(match.group("value")),
                _fortran_float(error_text) if error_text is not None else None,
            )
        )
    return variables[-1] if variables else None


def _parse_total_chi(text: str) -> tuple[float | None, float | None, int | None]:
    matches = list(_TOTAL_CHI_RE.finditer(text))
    if not matches:
        return None, None, None
    # Prefer CHI-command records, which include ``: chi2/dof per dof ...``.
    detailed = [match for match in matches if match.group("red") is not None]
    match = detailed[-1] if detailed else matches[-1]
    chi = _fortran_float(match.group("chi"))
    red_text = match.group("red")
    dof_text = match.group("dof")
    return (
        chi,
        _fortran_float(red_text) if red_text is not None else None,
        int(dof_text) if dof_text is not None else None,
    )


def require_migrad_convergence(text: str, *, log_file: str | Path) -> None:
    upper = text.upper()
    failures = (
        "MIGRAD TERMINATED WITHOUT CONVERGENCE",
        "STATUS=FAILED",
        "CALL LIMIT EXCEEDED IN MIGRAD",
    )
    if any(marker in upper for marker in failures):
        raise RuntimeError(
            "SFRESCOX/MINUIT did not converge; no best-fit curve will be published. "
            f"See {log_file}"
        )
    if "MIGRAD MINIMIZATION HAS CONVERGED" not in upper:
        raise RuntimeError(
            "SFRESCOX finished without an explicit MIGRAD convergence message; "
            f"refusing to accept the fit. See {log_file}"
        )


def parse_fit_result(
    plot_file: str | Path,
    *,
    log_file: str | Path,
    n_points: int,
) -> SfrescoFitResult:
    plot_file = Path(plot_file)
    log_file = Path(log_file)
    log_text = log_file.read_text(encoding="utf-8", errors="replace") if log_file.is_file() else ""
    require_migrad_convergence(log_text, log_file=log_file)

    variable = _parse_variable(log_text)
    if variable is None and plot_file.is_file():
        variable = _parse_variable(plot_file.read_text(encoding="utf-8", errors="replace"))
    if variable is None:
        raise ValueError(
            f"Could not parse the fitted SFRESCOX variable from {plot_file} or {log_file}"
        )

    chi, reduced, dof = _parse_total_chi(log_text)
    expected_dof = n_points - 1
    if dof is None:
        dof = expected_dof
    if chi is not None and reduced is None and dof > 0:
        reduced = chi / dof

    number, name, amplitude, amplitude_error = variable
    return SfrescoFitResult(
        variable_number=number,
        name=name,
        amplitude=amplitude,
        amplitude_error=amplitude_error,
        sfresco_chisq=chi,
        sfresco_reduced_chisq=reduced,
        dof=dof,
        n_points=n_points,
        plot_file=plot_file,
        log_file=log_file,
        converged=True,
    )



def parse_scan_fit_result(
    plot_file: str | Path,
    *,
    log_file: str | Path,
    n_points: int,
    amplitude_error: float | None,
) -> SfrescoFitResult:
    """Parse a final SET/CHI evaluation produced by the scan minimizer."""

    plot_file = Path(plot_file)
    log_file = Path(log_file)
    log_text = (
        log_file.read_text(encoding="utf-8", errors="replace")
        if log_file.is_file()
        else ""
    )
    variable = _parse_variable(log_text)
    if variable is None and plot_file.is_file():
        variable = _parse_variable(
            plot_file.read_text(encoding="utf-8", errors="replace")
        )
    if variable is None:
        raise ValueError(
            f"Could not parse the final SFRESCOX variable from {plot_file} or {log_file}"
        )

    chi, reduced, dof = _parse_total_chi(log_text)
    expected_dof = n_points - 1
    if dof is None:
        dof = expected_dof
    if chi is not None and reduced is None and dof > 0:
        reduced = chi / dof
    if chi is None:
        raise ValueError(f"Final SFRESCOX CHI result was not found in {log_file}")

    number, name, amplitude, _reported_error = variable
    return SfrescoFitResult(
        variable_number=number,
        name=name,
        amplitude=amplitude,
        amplitude_error=amplitude_error,
        sfresco_chisq=chi,
        sfresco_reduced_chisq=reduced,
        dof=dof,
        n_points=n_points,
        plot_file=plot_file,
        log_file=log_file,
        converged=True,
        method="scan",
    )


def validate_reported_amplitude(
    requested: float,
    reported: float,
    *,
    rel_tol: float = 1.0e-6,
    abs_tol: float = 1.0e-6,
) -> None:
    """Require SFRESCOX to report the exact final scan amplitude requested."""

    if not math.isclose(requested, reported, rel_tol=rel_tol, abs_tol=abs_tol):
        raise RuntimeError(
            "SFRESCOX final-amplitude handoff mismatch: "
            f"requested A={requested:.12g}, reported A={reported:.12g}. "
            "Refusing to write the best-fit FRESCOX card."
        )


def calculate_curve_chisq(
    points: Sequence[ExperimentalPoint],
    curve_file: str | Path,
    *,
    n_fit_parameters: int = 1,
) -> CurveChiSquare:
    """Independently evaluate chi-square from the exact final FRESCOX curve."""

    curve_file = Path(curve_file)
    theta, theory = load_fresco_curve(curve_file, thin=1, theta_max=None)
    x = np.asarray([p.angle for p in points], dtype=float)
    y = np.asarray([p.xsec for p in points], dtype=float)
    err = np.asarray([p.xsec_err for p in points], dtype=float)

    if x.min() < theta.min() or x.max() > theta.max():
        raise ValueError(
            f"Experimental angles [{x.min():g},{x.max():g}] exceed final FRESCOX "
            f"curve range [{theta.min():g},{theta.max():g}] in {curve_file}"
        )

    prediction = np.interp(x, theta, theory)
    pulls = (y - prediction) / err
    chisq = float(np.sum(pulls**2))
    dof = len(points) - n_fit_parameters
    reduced = chisq / dof if dof > 0 else math.nan
    return CurveChiSquare(
        chisq=chisq,
        reduced_chisq=reduced,
        n_points=len(points),
        max_abs_pull=float(np.max(np.abs(pulls))),
    )


def amplitude_squared_scale_bounds(
    *,
    best_amplitude: float,
    lower_amplitude: float,
    upper_amplitude: float,
) -> tuple[float, float]:
    """Return cross-section scale factors over a one-parameter A interval.

    For a single isolated transfer amplitude, ``sigma(theta; A)`` is
    proportional to ``A**2``. The confidence interval is therefore propagated
    exactly by the extrema of ``A**2`` on ``[A_low, A_high]``. This also
    handles an interval that crosses zero.
    """

    values = (best_amplitude, lower_amplitude, upper_amplitude)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Amplitudes used for the uncertainty band must be finite")
    if lower_amplitude > upper_amplitude:
        raise ValueError("Lower amplitude exceeds upper amplitude")
    if not (lower_amplitude <= best_amplitude <= upper_amplitude):
        raise ValueError("Best-fit amplitude is not inside the profile interval")
    if abs(best_amplitude) <= 1.0e-14:
        raise ValueError("Cannot form an A^2-scaled band for best amplitude A=0")

    endpoint_squares = (lower_amplitude**2, upper_amplitude**2)
    min_square = (
        0.0
        if lower_amplitude <= 0.0 <= upper_amplitude
        else min(endpoint_squares)
    )
    max_square = max(endpoint_squares)
    denominator = best_amplitude**2
    return min_square / denominator, max_square / denominator


def write_scaled_amplitude_band(
    best_curve: str | Path,
    lower_output: str | Path,
    upper_output: str | Path,
    *,
    best_amplitude: float,
    lower_amplitude: float,
    upper_amplitude: float,
) -> tuple[Path, Path]:
    """Write the exact constant-fractional band for ``sigma proportional A^2``.

    The angular dependence comes from the *single exact best-fit FRESCOX
    curve*. That avoids introducing run-to-run solver jitter into a purely
    multiplicative normalization uncertainty.
    """

    best_curve = Path(best_curve)
    lower_output = Path(lower_output)
    upper_output = Path(upper_output)
    data = np.loadtxt(best_curve, usecols=(0, 1), ndmin=2)
    if data.size == 0:
        raise ValueError(f"Best-fit curve is empty: {best_curve}")

    low_scale, high_scale = amplitude_squared_scale_bounds(
        best_amplitude=best_amplitude,
        lower_amplitude=lower_amplitude,
        upper_amplitude=upper_amplitude,
    )

    lower_output.parent.mkdir(parents=True, exist_ok=True)
    upper_output.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(
        lower_output,
        np.column_stack((data[:, 0], data[:, 1] * low_scale)),
        fmt="%.10g",
    )
    np.savetxt(
        upper_output,
        np.column_stack((data[:, 0], data[:, 1] * high_scale)),
        fmt="%.10g",
    )
    return lower_output, upper_output


def validate_amplitude_squared_scaling(
    reference_curve: str | Path,
    best_curve: str | Path,
    *,
    reference_amplitude: float,
    best_amplitude: float,
    max_relative_tolerance: float = 0.03,
    rms_relative_tolerance: float = 0.01,
) -> AmplitudeScalingCheck:
    """Check whether two FRESCOX curves obey ``sigma proportional A^2``.

    The original/reference calculation is analytically rescaled to the
    best-fit amplitude and compared point-by-point with the independently
    rerun best-fit curve. This makes the fast uncertainty propagation
    self-validating before JCEfresco draws a constant-fractional band.
    """

    if abs(reference_amplitude) <= 1.0e-14 or abs(best_amplitude) <= 1.0e-14:
        return AmplitudeScalingCheck(False, math.inf, math.inf, math.nan, 0)
    if max_relative_tolerance <= 0.0 or rms_relative_tolerance <= 0.0:
        raise ValueError("Scaling tolerances must be positive")

    ref_theta, ref_xsec = load_fresco_curve(
        Path(reference_curve), thin=1, theta_max=None
    )
    best_theta, best_xsec = load_fresco_curve(
        Path(best_curve), thin=1, theta_max=None
    )
    if best_theta.min() < ref_theta.min() or best_theta.max() > ref_theta.max():
        return AmplitudeScalingCheck(False, math.inf, math.inf, math.nan, 0)

    ref_on_best = np.interp(best_theta, ref_theta, ref_xsec)
    scale = (best_amplitude / reference_amplitude) ** 2
    predicted_best = ref_on_best * scale

    magnitude = np.maximum(np.abs(best_xsec), np.abs(predicted_best))
    floor = max(float(np.max(magnitude)) * 1.0e-8, 1.0e-14)
    mask = magnitude > floor
    if not np.any(mask):
        return AmplitudeScalingCheck(False, math.inf, math.inf, 1.0 / scale, 0)

    relative = (
        np.abs(predicted_best[mask] - best_xsec[mask])
        / np.maximum(magnitude[mask], floor)
    )
    rms = float(np.sqrt(np.mean(relative**2)))
    maximum = float(np.max(relative))
    return AmplitudeScalingCheck(
        passed=(
            rms <= rms_relative_tolerance
            and maximum <= max_relative_tolerance
        ),
        rms_relative_difference=rms,
        max_relative_difference=maximum,
        expected_cross_section_ratio=(reference_amplitude / best_amplitude) ** 2,
        points_compared=int(np.count_nonzero(mask)),
    )


def write_curve_envelope(
    curve_files: Sequence[str | Path],
    lower_output: str | Path,
    upper_output: str | Path,
    *,
    reference_curve: str | Path,
) -> tuple[Path, Path]:
    """Write a pointwise envelope of sampled FRESCOX curves.

    ``reference_curve`` defines the output angular grid and should be the exact
    best-fit curve. It is always included in the envelope, which guarantees the
    best-fit prediction cannot lie outside the published band.
    """

    reference_curve = Path(reference_curve)
    theta, best = load_fresco_curve(reference_curve, thin=1, theta_max=None)
    arrays = [best]
    reference_resolved = reference_curve.resolve()

    for item in curve_files:
        path = Path(item)
        if path.resolve() == reference_resolved:
            continue
        x, y = load_fresco_curve(path, thin=1, theta_max=None)
        if theta.min() < x.min() or theta.max() > x.max():
            raise ValueError(
                f"Envelope curve {path} does not cover the best-fit angular grid"
            )
        arrays.append(np.interp(theta, x, y))

    stack = np.vstack(arrays)
    lower = np.min(stack, axis=0)
    upper = np.max(stack, axis=0)
    lower = np.minimum(lower, best)
    upper = np.maximum(upper, best)

    lower_output = Path(lower_output)
    upper_output = Path(upper_output)
    lower_output.parent.mkdir(parents=True, exist_ok=True)
    upper_output.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(lower_output, np.column_stack((theta, lower)), fmt="%.10g")
    np.savetxt(upper_output, np.column_stack((theta, upper)), fmt="%.10g")
    return lower_output, upper_output


def chi_square_relative_difference(
    result: SfrescoFitResult,
    validation: CurveChiSquare,
) -> float:
    """Return the fractional SFRESCOX-vs-final-FRESCOX chi-square difference.

    SFRESCOX is the search engine, while the independently rerun FRESCOX curve
    is the artifact JCEfresco ultimately publishes and plots.  Small numerical
    differences can occur because the two paths do not necessarily reuse the
    identical internal solver state.
    """

    if result.sfresco_chisq is None:
        raise RuntimeError("SFRESCOX log did not contain a final total chi-square")
    scale = max(abs(result.sfresco_chisq), abs(validation.chisq), 1.0e-12)
    return abs(result.sfresco_chisq - validation.chisq) / scale


def validate_curve_chisq(
    result: SfrescoFitResult,
    validation: CurveChiSquare,
    *,
    fail_rel_tol: float = 0.10,
    abs_tol: float = 0.05,
) -> float:
    """Cross-check SFRESCOX against the exact standalone FRESCOX curve.

    A small discrepancy is diagnostic rather than fatal: SFRESCOX performs the
    search through its own repeated FRESCOX evaluations, whereas JCEfresco then
    reruns the final card from scratch and computes chi-square from the actual
    published ``fort.16`` curve.  Large disagreements still indicate broken
    bookkeeping or a stale calculation and are rejected.

    Returns the fractional disagreement for reporting.
    """

    if result.sfresco_chisq is None:
        raise RuntimeError("SFRESCOX log did not contain a final total chi-square")
    relative = chi_square_relative_difference(result, validation)
    if not math.isclose(
        result.sfresco_chisq,
        validation.chisq,
        rel_tol=fail_rel_tol,
        abs_tol=abs_tol,
    ):
        raise RuntimeError(
            "Final FRESCOX curve fails the independent chi-square cross-check: "
            f"SFRESCOX chi2={result.sfresco_chisq:.6g}, "
            f"JCEfresco chi2={validation.chisq:.6g} "
            f"({100.0 * relative:.2f}% difference). Refusing to publish the curve."
        )
    return relative


# ---------------------------------------------------------------------------
# Best-fit input / exact final FRESCOX curve / publication for plot.py
# ---------------------------------------------------------------------------

def _format_amplitude(value: float) -> str:
    text = f"{value:.12f}".rstrip("0")

    if text.endswith("."):
        return text + "000"

    whole, frac = text.split(".", 1)
    return f"{whole}.{frac.ljust(3, '0')}"

def write_best_fit_input(
    source: str | Path,
    destination: str | Path,
    *,
    cfp_number: int,
    amplitude: float,
) -> Path:
    """Change only ``A=`` in the selected ordered &CFP block."""

    source = Path(source)
    destination = Path(destination)
    text = source.read_text(encoding="utf-8", errors="replace")

    # Locate physical blocks in the original text so comments/formatting stay intact.
    # Converter-style zeroed terminators do not consume a physical CFP number.
    original_blocks = list(re.finditer(r"(?is)&\s*cfp\b(?:(?!&\s*cfp\b).)*?/", text))
    physical_blocks = []
    for match in original_blocks:
        block = match.group(0)
        if "=" not in block:
            continue
        if _is_cfp_terminator(_input_cfp_signature(block)):
            continue
        physical_blocks.append(match)

    if cfp_number < 1 or cfp_number > len(physical_blocks):
        raise ValueError(f"Physical CFP #{cfp_number} does not exist in {source}")

    target = physical_blocks[cfp_number - 1]
    old_block = target.group(0)
    a_re = re.compile(rf"(?i)(?<![A-Za-z0-9_])A\s*=\s*{_FLOAT_RE_TEXT}")
    if not a_re.search(old_block):
        raise ValueError(f"Selected CFP #{cfp_number} has no A= assignment to replace")

    new_block = a_re.sub(f"a=   {_format_amplitude(amplitude)}", old_block, count=1)
    updated = text[: target.start()] + new_block + text[target.end() :]

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(updated, encoding="utf-8")
    return destination


def _remove_stale_final_files(cwd: Path) -> None:
    for name in ("fort.3", "fort.13", "fort.16"):
        path = cwd / name
        if path.exists():
            path.unlink()


def run_frescox(
    *,
    executable: str | Path,
    input_file: str | Path,
    cwd: str | Path,
    log_file: str | Path,
    timeout: float | None = None,
    show_progress: bool = True,
    verbose: bool = False,
    stage: str = "final-frescox",
) -> Path:
    """Run one ordinary FRESCOX calculation with live progress."""

    cwd = Path(cwd)
    input_file = Path(input_file)
    log_file = Path(log_file)
    resolved = resolve_executable(executable)

    _remove_stale_final_files(cwd)
    text = input_file.read_text(encoding="utf-8", errors="replace")
    start = time.monotonic()

    def _handle(line: str) -> None:
        if verbose:
            print(f"[{stage}:raw] {line.rstrip()}", flush=True)

    if show_progress:
        print(f"[{stage}] starting FRESCOX calculation...", flush=True)
    returncode = _run_streaming_process(
        command=[resolved],
        input_text=text,
        cwd=cwd,
        log_file=log_file,
        timeout=timeout,
        line_handler=_handle,
        heartbeat_label=stage if show_progress else None,
    )
    if returncode != 0:
        raise RuntimeError(
            f"FRESCOX exited with status {returncode}. See {log_file}"
        )
    if not (cwd / "fort.16").is_file():
        raise RuntimeError(
            f"FRESCOX completed but did not produce {cwd / 'fort.16'}. See {log_file}"
        )
    if show_progress:
        print(
            f"[{stage}] finished in {_format_duration(time.monotonic() - start)}",
            flush=True,
        )
    return log_file


def run_frescox_curve_at_amplitude(
    *,
    source_input: str | Path,
    cfp_number: int,
    amplitude: float,
    run_dir: str | Path,
    state_file: str | Path,
    executable: str | Path = 'frescox',
    timeout: float | None = None,
    show_progress: bool = True,
    verbose: bool = False,
    stage_label: str = 'sigma',
) -> tuple[Path, Path, Path]:
    """Run an isolated FRESCOX calculation at one specified CFP amplitude.

    Returns ``(input_file, log_file, parsed_curve)``.  The calculation lives in
    its own directory so it cannot overwrite the best-fit fort.* files.
    """

    source_input = Path(source_input)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    local_source = run_dir / source_input.name
    if source_input.resolve() != local_source.resolve():
        shutil.copy2(source_input, local_source)

    varied_input = write_best_fit_input(
        local_source,
        run_dir / f'{stage_label}_{source_input.name}',
        cfp_number=cfp_number,
        amplitude=amplitude,
    )
    log_file = run_dir / f'{stage_label}_frescox.out'
    run_frescox(
        executable=executable,
        input_file=varied_input,
        cwd=run_dir,
        log_file=log_file,
        timeout=timeout,
        show_progress=show_progress,
        verbose=verbose,
        stage=stage_label,
    )
    local_dists = run_dir / 'fresco_dists'
    split_fort16(run_dir / 'fort.16', local_dists)
    curve = local_dists / Path(state_file).name
    if not curve.is_file():
        raise RuntimeError(
            f'FRESCOX uncertainty calculation did not produce requested curve {curve}'
        )
    return varied_input, log_file, curve


def split_and_publish_best_curve(
    *,
    fit_dir: str | Path,
    state_file: str | Path,
    publish_dir: str | Path,
    publish_name: str | None = None,
) -> tuple[Path, Path]:
    """Reuse split.py's core splitter, then publish a plot.py-compatible curve."""

    fit_dir = Path(fit_dir)
    state_name = Path(state_file).name
    local_dists = fit_dir / "fresco_dists"
    written = split_fort16(fit_dir / "fort.16", local_dists)

    local_curve = local_dists / state_name
    if local_curve not in written and not local_curve.is_file():
        raise ValueError(
            f"Best-fit fort.16 was split, but requested {state_name} was not produced"
        )

    # Build the same physics-focused map used by the normal split workflow when
    # the final FRESCOX run produced the needed bookkeeping files.
    try:
        build_cross_section_map(
            fit_dir,
            local_dists / "xsec_map.txt",
            fort3_name="fort.3",
            fort13_name="fort.13",
            fort16_name="fort.16",
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"[warn] best-fit xsec_map.txt not written: {exc}")

    publish_dir = Path(publish_dir)
    publish_dir.mkdir(parents=True, exist_ok=True)
    if publish_name is None:
        stem = Path(state_name).stem
        publish_name = f"{stem}_sfresco_fit.txt"
    published_curve = publish_dir / publish_name
    shutil.copy2(local_curve, published_curve)
    return local_curve, published_curve


def write_summary_json(
    path: str | Path,
    *,
    result: SfrescoFitResult,
    selected_cfp: NumberedCFP,
    reaction: str,
    model: str,
    state_keV: int,
    state_file: str,
    experimental_file: str | Path,
    published_curve: str | Path | None,
    sfresco_executable: str,
    fresco_executable: str,
    scan_best: ScanPoint | None = None,
    curve_validation: CurveChiSquare | None = None,
    profile_interval: ProfileInterval | None = None,
    chi2_profile_csv: str | Path | None = None,
    chi2_profile_plot: str | Path | None = None,
    sigma_low_curve: str | Path | None = None,
    sigma_high_curve: str | Path | None = None,
    uncertainty_band_method: str | None = None,
    amplitude_scaling_check: AmplitudeScalingCheck | None = None,
) -> Path:
    path = Path(path)
    payload = {
        "reaction": reaction,
        "model": model,
        "state_keV": state_keV,
        "state_file": state_file,
        "experimental_file": str(experimental_file),
        "cfp_number": selected_cfp.number,
        "cfp_in": selected_cfp.info.partition,
        "cfp_ib": selected_cfp.info.final_state,
        "cfp_ia": selected_cfp.info.core_state,
        "cfp_kn": selected_cfp.info.overlap_kn,
        "amplitude_initial": selected_cfp.info.amplitude,
        "amplitude_best": result.amplitude,
        "amplitude_error": result.amplitude_error,
        "spectroscopic_factor": result.spectroscopic_factor,
        "spectroscopic_factor_error": result.spectroscopic_factor_error,
        "n_points": result.n_points,
        "sfresco_chisq": result.sfresco_chisq,
        "sfresco_reduced_chisq": result.sfresco_reduced_chisq,
        "dof": result.dof,
        "fit_method": result.method,
        "converged": result.converged,
        "scan_best_amplitude": scan_best.amplitude if scan_best is not None else None,
        "scan_best_reduced_chisq": scan_best.reduced_chisq if scan_best is not None else None,
        "jcefresco_curve_chisq": curve_validation.chisq if curve_validation is not None else None,
        "jcefresco_curve_reduced_chisq": curve_validation.reduced_chisq if curve_validation is not None else None,
        "jcefresco_curve_max_abs_pull": curve_validation.max_abs_pull if curve_validation is not None else None,
        "profile_delta_chisq": profile_interval.delta_chisq if profile_interval is not None else None,
        "amplitude_1sigma_low": profile_interval.lower_amplitude if profile_interval is not None else None,
        "amplitude_1sigma_high": profile_interval.upper_amplitude if profile_interval is not None else None,
        "amplitude_1sigma_minus": profile_interval.minus if profile_interval is not None else None,
        "amplitude_1sigma_plus": profile_interval.plus if profile_interval is not None else None,
        "chi2_profile_csv": str(chi2_profile_csv) if chi2_profile_csv is not None else None,
        "chi2_profile_plot": str(chi2_profile_plot) if chi2_profile_plot is not None else None,
        "sigma_low_curve": str(sigma_low_curve) if sigma_low_curve is not None else None,
        "sigma_high_curve": str(sigma_high_curve) if sigma_high_curve is not None else None,
        "uncertainty_band_method": uncertainty_band_method,
        "amplitude_scaling_passed": (
            amplitude_scaling_check.passed
            if amplitude_scaling_check is not None
            else None
        ),
        "amplitude_scaling_rms_relative_difference": (
            amplitude_scaling_check.rms_relative_difference
            if amplitude_scaling_check is not None
            else None
        ),
        "amplitude_scaling_max_relative_difference": (
            amplitude_scaling_check.max_relative_difference
            if amplitude_scaling_check is not None
            else None
        ),
        "published_curve": str(published_curve) if published_curve is not None else None,
        "sfresco_executable": sfresco_executable,
        "fresco_executable": fresco_executable,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
