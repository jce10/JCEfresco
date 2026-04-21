from pathlib import Path
import polars as pl


def combine_xsec_csvs(csv_files, output_file):
    """
    Combine multiple section CSV files into one CSV.
    """

    frames = []

    for file in csv_files:
        file = Path(file)

        try:
            df = pl.read_csv(file)
        except Exception as e:
            print(f"Skipping {file.name}: {e}")
            continue

        # Ensure source_file column exists
        if "source_file" not in df.columns:
            df = df.with_columns(pl.lit(file.name).alias("source_file"))

        frames.append(df)

    if not frames:
        raise ValueError("No valid CSV files found to combine.")

    combined = pl.concat(frames, how="vertical")
    combined.write_csv(output_file)

    print(f"\n✅ Combined CSV saved to: {output_file}")
    print(f"Rows: {combined.height}, Columns: {combined.width}")


# ==========================================================
# 🚀 RUN SECTION (just run the script from the directory)
# ==========================================================
if __name__ == "__main__":

    csv_dir = Path("/home/jce18b/Programs/JCEfresco/Exercises/fresconamelist/56Fedp/scraped_csvs")
    output_file = csv_dir / "xsec_combined.csv"

    # find all CSVs in this directory
    csv_files = [
        f for f in csv_dir.glob("*.csv")
        if f.name != output_file.name
    ]

    print(f"Found {len(csv_files)} CSV file(s):")
    for f in csv_files:
        print(f"  - {f.name}")

    if not csv_files:
        raise ValueError("No CSV files found in this directory.")

    combine_xsec_csvs(csv_files, output_file)