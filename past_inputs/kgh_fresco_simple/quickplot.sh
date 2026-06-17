#!/bin/sh

for file in plotFiles/*.txt
do
    cp $file temp.txt
    gnuplot -persist <<EOF
set terminal postscript color enhanced
set output "plotFiles/temp.ps"
set xlabel "{/Symbol q}_{cm} (deg.)"
set ylabel "d{/Symbol s}/d{/Symbol W} (mb/sr)"
set logscale y
plot "temp.txt" with lines lt 1 lc 1
EOF
    rm temp.txt
    mv plotFiles/temp.ps ${file%.*}.ps
done
