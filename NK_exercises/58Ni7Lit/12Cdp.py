# Plotting the Exercise 12C(d,p)13C data from exercies.  

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
import os

# fort.201 file path
file_path = '/home/jce18b/Programs/fresco/12Cdp/fort.16'

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

# Convert the collected data into a pandas DataFrame
df = pd.DataFrame(data)

# Show the scraped data
#print(df)


# # Plot the first two columns and ignore the third column
# # plt.plot(df[0], df[1], 'o-', label='DWBA')

# # Plot the first two columns but skip indecies 0-5
# plt.plot(df[0][0:361], df[1][0:361], 'o-', label='E.S.')
# plt.plot(df[0][362:722], df[1][362:722], 'o-', label='transfer')
# plt.yscale('log')

# # Customize the plot
# plt.xlabel('$\Theta_{\mathrm{C.M.}}$ (degrees)')
# plt.ylabel('$d\sigma/d\Omega$ (mb/sr)')
# plt.title('$^{12}C(d,p)^{13}C$')
# plt.grid(True)
# plt.legend()

# # Show the plot
# plt.show()

# Create a 2x1 grid of subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 10))

# First subplot: Plot first column vs. second column
ax1.plot(df[0][0:361], df[1][0:361], 'o-', label='First vs Second Column')
ax1.set_xlabel('$\Theta_{\mathrm{C.M.}}$ (degrees)')
ax1.set_ylabel('$d\sigma/d\Omega$ (mb/sr)')
ax1.set_title('$^{12}C(d,p)^{13}C$ G.S. E.S.')
ax1.grid(True)
ax1.set_yscale('log')
#ax1.legend()

# Second subplot: Plot second column vs. third column
ax2.plot(df[0][362:722], df[1][362:722], 's-', label='Second vs Third Column', color='orange')
ax2.set_xlabel('$\Theta_{\mathrm{C.M.}}$ (degrees)')
ax2.set_ylabel('$d\sigma/d\Omega$ (mb/sr)')
ax2.set_title('$^{12}C(d,p)^{13}C$ G.S. transfer')
ax2.grid(True)
ax2.set_yscale('log')
#ax2.legend()

# Adjust layout and show plot
plt.tight_layout()
plt.show()
