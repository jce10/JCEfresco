all: $(patsubst %.fri,%.out,$(wildcard *.fri))
	echo "FRESCO calculations done."

%.out: %.fri
	fresco < $*.fri | tee $*.out
	cp fort.202 $*.txt

clean:
	rm *.fri *.out *.txt fort*


