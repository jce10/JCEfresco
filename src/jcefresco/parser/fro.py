from __future__ import annotations

from pathlib import Path


def extract_cross_section_map(
    fro_file: str | Path,
    output_file: str | Path = "cross_section_map.txt",
) -> int:
    """Map parsed state numbers to CROSS SECTIONS sections in a .fro file."""
    fro_path = Path(fro_file)
    output_path = Path(output_file)

    if not fro_path.is_file():
        raise FileNotFoundError(f"Could not find {fro_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    key = "CROSS SECTIONS FOR OUTGOING"
    state_counter = 0

    with fro_path.open("r", encoding="utf-8", errors="replace") as source, output_path.open(
        "w", encoding="utf-8"
    ) as output:
        for line_number, line in enumerate(source, start=1):
            if key not in line:
                continue

            info = line.split(key, maxsplit=1)[1].strip()
            output.write(f"state{state_counter} | line#: {line_number}\n")
            output.write(f"{info}\n\n")
            state_counter += 1

    print(f"[wrote] {output_path}")
    print(f"[map] found {state_counter} cross-section sections")
    return state_counter
