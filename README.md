## Workflow For Fresco Calculations
1. Create Fresco directory in JCEfresco
2. Run Fresco calculations using `run_all_fresco.sh`
3. Parse the cross section output file (`fort.16`) and general output files (`*fro`) using `splitter.sh`
    This will create a new sub directory `fresco_dists`
4. Set paths in `plot_fresco_xsecs.py` to view plots