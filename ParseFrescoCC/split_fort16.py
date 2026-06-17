from pathlib import Path
from read_fro import extract_cross_section_map


"""

Description : A Python program that reads the Fresco DWBA output file
             "fort.16" and converts it into a text file for use with
              xmgrace, ROOT, or matplotlib. Setup only to read differential cross
             sections and not the analyzing powers.


"""

def split_fort16(
    input_file: str | Path = "fort.16",
    output_dir: str | Path = "fresco_dists",
):
    input_file = Path(input_file)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_file.exists():
        raise FileNotFoundError(f"Could not find {input_file}")

    with input_file.open("r") as f:
        tokens = f.read().split()

    i = 0
    state_counter = 0

    while i < len(tokens):
        # Search for the next section marker
        while i < len(tokens) and tokens[i] != "projectile":
            i += 1

        if i >= len(tokens):
            break

        # Move past "projectile"
        i += 1

        if state_counter == 0:
            outfile = output_dir / "elastic.txt"
        else:
            outfile = output_dir / f"state{state_counter}.txt"

        with outfile.open("w") as out:
            while i < len(tokens):
                theta = tokens[i]
                i += 1

                if theta == "END":
                    break

                if i >= len(tokens):
                    break

                sigma = tokens[i]
                i += 1

                out.write(f"{theta} {sigma}\n")

        print(f"Wrote {outfile}")
        state_counter += 1




if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Split FRESCO fort.16 into state files.")
    parser.add_argument("fort16", help="Path to fort.16 file")
    parser.add_argument(
        "-o", "--output-dir",
        default="fresco_dists",
        help="Directory where split files will be written"
    )
    parser.add_argument(
        "--fro",
        default=None,
        help="Optional .fro file to create 'cross_section_map.txt'"
    )

    args = parser.parse_args()

    split_fort16(args.fort16, args.output_dir)

    if args.fro is not None:
        extract_cross_section_map(
            args.fro,
            Path(args.output_dir) / "cross_section_map.txt"
        )
