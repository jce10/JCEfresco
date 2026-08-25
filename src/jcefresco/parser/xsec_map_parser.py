from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import argparse

from typing import Any


"""Build a physics-focused FRESCO cross-section map.

Primary sources
---------------
fort.3
    FRESCO's expanded namelist bookkeeping.  This is treated as the source of
    truth for partitions, states, overlaps, couplings, CFP/spec amplitudes, and
    basic calculation controls.

fort.16
    Differential-cross-section table.  Its Grace/Xmgrace legend lines provide
    the partition/state ordering used by ``elastic.txt`` / ``stateN.txt``.

fort.13
    Integrated channel cross sections.  This parser is intentionally tolerant:
    the file is optional, and its numeric rows are preserved even when a
    particular FRESCO build uses a layout we have not yet specialized.

The standard .fro/.out file is deliberately not required.
"""


FLOAT_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?$"
)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class StateInfo:
    index: int
    projectile_j: float | None = None
    projectile_parity: int | None = None
    projectile_energy: float | None = None
    target_j: float | None = None
    target_parity: int | None = None
    target_energy: float | None = None
    cpot: int | None = None


@dataclass
class PartitionInfo:
    index: int
    projectile: str
    target: str
    q_value: float | None = None
    states: dict[int, StateInfo] = field(default_factory=dict)


@dataclass
class OverlapInfo:
    kn: int
    partition: int | None
    nn: int | None
    l: int | None
    s: float | None
    j: float | None
    binding_energy: float | None
    kind: int | None
    kbpot: int | None


@dataclass
class CFPInfo:
    partition: int
    final_state: int
    core_state: int
    overlap_kn: int
    amplitude: float


@dataclass
class CouplingInfo:
    number: int
    to_partition: int | None
    from_partition: int | None
    kind: int | None
    ip1: int | None
    ip2: int | None
    ip3: int | None
    ip4: int | None
    ip5: int | None


@dataclass
class CurveInfo:
    state_number: int
    partition: int
    excitation: int
    near_far: int | None = None
    lab_energy: float | None = None


@dataclass
class Fort13StateXsec:
    partition: int
    state: int
    projectile_j: float
    projectile_parity: int
    projectile_energy: float
    target_j: float
    target_parity: int
    target_energy: float
    cross_section_mb: float
    extra_values: list[float] = field(default_factory=list)


@dataclass
class Fort13Data:
    beam_energy: float | None = None
    states: dict[tuple[int, int], Fort13StateXsec] = field(default_factory=dict)
    header_values: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Generic fort.3 namelist parsing
# ---------------------------------------------------------------------------

def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("D", "E").replace("d", "e")
    try:
        return float(text)
    except ValueError:
        return None


def _as_int(value: Any) -> int | None:
    f = _as_float(value)
    if f is None:
        return None
    return int(round(f))


