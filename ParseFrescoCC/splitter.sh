#!/bin/bash
set -e

FULL_FRESCO_DIR="/home/jce18b/Programs/JCEfresco/jce/9Be6Lid_cdcc"
SPLITTER="/home/jce18b/Programs/JCEfresco/ParseFrescoCC/split_fort16.py"

for state_dir in "$FULL_FRESCO_DIR"/*keV/; do
    state_name=$(basename "$state_dir")

    echo "Processing $state_name"

    python "$SPLITTER" \
        "$state_dir/fort.16" \
        -o "$state_dir/fresco_dists" \
        --fro "$state_dir"/*.fro \

done