#!/usr/bin/python3

import sys
from matplotlib import pyplot as plt

def read_fresco(fileName, scale=1.0):
    # Read the calculated differential cross sections
    th = []
    x  = []

    try:
        file = open(fileName, "r")
    except:
        print( 'Could not open {}'.format(fileName) )
        exit()

    # Skip the header
    for i in range(10):
        line = file.readline()
    
    while True:
        line = file.readline()
        if line == '':
            break
        words = line.split()
        if( words[0] == 'END' ):
            break

        th.append( float( words[0] ) )
        x.append( float( words[1] )*scale )

    file.close()

    return th, x

# Plot a FRESCO angular distribution. (Reads fort.20X files.)
def fresco(fileName, scale=1.0, opts='b-', label=''):

    th, x = read_fresco(fileName, scale)

    if opts == 'o--':
        return plt.plot(th, x, color='gold', linestyle='--',
                        label=r'{}'.format(label))
    elif opts == 'o-':
        return plt.plot(th, x, color='gold', linestyle='-',
                        label=r'{}'.format(label))
    else: 
        return plt.plot(th, x, opts,
                        label=r'{}'.format(label))

def fresco_doublet(fileName1, fileName2, scale1=1.0, scale2=1.0,
                   opts='b-', label=''):
    
    # Read the calculated differential cross sections
    th1, x1 = read_fresco(fileName1, scale1)
    th2, x2 = read_fresco(fileName2, scale2)

    x  = []
    for i in range(len(th1)):
        x.append(x1[i] + x2[i])
    
    if opts == 'o--':
        return plt.plot(th1, x, color='gold', linestyle='--',
                        label=r'{}'.format(label))
    elif opts == 'o-':
        return plt.plot(th1, x, color='gold', linestyle='-',
                        label=r'{}'.format(label))
    else: 
        return plt.plot(th1, x, opts,
                        label=r'{}'.format(label))
    
def main():
    fresco(sys.argv[1], label=sys.argv[2])
    plt.xlabel(r'$\theta_{CM}$ (deg)')
    plt.ylabel(r'$d \sigma/d \Omega$ (mb/sr)')
    plt.legend()
    plt.show()

main()
