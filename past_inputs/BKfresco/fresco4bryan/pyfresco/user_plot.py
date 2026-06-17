
import matplotlib.pyplot as plt
import sys

n=len(sys.argv)
if n == 2:
    file=str(sys.argv[1])
else:
    file=input('Input File Name to Plot: ')

X, Y = [], []
for line in open(file, 'r'):
  values = [float(s) for s in line.split()]
  X.append(values[0])
  Y.append(values[1])

plt.plot(X, Y)
# plt.yscale("log")
# plt.xlim([0,50])

# file='data/state3_tunl.txt'
# X, Y = [], []
# for line in open(file, 'r'):
#   values = [float(s) for s in line.split()]
#   X.append(values[0])
#   Y.append(values[1])

# plt.plot(X, Y)
# plt.yscale("log")
# plt.xlim([0,50])


plt.show()