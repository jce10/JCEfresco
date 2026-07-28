import os
import subprocess

base_title = '49Ti(d,p)50Ti 16 MeV (ADWA)'
binding    = 10.93919 # neutron separation energy of final nucleus
Qvalue     = 8.7146
Z          = 22
label_in   = '49Ti' # 4 characters
m_in    = 48.9478
label_out  = '50Ti' # 4 characters
m_out   = 49.9447

inputFileName = 'input_generator.inp'
inputFile = open(inputFileName, 'r')
energies = []
ns       = []
ls       = []
js_transfer = []
js_finalstate = []
while True:
    line = inputFile.readline()
    if line.startswith('#'):
        continue
    if line == '':
        break
    words = line.split()
    energies.append(float(words[0]))
    js_finalstate.append(float(words[1]))
    ns.append(words[2])
    ls.append(words[3])
    js_transfer.append(words[4])

l_dict = {'s': 0, 'p': 1, 'd': 2, 'f': 3, 'g': 4}
frac_dict = {'0.5': 12, '1.5': 32, '2.5': 52, '3.5': 72, '4.5': 92} 

fri='''{bt}, {j_pi}{parity[0]} {e} MeV {n}{ll}{jt}
0.10    55.0    0.20    0.20    30.0    -6.0
 00. 20.  +.00   F F
0  15.0     65.   0.1  1
0.0    0 1   1 1  48          .000    0.   0.001
 1 1 0 0 2 3 0 0-3 1 0 0 1
2H      2.0141  1.0        1  {label_in}    {mass_in} {Z}    0.0000
1.0   +1 0.0               1  3.5   -1 0.000
1H      1.0078  1.0        1  {label_out}    {mass_out} {Z}    {q}
0.5   +1 0.0               2  {j_pi}   {parity} {e}

  1 0  0    49.0     0.0   1.300
  1 1  0   98.68   1.193   0.703   1.146   1.193   0.703
  1 2  0                           14.92   1.284   0.570
  1 3  0   10.32   1.009   0.627   -0.23   1.009   0.627
  2 0  0    50.0     0.0   1.270
  2 1  0   53.64   1.201   0.671   1.300   1.201   0.671
  2 2  0                            8.51   1.284   0.554
  2 3  0    5.52   1.009   0.590   -0.06   1.009   0.590
  3 0  0    1.00            1.25
  3 1  5    1.00            1.00
  3 3  5    1.00            1.00
  3 4  5    1.00            1.00
  3 7  5    1.00            1.00
  4 0  0    50.0     0.0    1.25
  4 1  0    50.0    1.25    0.65
  4 3  0     6.0    1.25    0.65
0
  1  2 1 2-1 3   1 0 2 0.5 1 1.5 1  3  0  2.2260  0  3  0
  3    1 2-2 0   {n} {l}   0.5   {jt}    4  0  {be}  1  0  0

  -2   1   7 0-1 0
       1   1   1   1  1.0000
       2   1   1   3  1.0000
0
   0   1   1
16.0
EOF
'''
    
dir = os.getcwd()
for i in range(len(energies)):
    q = f'{Qvalue:6.4f}'
    e = f'{energies[i]:5.3f}'
    be = float(binding) - float(e)
    be = f'{be:6.4f}'
    Z = f'{float(Z):4.1f}'
    mass_in = f'{m_in:7.4f}'
    mass_out = f'{m_out:7.4f}'
    energy = float(e)*1000
    l = l_dict[ls[i]]
    parity = '+1'
    if ls[i]=='s' or ls[i]=='d' or ls[i]=='g':
        parity = '-1'
    print(e, be, l, js_transfer[i])
    fileName = f'ti50dp_adwa_{int(energy)}_{ns[i]}{ls[i]}{frac_dict[js_transfer[i]]}_{int(js_finalstate[i])}{parity[0]}.fri'
    if not os.path.exists(fileName):
        file = open(fileName, 'w')
        file.write(fri.format(bt=base_title, Z=Z,
                              label_in=label_in, label_out=label_out,
                              mass_in=mass_in, mass_out=mass_out, q=q,
                              e=e, ll=ls[i], j_pi=js_finalstate[i], 
                              jt=js_transfer[i], parity=parity,
                              n=ns[i], l=l, be=be))
        file.close()
    
    inFile = fileName
    outfile = f'ti50dp_adwa_{int(energy)}_{ns[i]}{ls[i]}{frac_dict[js_transfer[i]]}_{int(js_finalstate[i])}{parity[0]}.fro'
    executable_path = './bin/fresco'
    command_string = f'{executable_path} < {inFile} > {outfile}'
    command = [command_string]
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as error:
        print(f'Error running the command {error}')
    
    # take the cross-section output file & rename it so it does not get overwritten in the next iteration
    x_sec_outfile = f'{dir}/fort.16'
    renamed_outfile = f'{dir}/50Ti_{int(energy)}_{ns[i]}{ls[i]}{frac_dict[js_transfer[i]]}_{int(js_finalstate[i])}{parity[0]}.txt'

    try:
        os.rename(x_sec_outfile, renamed_outfile)
        print(f"File '{x_sec_outfile}' has been renamed to '{renamed_outfile}'.")
    except FileNotFoundError:
        print(f"Error: File '{x_sec_outfile}' not found.")
    except FileExistsError:
        print(f"Error: File '{renamed_outfile}' already exists.")
    except Exception as error:
        print(f"An error occurred: {error}")
    print(f'Calculated the transfer to the Jpi={int(js_finalstate[i])}{parity[0]}, {ns[i]}{ls[i]}{frac_dict[js_transfer[i]]} configuration')
    print(f"Successfully ran fresco & created cross-section file {renamed_outfile}")
    
    

    

    


