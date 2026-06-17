"""
JCEViewFresco.py

My script for scraping, writing csvs, and plotting Fresco output files.

Current capabilities:
- Scrape sections from fort.16 files and write them to csvs.
- Plot sections from fort.16 files individually.
- Plot sections from csv files.

J. C. Esparza 2026

"""

from pathlib import Path
from ScrapeNPlot import scrape_fort16_sections, plot_sections_individually, plot_section_from_csv_dir
from CombineCSV import combine_xsec_csvs
import matplotlib.pyplot as plt
import polars as pl


# # ========== RXN 3: 12C(d,p)13C ========== #
# sections = scrape_fort16_sections("/home/jce18b/Programs/JCEfresco/jce/12Cdp/fort.16")
# plot_sections_individually(sections)
# ========================================================== #



# # ========== 12C(d,p)13C Coupled Channel gracias de Ken ========== #
# sections = scrape_fort16_sections("/home/jce18b/Programs/JCEfresco/jce/12Cdp_CC/fort.16")
# plot_sections_individually(sections)
# # ========================================================== #



# ========== 12C(d,p)13C Coupled Reaction Channel gracias de Ken ========== #

sections = scrape_fort16_sections("/home/jce18b/Programs/JCEfresco/jce/12Cdp_CRC/fort.16")
plot_sections_individually(sections)

root_dir = Path("/home/jce18b/Programs/JCEfresco/Exercises/fresconamelist/28Sidp")
indiv_dir = root_dir / "scraped_csvs"

# namelist
# name_file = root_dir / "namelist" / "fort.16"
# Fedp_namelist = scrape_fort16_sections(
#     name_file,
#     output_file=indiv_dir / f"Fedp_{name_file.parent.name}.csv"
# )
# # adwa old card
# adwa_file = root_dir / "adwa" / "fort.16"
# Fedp_ADWA = scrape_fort16_sections(
#     adwa_file,
#     output_file=indiv_dir / f"Fedp_{adwa_file.parent.name}.csv"
# )
# dwba old card
# dwba_file = root_dir / "dwba" / "fort.16"
# Fedp_DWBA = scrape_fort16_sections(
#     dwba_file,
#     output_file=indiv_dir / f"Fedp_{dwba_file.parent.name}.csv"
# )

# comparison plot 
plot_section_from_csv_dir(indiv_dir, section_tag="@s1")

# ================================================================================ #





plt.show()
