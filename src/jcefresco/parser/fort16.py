from __future__ import annotations

from pathlib import Path


SECTION_END = {"END", "&"}


def split_fort16(
    input_file: str | Path = "fort.16",
    output_dir: str | Path = "fresco_dists",
) -> list[Path]:
    """Split differential cross sections in ``fort.16`` into text files."""
    input_path = Path(input_file)
    output_path = Path(output_dir)

    if not input_path.is_file():
        raise FileNotFoundError(f"Could not find {input_path}")

    output_path.mkdir(parents=True, exist_ok=True)
    tokens = input_path.read_text(encoding="utf-8", errors="replace").split()

    index = 0
    state_counter = 0
    written: list[Path] = []

    while index < len(tokens):
        while index < len(tokens) and tokens[index] != "projectile":
            index += 1

        if index >= len(tokens):
            break

        index += 1
        filename = "elastic.txt" if state_counter == 0 else f"state{state_counter}.txt"
        destination = output_path / filename

        with destination.open("w", encoding="utf-8") as output:
            while index < len(tokens):
                theta = tokens[index]
                index += 1

                if theta.upper() in SECTION_END:
                    break
                if index >= len(tokens):
                    raise ValueError(
                        f"Malformed {input_path}: missing cross section after angle {theta!r}"
                    )

                sigma = tokens[index]
                index += 1
                output.write(f"{theta} {sigma}\n")

        written.append(destination)
        print(f"[wrote] {destination}")
        state_counter += 1

    if not written:
        raise ValueError(f"No 'projectile' cross-section sections found in {input_path}")

    return written