def _first_scalar(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _parse_scalar(text: str) -> Any:
    text = text.strip()
    if not text:
        return ""

    upper = text.upper()
    if upper in {"T", ".TRUE."}:
        return True
    if upper in {"F", ".FALSE."}:
        return False

    if (text.startswith("'") and text.endswith("'")) or (
        text.startswith('"') and text.endswith('"')
    ):
        return _strip_quotes(text)

    numeric = text.replace("D", "E").replace("d", "e")
    if FLOAT_RE.match(numeric):
        try:
            if not any(ch in numeric for ch in ".Ee"):
                return int(numeric)
            return float(numeric)
        except ValueError:
            pass

    return text


def _split_assignments(body: str) -> list[str]:
    """Split a namelist body on commas outside quoted strings."""
    out: list[str] = []
    buf: list[str] = []
    quote: str | None = None

    for ch in body:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue

        if ch in {"'", '"'}:
            quote = ch
            buf.append(ch)
        elif ch == ",":
            item = "".join(buf).strip()
            if item:
                out.append(item)
            buf = []
        else:
            buf.append(ch)

    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _parse_namelist_block(body: str) -> dict[str, Any]:
    """Parse scalar namelist assignments needed by the map.

    Array continuations such as ``P=..., ..., ...`` are intentionally retained
    only through the first explicit assignment value because the cross-section
    map does not currently summarize full optical-potential arrays.
    """
    result: dict[str, Any] = {}
    current_key: str | None = None

    for item in _split_assignments(body):
        if "=" in item:
            key, value = item.split("=", 1)
            key = key.strip().upper()
            current_key = key
            result[key] = _parse_scalar(value)
        elif current_key is not None:
            # Continuation of an array-valued assignment. Keep it available for
            # future extensions without affecting scalar fields used today.
            old = result[current_key]
            if not isinstance(old, list):
                old = [old]
            old.append(_parse_scalar(item))
            result[current_key] = old

    return result


def parse_fort3_blocks(path: str | Path) -> tuple[list[tuple[str, dict[str, Any]]], str | None]:
    """Read actual fort.3 namelist blocks line-by-line.

    FRESCO also writes section sentinels such as ``&partition /`` and
    ``&overlap /``.  Those are not real data blocks and are ignored.
    """
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    title: str | None = None
    for i, line in enumerate(lines):
        if line.strip().upper() == "NAMELIST":
            for previous in reversed(lines[:i]):
                if previous.strip():
                    title = previous.strip()
                    break
            break

    blocks: list[tuple[str, dict[str, Any]]] = []
    i = 0

    start_re = re.compile(r"^\s*&([A-Za-z][A-Za-z0-9_]*)\b(.*)$")

    while i < len(lines):
        line = lines[i]
        match = start_re.match(line)
        if not match:
            i += 1
            continue

        name = match.group(1).upper()
        remainder = match.group(2).strip()

        # FRESCO writes section-ending markers such as:
        #     &partition /
        #     &overlap /
        # They contain no assignments and must not be interpreted as blocks.
        if remainder == "/" or (remainder.endswith("/") and "=" not in remainder):
            i += 1
            continue

        body_parts: list[str] = []
        if remainder:
            # A real block may theoretically begin assignments on the same line.
            if remainder.endswith("/"):
                body_parts.append(remainder[:-1])
                body = "\n".join(body_parts)
                if "=" in body:
                    blocks.append((name, _parse_namelist_block(body)))
                i += 1
                continue
            body_parts.append(remainder)

        i += 1
        while i < len(lines):
            current = lines[i]
            if current.strip() == "/":
                break
            body_parts.append(current)
            i += 1

        body = "\n".join(body_parts).strip()
        if body and "=" in body:
            blocks.append((name, _parse_namelist_block(body)))

        # Move past the terminating slash when present.
        if i < len(lines) and lines[i].strip() == "/":
            i += 1

    return blocks, title


def parse_fort3(path: str | Path):
    blocks, title = parse_fort3_blocks(path)

    partitions: dict[int, PartitionInfo] = {}
    overlaps: dict[int, OverlapInfo] = {}
    cfps: list[CFPInfo] = []
    couplings: list[CouplingInfo] = []
    fresco: dict[str, Any] = {}

    current_partition: PartitionInfo | None = None

    for name, data in blocks:
        if name == "PARTITION":
            idx = len(partitions) + 1
            current_partition = PartitionInfo(
                index=idx,
                projectile=str(_first_scalar(data.get("NAMEP", ""))).strip(),
                target=str(_first_scalar(data.get("NAMET", ""))).strip(),
                q_value=_as_float(_first_scalar(data.get("QVAL"))),
            )
            partitions[idx] = current_partition

        elif name == "STATES" and current_partition is not None:
            idx = len(current_partition.states) + 1

            jp = _as_float(_first_scalar(data.get("JP")))
            ep = _as_float(_first_scalar(data.get("EP")))
            j_t = _as_float(_first_scalar(data.get("JT")))
            e_t = _as_float(_first_scalar(data.get("ET")))

            # COPYP/COPYT are commonly used for repeated channel copies. Resolve
            # the visible projectile/target quantum numbers from the referenced
            # earlier state whenever possible.
            copy_p = _as_int(_first_scalar(data.get("COPYP"))) or 0
            copy_t = _as_int(_first_scalar(data.get("COPYT"))) or 0

            if copy_p and current_partition.states:
                source = current_partition.states.get(copy_p)
                if source is None:
                    source = current_partition.states[min(current_partition.states)]
                jp = source.projectile_j
                ep = source.projectile_energy
                ptyp = source.projectile_parity
            else:
                ptyp = _as_int(_first_scalar(data.get("PTYP")))

            if copy_t and current_partition.states:
                source = current_partition.states.get(copy_t)
                if source is None:
                    source = current_partition.states[min(current_partition.states)]
                j_t = source.target_j
                e_t = source.target_energy
                ptyt = source.target_parity
            else:
                ptyt = _as_int(_first_scalar(data.get("PTYT")))

            current_partition.states[idx] = StateInfo(
                index=idx,
                projectile_j=jp,
                projectile_parity=ptyp,
                projectile_energy=ep,
                target_j=j_t,
                target_parity=ptyt,
                target_energy=e_t,
                cpot=_as_int(_first_scalar(data.get("CPOT"))),
            )

        elif name == "OVERLAP":
            kn = _as_int(_first_scalar(data.get("KN1")))
            if kn is None:
                continue
            overlaps[kn] = OverlapInfo(
                kn=kn,
                partition=_as_int(_first_scalar(data.get("IN"))),
                nn=_as_int(_first_scalar(data.get("NN"))),
                l=_as_int(_first_scalar(data.get("L"))),
                s=_as_float(_first_scalar(data.get("SN"))),
                j=_as_float(_first_scalar(data.get("J"))),
                binding_energy=_as_float(_first_scalar(data.get("BE"))),
                kind=_as_int(_first_scalar(data.get("KIND"))),
                kbpot=_as_int(_first_scalar(data.get("KBPOT"))),
            )

        elif name == "CFP":
            partition = _as_int(_first_scalar(data.get("IN")))
            ib = _as_int(_first_scalar(data.get("IB")))
            ia = _as_int(_first_scalar(data.get("IA")))
            kn = _as_int(_first_scalar(data.get("KN")))
            amp = _as_float(_first_scalar(data.get("A")))
            if None not in (partition, ib, ia, kn, amp):
                cfps.append(
                    CFPInfo(
                        partition=partition,
                        final_state=ib,
                        core_state=ia,
                        overlap_kn=kn,
                        amplitude=amp,
                    )
                )

        elif name == "COUPLING":
            couplings.append(
                CouplingInfo(
                    number=len(couplings) + 1,
                    to_partition=_as_int(_first_scalar(data.get("ICTO"))),
                    from_partition=_as_int(_first_scalar(data.get("ICFROM"))),
                    kind=_as_int(_first_scalar(data.get("KIND"))),
                    ip1=_as_int(_first_scalar(data.get("IP1"))),
                    ip2=_as_int(_first_scalar(data.get("IP2"))),
                    ip3=_as_int(_first_scalar(data.get("IP3"))),
                    ip4=_as_int(_first_scalar(data.get("IP4"))),
                    ip5=_as_int(_first_scalar(data.get("IP5"))),
                )
            )

        elif name == "FRESCO":
            fresco = data

    return title, partitions, overlaps, cfps, couplings, fresco


# ---------------------------------------------------------------------------
# fort.16: stateN.txt -> partition/excitation mapping
# ---------------------------------------------------------------------------

FORT16_LEGEND_RE = re.compile(
    # r'legend\s+"Partition=\s*(?P<partition>\d+)\s+'
    # r'Excit=\s*(?P<excitation>\d+)\s+near/far=\s*(?P<nearfar>-?\d+)"',
    # re.IGNORECASE,
    r'Partition=\s*(?P<partition>\d+)\s+'
    r'Excit=\s*(?P<excitation>\d+)\s+'
    r'near/far=\s*(?P<nearfar>-?\d+)',
    re.IGNORECASE,

)

FORT16_ENERGY_RE = re.compile(
    r"Lab energy\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?)",
    re.IGNORECASE,
)


def parse_fort16(path: str | Path) -> list[CurveInfo]:
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    curves: list[CurveInfo] = []
    for i, line in enumerate(lines):
        match = FORT16_LEGEND_RE.search(line)
        if not match:
            continue

        lab_energy = None
        for later in lines[i + 1 : min(i + 5, len(lines))]:
            em = FORT16_ENERGY_RE.search(later)
            if em:
                lab_energy = float(em.group(1).replace("D", "E").replace("d", "e"))
                break

        curves.append(
            CurveInfo(
                state_number=len(curves),
                partition=int(match.group("partition")),
                excitation=int(match.group("excitation")),
                near_far=int(match.group("nearfar")),
                lab_energy=lab_energy,
            )
        )

    return curves


# ---------------------------------------------------------------------------
# fort.13: deliberately tolerant first-pass reader
# ---------------------------------------------------------------------------

def parse_fort13(path: str | Path) -> Fort13Data:
    """Parse FRESCO ``fort.13`` total cross sections by partition and state.

    The observed FRESCO layout is::

        Integrated cross sections for all states
        <run header>
        <partition_index> <number_of_states>
        Jp Pp Ep  Jt Pt Et  sigma [extra elastic/global values...]
        ...

    ``sigma`` is the first value following the six state-identification
    columns.  Some FRESCO builds append additional values to the elastic
    entrance-channel row; these are retained in ``extra_values`` but are not
    assigned a physical label here.
    """
    path = Path(path)
    raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = [line.strip() for line in raw_lines if line.strip()]

    data = Fort13Data()
    if not lines:
        return data

    i = 0

    if lines[0].lower().startswith("integrated cross sections"):
        i += 1

    # FRESCO writes one run-header line before the partition blocks.  Preserve
    # it without depending on every field's undocumented meaning. ELAB is the
    # fourth numeric field in the layout produced by the current FRESCO build.
    if i < len(lines):
        header_tokens = lines[i].replace("D", "E").replace("d", "e").split()
        try:
            header_values = [float(token) for token in header_tokens]
        except ValueError:
            header_values = []

        if len(header_values) >= 4:
            data.header_values = header_values
            data.beam_energy = header_values[3]
            i += 1

    while i < len(lines):
        header = lines[i].split()

        # A partition header contains exactly two integer-valued fields:
        #     partition_number  number_of_states
        if len(header) != 2:
            i += 1
            continue

        try:
            partition = int(header[0])
            nstates = int(header[1])
        except ValueError:
            i += 1
            continue

        i += 1

        for state_index in range(1, nstates + 1):
            if i >= len(lines):
                raise ValueError(
                    f"Malformed {path}: partition {partition} declares "
                    f"{nstates} states but the file ended early"
                )

            tokens = lines[i].replace("D", "E").replace("d", "e").split()
            i += 1

            if len(tokens) < 7:
                raise ValueError(
                    f"Malformed {path}: expected at least 7 values for "
                    f"partition {partition}, state {state_index}; got {tokens!r}"
                )

            try:
                values = [float(token) for token in tokens]
            except ValueError as exc:
                raise ValueError(
                    f"Malformed {path}: non-numeric state row for "
                    f"partition {partition}, state {state_index}: {tokens!r}"
                ) from exc

            data.states[(partition, state_index)] = Fort13StateXsec(
                partition=partition,
                state=state_index,
                projectile_j=values[0],
                projectile_parity=int(round(values[1])),
                projectile_energy=values[2],
                target_j=values[3],
                target_parity=int(round(values[4])),
                target_energy=values[5],
                cross_section_mb=values[6],
                extra_values=values[7:],
            )

    return data


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _parity(value: int | None) -> str:
    if value is None:
        return "?"
    return "+" if value >= 0 else "-"


def _j(value: float | None) -> str:
    if value is None:
        return "?"
    twice = round(2 * value)
    if abs(value * 2 - twice) < 1e-6:
        if twice % 2 == 0:
            return str(twice // 2)
        return f"{twice}/2"
    return f"{value:g}"


def _state_channel(partition: PartitionInfo, state: StateInfo) -> str:
    return (
        f"{partition.projectile}({_j(state.projectile_j)}{_parity(state.projectile_parity)}) + "
        f"{partition.target}({_j(state.target_j)}{_parity(state.target_parity)}, "
        f"Ex={state.target_energy or 0.0:.4f} MeV)"
    )


def _fmt_amp(value: float) -> str:
    return f"{value:+.6g}"


def _ip2_label(ip2: int | None) -> str | None:
    # Labels are kept intentionally conservative and match the common FRESCO
    # transfer bookkeeping used in the current JCEfresco calculations.
    return {
        -1: "COMPLEX",
        -2: "NONO+COMPLEX",
    }.get(ip2)


def _form_label(ip1: int | None) -> str | None:
    # FRESCO transfer convention used by KIND=7 calculations.
    return {
        0: "POST",
        1: "PRIOR",
    }.get(ip1)


# ---------------------------------------------------------------------------
# Map writer
# ---------------------------------------------------------------------------

def build_cross_section_map(
    directory: str | Path = ".",
    output_file: str | Path | None = None,
    *,
    fort3_name: str = "fort.3",
    fort13_name: str = "fort.13",
    fort16_name: str = "fort.16",
    include_zero_amplitudes: bool = True,
) -> Path:
    directory = Path(directory)
    fort3 = directory / fort3_name
    fort16 = directory / fort16_name
    fort13 = directory / fort13_name

    if not fort3.is_file():
        raise FileNotFoundError(f"Could not find required bookkeeping file: {fort3}")
    if not fort16.is_file():
        raise FileNotFoundError(f"Could not find required cross-section file: {fort16}")

    if output_file is None:
        output_path = directory / "xsec_map.txt"
    else:
        output_path = Path(output_file)
        if not output_path.is_absolute():
            output_path = directory / output_path

    title, partitions, overlaps, cfps, couplings, fresco = parse_fort3(fort3)
    curves = parse_fort16(fort16)
    totals = parse_fort13(fort13) if fort13.is_file() else None

    # If fort.16 is absent-minded about a curve or an old build omits legends,
    # fail loudly rather than silently making a wrong state assignment.
    if not curves:
        raise ValueError(f"No Partition/Excit legends found in {fort16}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as out:
        out.write("=" * 80 + "\n")
        out.write("FRESCO CROSS-SECTION MAP\n")
        out.write("=" * 80 + "\n\n")

        out.write("SOURCES\n-------\n")
        out.write(f"physics bookkeeping : {fort3.name}\n")
        out.write(f"curve/state map      : {fort16.name}\n")
        out.write(
            f"integrated xsecs     : {fort13.name if fort13.is_file() else '[fort.13 not found]'}\n\n"
        )

        out.write("CALCULATION\n-----------\n")
        if title:
            out.write(f"Title           : {title}\n")

        elab = _as_float(_first_scalar(fresco.get("ELAB")))
        if elab is not None:
            out.write(f"Beam energy     : {elab:.4f} MeV lab\n")

        thmin = _as_float(_first_scalar(fresco.get("THMIN")))
        thmax = _as_float(_first_scalar(fresco.get("THMAX")))
        thinc = _as_float(_first_scalar(fresco.get("THINC")))
        if thmin is not None and thmax is not None:
            out.write(f"Theta range     : {thmin:.2f} - {thmax:.2f} deg\n")
        if thinc is not None:
            out.write(f"Theta step      : {thinc:.3f} deg\n")

        jtmax = _as_float(_first_scalar(fresco.get("JTMAX")))
        if jtmax is not None:
            out.write(f"Jmax            : {jtmax:g}\n")

        iters = _as_int(_first_scalar(fresco.get("ITER")))
        if iters is not None:
            out.write(f"Iterations max  : {iters}\n")
        out.write("\n")

        out.write("REACTION PARTITIONS\n-------------------\n")
        for pidx in sorted(partitions):
            partition = partitions[pidx]
            q = (
                f"{partition.q_value:+.4f} MeV"
                if partition.q_value is not None
                else "unknown"
            )
            out.write(
                f"Partition {pidx}: {partition.projectile} + {partition.target}    Q = {q}\n"
            )
            for sidx in sorted(partition.states):
                out.write(
                    f"    state {sidx}: {_state_channel(partition, partition.states[sidx])}\n"
                )
            out.write("\n")

        if couplings:
            out.write("TRANSFER / REACTION COUPLINGS\n-----------------------------\n")
            for coupling in couplings:
                route = ""
                if coupling.to_partition is not None and coupling.from_partition is not None:
                    route = (
                        f"    partitions      : {coupling.to_partition} <- "
                        f"{coupling.from_partition}\n"
                    )
                out.write(f"Coupling #{coupling.number}\n")
                if coupling.kind is not None:
                    out.write(f"    KIND            : {coupling.kind}\n")
                if route:
                    out.write(route)

                if coupling.kind == 7:
                    out.write("    type            : finite-range transfer\n")

                form = _form_label(coupling.ip1)
                if form:
                    out.write(f"    form            : {form}\n")
                if coupling.ip1 is not None:
                    out.write(f"    IP1             : {coupling.ip1}\n")
                if coupling.ip2 is not None:
                    label = _ip2_label(coupling.ip2)
                    suffix = f" ({label})" if label else ""
                    out.write(f"    IP2             : {coupling.ip2}{suffix}\n")
                out.write("\n")

        out.write("OVERLAP DEFINITIONS\n-------------------\n")
        for kn in sorted(overlaps):
            ov = overlaps[kn]
            out.write(f"Overlap KN={kn}\n")
            if ov.partition is not None:
                out.write(f"    partition       : {ov.partition}\n")
            out.write(
                "    quantum numbers : "
                f"NN={ov.nn if ov.nn is not None else '?'}, "
                f"s={_j(ov.s)}, "
                f"l={ov.l if ov.l is not None else '?'}, "
                f"j={_j(ov.j)}\n"
            )
            if ov.l is not None:
                out.write(f"    l-transfer      : {ov.l}\n")
            if ov.binding_energy is not None:
                out.write(f"    binding energy  : {ov.binding_energy:.4f} MeV\n")
            if ov.kind is not None:
                out.write(f"    overlap KIND    : {ov.kind}\n")
            if ov.kbpot is not None:
                out.write(f"    binding pot     : {ov.kbpot}\n")
            out.write("\n")

        if totals is not None:
            out.write("INTEGRATED CHANNEL CROSS SECTIONS (fort.13)\n")
            out.write("-------------------------------------------\n")
            for key in sorted(totals.states):
                item = totals.states[key]
                out.write(
                    f"partition {item.partition}, state {item.state}: "
                    f"{item.cross_section_mb:.6g} mb\n"
                )
            out.write("\n")

        out.write("=" * 80 + "\n")
        out.write("PARSED CROSS-SECTIONS\n")
        out.write("=" * 80 + "\n\n")

        for curve in curves:
            filename = "elastic.txt" if curve.state_number == 0 else f"state{curve.state_number}.txt"
            out.write(f"{filename}\n")
            out.write("-" * 40 + "\n")
            out.write(
                f"FRESCO mapping : partition {curve.partition}, state {curve.excitation}"
            )
            if curve.near_far is not None:
                out.write(f", near/far={curve.near_far}")
            out.write("\n")

            partition = partitions.get(curve.partition)
            state = (
                partition.states.get(curve.excitation)
                if partition is not None
                else None
            )

            if partition is not None and state is not None:
                out.write(f"Channel        : {_state_channel(partition, state)}\n")

            relevant_cfps = [
                cfp
                for cfp in cfps
                if cfp.partition == curve.partition
                and cfp.final_state == curve.excitation
                and (include_zero_amplitudes or abs(cfp.amplitude) > 0.0)
            ]

            # Projectile overlap CFPs (e.g. d -> p+n) and final-nucleus CFPs are
            # both present in fort.3. For the plotted transfer channels, the
            # structure information of interest is the final-state partition.
            if relevant_cfps and curve.partition != 1:
                out.write("\nTransfer configurations:\n\n")

                entrance = partitions.get(1)
                for cfp in relevant_cfps:
                    overlap = overlaps.get(cfp.overlap_kn)

                    core_label = f"partition 1 state {cfp.core_state}"
                    if entrance is not None:
                        core = entrance.states.get(cfp.core_state)
                        if core is not None:
                            core_label = (
                                f"{entrance.target}({_j(core.target_j)}"
                                f"{_parity(core.target_parity)}, "
                                f"Ex={core.target_energy or 0.0:.4f} MeV)"
                            )

                    final_label = partition.target if partition else f"partition {curve.partition}"
                    if state is not None and partition is not None:
                        final_label = (
                            f"{partition.target}({_j(state.target_j)}"
                            f"{_parity(state.target_parity)}, "
                            f"Ex={state.target_energy or 0.0:.4f} MeV)"
                        )

                    out.write(
                        f"    {core_label} + transferred particle -> {final_label}\n"
                    )
                    out.write(f"        overlap KN      : {cfp.overlap_kn}\n")

                    if overlap is not None:
                        out.write(
                            "        quantum numbers : "
                            f"NN={overlap.nn if overlap.nn is not None else '?'}, "
                            f"s={_j(overlap.s)}, "
                            f"l={overlap.l if overlap.l is not None else '?'}, "
                            f"j={_j(overlap.j)}\n"
                        )
                        if overlap.l is not None:
                            out.write(f"        l-transfer      : {overlap.l}\n")
                        if overlap.binding_energy is not None:
                            out.write(
                                f"        binding energy  : {overlap.binding_energy:.4f} MeV\n"
                            )

                    out.write(f"        SpecAmp (CFP A) : {_fmt_amp(cfp.amplitude)}\n\n")

            if curve.lab_energy is not None:
                out.write(f"Lab energy      : {curve.lab_energy:.4f} MeV\n")

            if totals is not None:
                total = totals.states.get((curve.partition, curve.excitation))
                if total is not None:
                    out.write(
                        f"Integrated xsec : {total.cross_section_mb:.6g} mb "
                        f"(fort.13)\n"
                    )

            out.write("\n")

    print(f"[wrote] {output_path}")
    print(f"[map] {len(curves)} fort.16 curve(s), {len(overlaps)} overlap(s), {len(cfps)} CFP(s)")
    if not fort13.is_file():
        print(f"[warn] {fort13.name} not found; integrated cross sections omitted")
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build an xsec_map.txt from FRESCO fort.3 bookkeeping, fort.16 "
            "curve labels, and optional fort.13 integrated cross sections."
        )
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        type=Path,
        help="FRESCO calculation directory containing fort.3/fort.16/fort.13.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output map path. Default: <directory>/xsec_map.txt",
    )
    parser.add_argument("--fort3", default="fort.3")
    parser.add_argument("--fort13", default="fort.13")
    parser.add_argument("--fort16", default="fort.16")
    parser.add_argument(
        "--hide-zero-specamps",
        action="store_true",
        help="Do not print CFP entries whose SpecAmp is exactly zero.",
    )

    args = parser.parse_args()
    build_cross_section_map(
        args.directory,
        args.out,
        fort3_name=args.fort3,
        fort13_name=args.fort13,
        fort16_name=args.fort16,
        include_zero_amplitudes=not args.hide_zero_specamps,
    )


if __name__ == "__main__":
    main()
