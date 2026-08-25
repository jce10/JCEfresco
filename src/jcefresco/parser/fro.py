from __future__ import annotations

from pathlib import Path
import re


FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"


def _parse_calculation_info(lines: list[str]) -> dict[str, object]:
    """Extract high-level run information from the human-readable FRESCO output."""
    info: dict[str, object] = {}

    # Version banner.
    for line in lines[:20]:
        match = re.search(r"FRESCO\s*-\s*(FRES\s+\S+)", line, re.IGNORECASE)
        if match:
            info["version"] = match.group(1)
            break

    # Calculation title.  In the outputs used by JCEfresco this is normally the
    # first descriptive line after the banner / NAMELIST notice.
    for line in lines[:100]:
        stripped = line.strip()
        if not stripped:
            continue
        if "Coupled Reaction Channels" in stripped:
            continue
        if stripped.lower().startswith("assuming namelist"):
            continue
        if stripped.startswith(("FRESCO", "FRES ")):
            continue

        # A reaction title usually contains parentheses and/or an arrow/reaction
        # notation. Avoid overfitting to one exact reaction string.
        if re.search(r"\([^)]*\)", stripped) and any(
            token in stripped for token in ("MeV", "(d,p)", "(d,n)", "CCBA", "DWBA", "CRC", "CDCC")
        ):
            info["title"] = stripped
            break

    # Angular controls.
    for line in lines[:150]:
        match = re.search(
            rf"Theta from\s+({FLOAT})\s+to\s+({FLOAT})\s+in steps of\s+({FLOAT})",
            line,
            re.IGNORECASE,
        )
        if match:
            info["theta_min"] = float(match.group(1).replace("D", "E"))
            info["theta_max"] = float(match.group(2).replace("D", "E"))
            info["theta_step"] = float(match.group(3).replace("D", "E"))

        match = re.search(
            rf"Range of total J is\s+({FLOAT})\s+<=\s*J\s*<=\s*({FLOAT})",
            line,
            re.IGNORECASE,
        )
        if match:
            info["j_min"] = float(match.group(1).replace("D", "E"))
            info["j_max"] = float(match.group(2).replace("D", "E"))

        match = re.search(
            r"Iterate Couplings between\s+(\d+)\s+and\s+(\d+)\s+times,\s*to\s*([\d.]+)\s*%",
            line,
            re.IGNORECASE,
        )
        if match:
            info["iter_min"] = int(match.group(1))
            info["iter_max"] = int(match.group(2))
            info["iter_tol_percent"] = float(match.group(3))

    # Beam energy.
    for line in lines:
        match = re.search(
            rf"LABORATORY\s+\S+\s+ENERGY\s*=\s*({FLOAT})\s+MeV",
            line,
            re.IGNORECASE,
        )
        if match:
            info["beam_energy"] = float(match.group(1).replace("D", "E"))
            break

    return info


def _parse_transfer_info(lines: list[str]) -> dict[str, object]:
    """Record coupling bookkeeping exactly as FRESCO prints it.

    This deliberately does not infer DWBA/CCBA/CRC from filenames or model
    names.  It reports ONE-way/TWO-way, KIND, and finite-range settings from
    the output itself.
    """
    couplings: list[dict[str, object]] = []
    finite_range: dict[str, object] = {}

    coupling_re = re.compile(
        r"\b(ONE|TWO)-way\s+COUPLING\s*#\s*(\d+).*?"
        r"(?:partitions?\s+(-?\d+)\s*<-\s*(-?\d+).*?)?"
        r"of\s+KIND\s+(-?\d+)",
        re.IGNORECASE,
    )

    for line in lines:
        match = coupling_re.search(line)
        if match:
            entry: dict[str, object] = {
                "direction": f"{match.group(1).upper()}-way",
                "number": int(match.group(2)),
                "kind": int(match.group(5)),
            }
            if match.group(3) is not None:
                entry["to_partition"] = int(match.group(3))
            if match.group(4) is not None:
                entry["from_partition"] = int(match.group(4))
            couplings.append(entry)

        match = re.search(
            r"So\s+FINITE-RANGE\s+TRANSFER\s*:\s*"
            r"IP1\s*=\s*(-?\d+)\s*\(([^)]+)\),\s*"
            r"IP2\s*=\s*(-?\d+)\s*=\s*([^,]+)",
            line,
            re.IGNORECASE,
        )
        if match:
            finite_range = {
                "type": "finite-range",
                "ip1": int(match.group(1)),
                "form": match.group(2).strip(),
                "ip2": int(match.group(3)),
                "ip2_label": match.group(4).strip(),
            }

    return {
        "couplings": couplings,
        "finite_range": finite_range,
    }


def _parse_global_cross_sections(lines: list[str]) -> dict[str, float]:
    """Extract only global/cumulative reaction quantities from the output.

    Per-state integrated cross sections now belong to fort.13 and are therefore
    intentionally not scraped here.
    """
    totals: dict[str, float] = {}

    patterns = {
        "reaction": rf"CUMULATIVE\s+REACTION\s+cross section\s*=\s*({FLOAT})",
        "outgoing": rf"CUMULATIVE\s+OUTGOING\s+cross section\s*=\s*({FLOAT})",
        "absorption": rf"Cumulative\s+ABSORBTION\s+by\s+Imaginary\s+Potentials\s*=\s*({FLOAT})",
    }

    for line in lines:
        for key, pattern in patterns.items():
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                totals[key] = float(match.group(1).replace("D", "E"))

    return totals


