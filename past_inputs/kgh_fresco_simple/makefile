CC = g++

%: inputFiles/%.fri conv_fort.cpp
	@rm -f fort.* plotFiles/*.txt plotFiles/*.jpg
	@./fresco < inputFiles/$@.fri > outputFiles/$@.fro
	@./convFort
	@./quickplot.sh

convFort: conv_fort.cpp
	@$(CC) -o $@ $<

.PRECIOUS: outputFiles/%.out

cleanfort:
	rm -f fort.*

clean:
	rm -f *~
