"""
FrescoExercises.py

My script for the FRESCO exercises provided by Nick Keeley (I think).

Imports the functions from ScrapeNPlot.py to read in the fort.201 files and plot the distributions.

J. C. Esparza 2026

"""

from pathlib import Path
from ScrapeNPlot import scrape_fort16_sections, plot_sections_individually, plot_section_from_csv_dir
from CombineCSV import combine_xsec_csvs
import matplotlib.pyplot as plt
import polars as pl



# =============== 56Fe(d,p)57Fe =============== #

root_dir = Path("/home/jce18b/Programs/JCEfresco/jce/fresconamelist/28Sidp")
indiv_dir = root_dir / "scraped_csvs"

# namelist
name_file = root_dir / "namelist" / "fort.16"
Fedp_namelist = scrape_fort16_sections(
    name_file,
    output_file=indiv_dir / f"Sidp_{name_file.parent.name}.csv"
)

# adwa old card
adwa_file = root_dir / "adwa" / "fort.16"
Fedp_ADWA = scrape_fort16_sections(
    adwa_file,
    output_file=indiv_dir / f"Sidp_{adwa_file.parent.name}.csv"
)

# dwba old card
dwba_file = root_dir / "dwba" / "fort.16"
Fedp_DWBA = scrape_fort16_sections(
    dwba_file,
    output_file=indiv_dir / f"Sidp_{dwba_file.parent.name}.csv"
)

# comparison plot
plot_section_from_csv_dir(indiv_dir, section_tag="@s1")


# ============================================= #



# =============== 56Fe(d,p)57Fe =============== #

# root_dir = Path("/home/jce18b/Programs/JCEfresco/Exercises/fresconamelist/56Fedp")
# indiv_dir = root_dir / "scraped_csvs"

# # namelist
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
# # dwba old card
# dwba_file = root_dir / "dwba" / "fort.16"
# Fedp_DWBA = scrape_fort16_sections(
#     dwba_file,
#     output_file=indiv_dir / f"Fedp_{dwba_file.parent.name}.csv"
# )

# # # plot individually
# # # plot_sections_individually(Fedp_namelist)
# # # plot_sections_individually(Fedp_DWBA)
# # # plot_sections_individually(Fedp_ADWA)


# plot_section_from_csv_dir(indiv_dir, section_tag="@s1")


# ============================================= #


# =============== 135Xe(t,a)134I =============== #

# root_dir = Path("/home/jce18b/Programs/JCEfresco/Exercises/fresconamelist/136Xeta")
# indiv_dir = root_dir / "scraped_csvs"

# # namelist
# name_file = root_dir / "fort.16"
# Fedp_namelist = scrape_fort16_sections(
#     name_file,
#     output_file=indiv_dir / f"Fedp_{name_file.parent.name}.csv"
# )


# plot_section_from_csv_dir(indiv_dir, section_tag="@s1")

# ============================================ #



# ========================================================== #




plt.show()
