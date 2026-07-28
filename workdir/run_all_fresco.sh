#!/bin/bash
set -e

# Usage:
#   ./run_all_fresco.sh /path/to/full_fresco_dir
#
# Assumes each state directory looks like:
#   6860keV/
#       some_input.fri

FULL_FRESCO_DIR="${1:-.}"
FRESCO_EXE="${FRESCO_EXE:-fresco}"

for state_dir in "$FULL_FRESCO_DIR"/*keV/; do
    [[ -d "$state_dir" ]] || continue

    state_name=$(basename "$state_dir")
    echo "========================================"
    echo "Running FRESCO for $state_name"
    echo "Directory: $state_dir"
    echo "========================================"

    cd "$state_dir"

    input_file=$(find . -maxdepth 1 -name "*.fri" | head -n 1)

    if [[ -z "$input_file" ]]; then
        echo "Skipping $state_name: no .fri input file found"
        cd - > /dev/null
        continue
    fi

    base_name="${input_file%.fri}"
    base_name="${base_name#./}"

    echo "Input file: $input_file"

    "$FRESCO_EXE" < "$input_file" > "${base_name}.fro"

    echo "Finished $state_name"
    echo "Output: ${base_name}.fro"

    cd - > /dev/null
done

echo "All FRESCO runs complete."