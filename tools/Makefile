# ============================================================================
#  JCEfresco - fr2nl Makefile
#
#  Standalone build for Ian J. Thompson's old-format -> namelist converter.
#  No FRESCOX libraries or object files are required.
#
#  Usage:
#      make          Build fr2nl
#      make debug    Build fr2nl_debug with runtime checks
#      make clean    Remove generated executables/object/module files
#
#  The compiler can still be overridden from the command line, e.g.
#      make FC=ifort
# ============================================================================

FC = gfortran

# Ian Thompson's FRESCOX makefile builds fr2nl with -O1.
# fr2nl.f is legacy fixed-form Fortran; the unlimited fixed-line length is
# especially useful for the human-readable section headers in this version.
FFLAGS = -O1 -std=legacy -ffixed-line-length-none

TARGET = fr2nl
DEBUG_TARGET = fr2nl_debug
SRC = fr2nl.f

.PHONY: all debug clean

all: $(TARGET)

$(TARGET): $(SRC)
	$(FC) $(FFLAGS) -o $@ $<

debug: $(DEBUG_TARGET)

$(DEBUG_TARGET): $(SRC)
	$(FC) -O0 -g -std=legacy -ffixed-line-length-none \
		-fcheck=all -fbacktrace -o $@ $<

clean:
	rm -f $(TARGET) $(DEBUG_TARGET) *.o *.mod
