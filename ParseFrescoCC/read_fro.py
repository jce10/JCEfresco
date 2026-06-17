from pathlib import Path

"""

Read thru FRESCO (.fro) output file to log which state corresponds to which cross-section section. 

"""


def extract_cross_section_map(
    fro_file: str | Path,
    output_file: str | Path = "cross_section_map.txt",
):
    fro_file = Path(fro_file)
    output_file = Path(output_file)

    key = "CROSS SECTIONS FOR OUTGOING"

    with fro_file.open("r", errors="replace") as f:
        lines = f.readlines()

    state_counter = 0

    with output_file.open("w") as out:
        for line_number, line in enumerate(lines, start=1):
            if key in line:
                info = line.split(key, 1)[1].strip()

                out.write(f"state{state_counter} | line#: {line_number}\n")
                out.write(f"{info}\n\n")

                state_counter += 1

    print(f"Wrote {output_file}")
    print(f"Found {state_counter} cross-section sections.")


if __name__ == "__main__":

    root_dir = Path("/home/jce18b/Programs/JCEfresco/jce")

    # 9Be(6Li,d) first try
    # fro = "/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc/10750keV_short/10750keV_cdcc_short.fro"

    # 25Al(d,n)
    # fro = "/home/jce18b/Programs/JCEfresco/exercises/25Aldn_CDCC/25Aldn_fromken.fro"

    # 12C(d,p) 9.9 MeV CRC
    fro = root_dir / "12Cdp_CRC" / "12Cdp_CRC_9500keV.fro"
    output_file = root_dir / "12Cdp_CRC" / "fresco_dists" / "cross_section_map.txt"

    extract_cross_section_map(fro, output_file)