def _parse_convergence_notes(lines: list[str]) -> list[str]:
    """Collect a small set of useful convergence/solver diagnostics.

    Keep this intentionally conservative: only lines that explicitly mention
    iteration/convergence/failure are surfaced.
    """
    notes: list[str] = []
    seen: set[str] = set()

    keywords = (
        "converg",
        "iteration",
        "iterations",
        "fail in",
        "not converged",
        "convergence",
    )

    for line in lines:
        stripped = " ".join(line.split())
        if not stripped:
            continue

        lower = stripped.lower()
        if not any(word in lower for word in keywords):
            continue

        # Skip the standard input-control sentence because that information is
        # already summarized separately by _parse_calculation_info().
        if lower.startswith("iterate couplings between"):
            continue

        if stripped not in seen:
            seen.add(stripped)
            notes.append(stripped)

    return notes


def _write_output_summary(
    output_path: Path,
    info: dict[str, object],
    transfer: dict[str, object],
    totals: dict[str, float],
    convergence_notes: list[str],
) -> None:
    with output_path.open("w", encoding="utf-8") as out:
        out.write("=" * 80 + "\n")
        out.write("FRESCO OUTPUT SUMMARY\n")
        out.write("=" * 80 + "\n\n")

        out.write(
            "This file summarizes information taken from the human-readable "
            "FRESCO .fro/.out report.\n"
        )
        out.write(
            "State bookkeeping, overlaps, spectroscopic amplitudes, and "
            "per-state integrated cross sections are intentionally handled by "
            "xsec_map.txt using fort.3, fort.13, and fort.16.\n\n"
        )

        out.write("CALCULATION\n-----------\n")
        if "title" in info:
            out.write(f"Title           : {info['title']}\n")
        if "version" in info:
            out.write(f"FRESCO version  : {info['version']}\n")
        if "beam_energy" in info:
            out.write(f"Beam energy     : {info['beam_energy']:.4f} MeV lab\n")
        if all(key in info for key in ("theta_min", "theta_max")):
            out.write(
                f"Theta range     : {info['theta_min']:.2f} - "
                f"{info['theta_max']:.2f} deg\n"
            )
        if "theta_step" in info:
            out.write(f"Theta step      : {info['theta_step']:.4f} deg\n")
        if "j_min" in info and "j_max" in info:
            out.write(f"Total-J range  : {info['j_min']:g} - {info['j_max']:g}\n")
        elif "j_max" in info:
            out.write(f"Jmax            : {info['j_max']:g}\n")
        if "iter_min" in info and "iter_max" in info:
            out.write(
                f"Iterations      : {info['iter_min']} - {info['iter_max']}"
            )
            if "iter_tol_percent" in info:
                out.write(f" (tolerance {info['iter_tol_percent']:g}%)")
            out.write("\n")
        out.write("\n")

        couplings = transfer.get("couplings", [])
        finite_range = transfer.get("finite_range", {})

        if couplings or finite_range:
            out.write("COUPLING / TRANSFER OUTPUT\n--------------------------\n")

            for coupling in couplings:
                out.write(f"Coupling #{coupling['number']}\n")
                out.write(f"    direction       : {coupling['direction']}\n")
                out.write(f"    KIND            : {coupling['kind']}\n")
                if "to_partition" in coupling and "from_partition" in coupling:
                    out.write(
                        f"    partitions      : {coupling['to_partition']} <- "
                        f"{coupling['from_partition']}\n"
                    )
                out.write("\n")

            if finite_range:
                out.write("Finite-range transfer\n")
                out.write(f"    type            : {finite_range['type']}\n")
                out.write(f"    form            : {finite_range['form']}\n")
                out.write(f"    IP1             : {finite_range['ip1']}\n")
                label = (
                    f" ({finite_range['ip2_label']})"
                    if finite_range.get("ip2_label")
                    else ""
                )
                out.write(f"    IP2             : {finite_range['ip2']}{label}\n")
                out.write("\n")

        if totals:
            out.write("GLOBAL CROSS SECTIONS\n---------------------\n")
            if "outgoing" in totals:
                out.write(f"Cumulative outgoing : {totals['outgoing']:.6g} mb\n")
            if "reaction" in totals:
                out.write(f"Cumulative reaction : {totals['reaction']:.6g} mb\n")
            if "absorption" in totals:
                out.write(f"Absorption          : {totals['absorption']:.6g} mb\n")
            out.write("\n")

        if convergence_notes:
            out.write("CONVERGENCE / SOLVER NOTES\n--------------------------\n")
            for note in convergence_notes:
                out.write(f"- {note}\n")
            out.write("\n")


def extract_cross_section_map(
    fro_file: str | Path,
    output_file: str | Path = "output_map.txt",
) -> int:
    """Create a compact diagnostic summary from a FRESCO .fro/.out file.

    Despite the historical function name, this no longer attempts to build the
    detailed state-by-state cross-section map.  That job belongs to
    ``xsec_map.py`` using fort.3, fort.13, and fort.16.

    The function name is retained for backward compatibility with ``batch.py``.
    """
    fro_path = Path(fro_file)
    output_path = Path(output_file)

    if not fro_path.is_file():
        raise FileNotFoundError(f"Could not find {fro_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = fro_path.read_text(encoding="utf-8", errors="replace").splitlines()

    info = _parse_calculation_info(lines)
    transfer = _parse_transfer_info(lines)
    totals = _parse_global_cross_sections(lines)
    convergence_notes = _parse_convergence_notes(lines)

    _write_output_summary(
        output_path,
        info,
        transfer,
        totals,
        convergence_notes,
    )

    print(f"[wrote] {output_path}")
    print(
        f"[output-summary] couplings={len(transfer.get('couplings', []))} "
        f"global_xsecs={len(totals)} convergence_notes={len(convergence_notes)}"
    )

    # Retain an integer return value for compatibility with the original API.
    return len(transfer.get("couplings", []))
