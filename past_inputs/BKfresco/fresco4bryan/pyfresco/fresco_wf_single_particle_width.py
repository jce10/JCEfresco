# Single particle width calculations using the wave function from FRESCO CRC  
#
# Author: Eli Temanson
# Date: May 26, 2022

import matplotlib.pyplot as plt
import pandas as pd
from scipy import interpolate, integrate
import mpmath as mp
import numpy as np

HBARC=197.3269804  #MeV*fm
mu=901.909/931.494 # amu 
Zp=1
Zt=13

E=0.4154 #0.4138 # MeV
k=0.218735*np.sqrt(mu*E)
print('wave number, k = ',k)
eta=0.1574854*Zp*Zt*np.sqrt(mu/E)
print('sommerfeld parameter, coulomb eta = ', eta)

r0=1.25
ChannelRadius=r0*(1 + 25**(1.0/3.0))
print('channel radius = ', ChannelRadius, ' (fm)')

print('wavelength to sie ratio = ', k*ChannelRadius)

# regular coulomb wave fuction
def regCWF(l,eta,z):
    func = np.frompyfunc(mp.coulombf, 3, 1)
    return func(l,eta,z)
# irregular coulomb wave function
def irregCWF(l,eta,z): 
    func = np.frompyfunc(mp.coulombg, 3, 1)
    return func(l,eta,z)

wave_function = pd.read_csv('fort.58',sep='\s+',header=None,skiprows=1,skipfooter=1,engine='python')

#norm = interpolate.UnivariateSpline(x,y).integral(0,30)
norm = interpolate.UnivariateSpline(wave_function[0],wave_function[1]**2).integral(0,20)
#norm = 1
print('norm = ',norm)

wave_function[1] = wave_function[1]/np.sqrt(norm)
wf = interpolate.CubicSpline(wave_function[0], wave_function[1])

reduced_width_sqr = 0.5*ChannelRadius*wf(ChannelRadius)**2
print('Dimenisonless single-particle reduced width = ', reduced_width_sqr)

penetrability = k*ChannelRadius/(regCWF(0,eta,k*ChannelRadius)**2 + irregCWF(0,eta,k*ChannelRadius)**2)
print('penetrability = ', penetrability)

print('Single-Particle Width = ', reduced_width_sqr *penetrability* 2*HBARC**2/(931.494*mu*ChannelRadius**2), ' (MeV)')


plt.plot(wave_function[0], wf(wave_function[0])**2)
plt.axvline(x=ChannelRadius,color='r',linestyle='--')
plt.axvline(x=4.31,color='k',linestyle='--')
plt.axvline(x=6.37,color='k',linestyle='--')
plt.xlim(0,20)
plt.ylabel('$u(r)^{2}$')
plt.xlabel('Radius (fm)')
plt.show()
