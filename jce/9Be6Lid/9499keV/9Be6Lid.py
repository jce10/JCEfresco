# Plotting the FRESCO calculation and data for my 9Be(6Li,d) reaction. 

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os



#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Scrape FRESCO output file for data ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# fort.16 file path
file_path = '/home/jce18b/Esparza_SPS/2023_01_9Be_6Li_d/9Be6Lid_fresco/9500MeV/fort.16'

# Initialize lists to store columns of data
data = []

# Open the file
with open(file_path, 'r') as file:
    for line in file:
        # Try to split the line into float numbers
        try:
            # Convert line into list of floats if possible
            row = [float(i) for i in line.split()]
            data.append(row)
        except ValueError:
            # Skip lines that cannot be converted to floats (non-numeric lines)
            continue


# FRESCO output data
df = pd.DataFrame(data)

#~~~~~~~~~~~~~~~~~ Import the .ods file containing the experimental angular distribution data ~~~~~~~~~~~~~~~~#
pd.set_option('display.max_columns', None)

# Load exp data
ods_file = os.path.expanduser('/home/jce18b/Esparza_SPS/2023_01_9Be_6Li_d/totalangdistdata.ods')
df2 = pd.read_excel(ods_file, engine="odf", sheet_name="angdistdata_short")

# # Export to CSV to find correct cells
# csv_file = os.path.expanduser('/home/jce18b/Esparza_SPS/2023_01_9Be_6Li_d/datacheck.csv')
# df.to_csv(csv_file, index=False)
# print(f"Data exported to {csv_file}")

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Extract Data ! ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

# Esparza data 
# | CMangles | x sec6.86 | x sec7.55 | x sec7.65 | x sec9.5 | xsec 9.9 | xsec 10.75 |
data_esp = np.array([
    df2.iloc[20:25, 1].values,  # Values from the first column
    df2.iloc[20:25, 2].values,  # Values from the second column
    df2.iloc[20:25, 5].values,
    df2.iloc[20:25, 8].values,
    df2.iloc[20:25, 11].values,
    df2.iloc[20:25, 14].values,
    df2.iloc[20:25, 17].values,
])

# Aslanoglou data
# | 6.86ang | xsec6.86 | 7.55ang | xsec7.55 | 9.5ang | xsec9.5 | 9.9ang | xsec9.9 | 10.75ang | xsec10.75 |
data_aslan = np.array([
    df2.iloc[2:18, 1].values,
    df2.iloc[2:18, 2].values,
    df2.iloc[2:18, 4].values,
    df2.iloc[2:18, 5].values,
    df2.iloc[2:18, 10].values,
    df2.iloc[2:18, 11].values,
    df2.iloc[2:18, 13].values,
    df2.iloc[2:18, 14].values,
    df2.iloc[2:18, 16].values,
    df2.iloc[2:18, 17].values,

])

# Kemper ES data
# | ang0.0 | xsec0.0 | ang2.43 | xsec2.43 | 
data_kemp = np.array([
    df2.iloc[31:73, 1].values,
    df2.iloc[31:73, 2].values,
    df2.iloc[31:73, 4].values,
    df2.iloc[31:73, 5].values,
])

# Esparza, Aslanoglou, and Kemper experimental data
df_esp = pd.DataFrame(data_esp)
df_aslan = pd.DataFrame(data_aslan)
df_kemp = pd.DataFrame(data_kemp)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Elastic ! ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Plot the first two columns and ignore the third column
## plt.plot(df[0], df[1], 'o-', label='DWBA')

# print(df)

# # GS ES 
# plt.plot(df[0][0:174], df[1][0:174], 'o-', label='FRESCO DWBA')
# plt.plot(df_kemp.iloc[0, 1:], df_kemp.iloc[1, 1:], 'o-', label='Cook + Kemper')
# plt.yscale('log')
# plt.xlabel('$\Theta_{\mathrm{C.M.}}$ (degrees)')
# plt.ylabel('$d\sigma/d\Omega$ (mb/sr)')
# plt.title('$^{9}Be(^{6}Li,d)^{13}C$ G.S. E.S.')
# plt.grid(True)
# plt.legend()

# Show the plot
# plt.show()

# # ES plots
# fig, axs = plt.subplots(1, 2, figsize=(15, 10))
# axs[0].scatter(df_kemp.iloc[0], df_kemp.iloc[1], color='green', label='Kemper')
# axs[0].set_yscale('log')
# axs[0].set_xlabel('CM Angles (degrees)')
# axs[0].set_ylabel('Cross sections (mb/sr)')
# axs[0].set_title('0 MeV ES (3/2-)')
# axs[0].grid(True)
# axs[0].legend()

# axs[1].scatter(df_kemp.iloc[2], df_kemp.iloc[3], color='green', label='Kemper')
# axs[1].set_yscale('log')
# axs[1].set_xlabel('CM Angles (degrees)')
# axs[1].set_ylabel('Cross sections (mb/sr)')
# axs[1].set_title('2.43 MeV ES (5/2-)')
# axs[1].grid(True)
# axs[1].legend()

# plt.figure
# plt.tight_layout()
# plt.show()
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Ang. Dist. ! ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

# # ES Plots
# # 0.0 MeV ES 
# plt.figure("GS ES", figsize=(10, 6))
# plt.scatter(df_kemp.iloc[0,1:], df_kemp.iloc[1, 1:], color='blue', label='Cook')
# plt.yscale('log')
# plt.xlabel('CM Angles (degrees)')
# plt.ylabel('Cross sections (mb/sr)')
# plt.title('0 MeV ES (3/2-)')
# plt.grid(True)
# plt.legend()

# 9.5 MeV
plt.figure(figsize=(10, 6))
plt.scatter(df_aslan.iloc[4], df_aslan.iloc[5], color='blue', label='Aslanoglou')
plt.scatter(df_esp.iloc[0], df_esp.iloc[4], color='red', label='Esparza')
plt.scatter(df[0][362:542], df[1][362:542], color='green', label='FRESCO DWBA')
plt.yscale('log')
plt.xlabel('CM Angles (degrees)')
plt.ylabel('Cross sections (mb/sr)')
plt.title('9.5 MeV (9/2+)')
plt.grid(True)
plt.legend()

# Adjust layout and show plot
plt.tight_layout()
plt.show()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

# ~~~ JCE ~~~ #

