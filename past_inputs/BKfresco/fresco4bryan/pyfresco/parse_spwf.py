
def FilterWF(stateNum):
	dataFlag=False
	#lines is a list with each item representing a line of the file
	for l in lines: 
		if l[0:8]=='#  Theta' in l:
			dataFlag=True
			outfile = open('data/state'+str(stateNum)+'.txt', 'w') 
			continue
		if l[0:4]==' END' in l:
			dataFlag=False
			outfile.close()
			continue
		if dataFlag==True:
			x,y = l.split()
			outfile.write(l)
	infile.close()

if __name__ == "__main__":
		#Open the file
		infile = open('fort.58', 'r') 
		lines = infile.readlines() 
		Filter(1)