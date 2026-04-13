"""
FrescoExercises.py

My script for the FRESCO exercises provided by Nick Keeley (I think).

Imports the functions from ScrapeNPlot.py to read in the fort.201 files and plot the distributions.

J. C. Esparza 2026

"""

from pathlib import Path
from ScrapeNPlot import scrape_fort16_sections, plot_distribution, plot_distribution_16, plot_sections_individually
import matplotlib.pyplot as plt


# # ========== RXN 1: 12C(p,p) ========== #
# df_12Cpp = scrape_fort201(
#     "/home/jce18b/Programs/fresco/Exercises_materials/12Cpp/fort.201"
# )

# plot_distribution(
#     df_12Cpp,
#     skip=6,
#     label="ES",
#     title=r"$^{12}C(p,p)$"
# )
# # ==================================== #


# # ========== RXN 2: 12C(p,p) Koning and Delaroche ========== #
# df_12CppKD = scrape_fort201(
#     "/home/jce18b/Programs/fresco/Exercises_materials/12CppKD/fort.201"
# )

# plot_distribution(
#     df_12CppKD,
#     skip=6,
#     label="ES",
#     title=r"$^{12}C(p,p)$"
# )
# # ========================================================== #

# # ========== RXN 3: 12C(p,p) K+D 200 MeV protons ========== #
# df_12CppKD_2 = scrape_fort201(
#     "/home/jce18b/Programs/fresco/Exercises_materials/12CppKD200/fort.201"
# )

# plot_distribution(
#     df_12CppKD_2,
#     skip=6,
#     label="ES",
#     title=r"$^{12}C(p,p)$"
# )
# # ========================================================== #

# # ========== RXN 4: 208Pb(p,p) K+D 16 MeV protons ========== #
# df_208PbppKD = scrape_fort201(
#     "/home/jce18b/Programs/fresco/Exercises_materials/208Pbpp/fort.201"
# )

# plot_distribution(
#     df_208PbppKD,
#     skip=6,
#     label="ES",
#     title=r"$^{208}Pb(p,p)$"
# )
# # ========================================================== #

# # ========== RXN 5: 208Pb(p,p) K+D 200 MeV protons ========== #
# df_208PbppKD_2 = scrape_fort201(
#     "/home/jce18b/Programs/fresco/Exercises_materials/208Pbpp200/fort.201"
# )

# plot_distribution(
#     df_208PbppKD_2,
#     skip=6,
#     label="ES",
#     title=r"$^{208}Pb(p,p)$"
# )
# # ========================================================== #

# # ========== RXN 6: 58Ni(d,d) Daehnick OMPs 52 MeV deuts ========== #
# df_58Nidd = scrape_fort201(
#     "/home/jce18b/Programs/fresco/Exercises/58Nidd/fort.201"
# )

# plot_distribution(
#     df_58Nidd,
#     skip=6,
#     label="ES",
#     title=r"$^{58}Ni(d,d)^{58}Ni$"
# )
# # ========================================================== #

# # ========== RXN 7: 208Pb(7Li,7Li) KD OMPs ========== #
# df_208Pb7Li = scrape_fort201(
#     "/home/jce18b/Programs/fresco/Exercises/208Pb7Li/fort.201"
# )

# plot_distribution(
#     df_208Pb7Li,
#     skip=6,
#     label="ES",
#     title=r"$^{208}Pb(^{7}Li,^{7}Li)^{208}Pb$"
# )
# # ========================================================== #

# # ========== RXN 8: 12C(7Li,7Li) KD OMPs ========== #
# sections = scrape_fort16_sections("/home/jce18b/Programs/fresco/Exercises/12C7Li/fort.16")
# plot_sections_individually(sections)
# # ========================================================== #


# # ========== RXN 3: 12C(d,p)13C ========== #
# sections = scrape_fort16_sections("/home/jce18b/Programs/fresco/Exercises/12Cdp/fort.16")
# plot_sections_individually(sections)
# ========================================================== #


# ========== Coupled Channel gracias de Ken ========== #
sections = scrape_fort16_sections("/home/jce18b/Programs/fresco/Exercises/12Cdp_CC/fort.16")
plot_sections_individually(sections)
# ========================================================== #




plt.show()
