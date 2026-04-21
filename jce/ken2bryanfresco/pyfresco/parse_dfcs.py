
def Filter(stateNum):
	dataFlag=False
	#lines is a list with each item representing a line of the file
	for l in lines: 
		if l[0:8]=='#  Theta' in l:
			dataFlag=True
			outfile = open('state'+str(stateNum)+'.txt', 'w') 
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
		infile = open('fort.202', 'r') 
		lines = infile.readlines() 
		Filter(1)

		infile = open('fort.203', 'r') 
		lines = infile.readlines() 
		Filter(2)

		infile = open('fort.204', 'r') 
		lines = infile.readlines() 
		Filter(3)

		infile = open('fort.205', 'r') 
		lines = infile.readlines() 
		Filter(4)

		infile = open('fort.206', 'r') 
		lines = infile.readlines() 
		Filter(5)
