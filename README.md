# JCEfresco

Reusable Python infrastructure for parsing and plotting FRESCO calculations.

## Layout

```text
JCEfresco/
├── pyproject.toml
├── config/config.yaml
├── scripts/
│   ├── split.py
│   └── plot.py
├── src/jcefresco/
│   ├── config.py
│   ├── reactions.py
│   ├── parser/
│   └── plotting/
├── workdir/
├── data/
└── figures/
```

## Install for development

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

The editable installation makes the package importable while you continue editing `src/`.

## Parse calculations

Preview one reaction:

```bash
split-fresco --reaction 6Lid --dry-run
```

Parse all configured models:

```bash
split-fresco --reaction 6Lid
```

Parse selected models and states:

```bash
split-fresco \
    --reaction 6Lid \
    --models dwba cdcc \
    --states 6860 8220 10753
```

Rebuild existing `fresco_dists/` directories:

```bash
split-fresco --reaction 6Lid --overwrite
```

The development wrapper also works after installation:

```bash
python scripts/split.py --reaction 6Lid --dry-run
```

## Plot calculations

```bash
plot-fresco \
    --reaction 6Lid \
    --state 10753 \
    --models dwba cdcc \
    --scales cdcc=0.5 \
    --theta-max 60
```

Save a publication figure and set explicit bounds:

```bash
plot-fresco \
    --reaction 6Lid \
    --state 10753 \
    --models dwba cdcc \
    --x-min 0 --x-max 60 \
    --y-min 1e-5 --y-max 1e2 \
    --out figures/9Be6Lid_10753keV.png
```

## Add another reaction

Add a reaction and its models under `reactions:` in `config/config.yaml`.
Neither parser nor plotting code needs to be edited when the new calculations
follow the configured directory pattern.

## Plotting multiple channels from one coupled-channels calculation

Use a repeated `--curve` option when several parsed `state*.txt` files from the
same model directory belong on one figure. Its format is:

```text
MODEL:STATE_FILE[:SCALE[:LABEL]]
```

For example:

```bash
plot-fresco \
    --reaction dp \
    --state 6864 \
    --curve 'cc:state1.txt:1.0:0d5/2' \
    --curve 'cc:state2.txt:1.0:2s1/2' \
    --curve 'cc:state3.txt:1.0:2d5/2' \
    --curve 'cc:state4.txt:10.0:2d3/2 (x10)' \
    --theta-max 90
```

The option may also mix calculations from different model directories:

```bash
plot-fresco \
    --reaction dp \
    --state 6864 \
    --curve 'dwba:state1.txt:1.0:DWBA' \
    --curve 'cc:state1.txt:1.0:CC total' \
    --curve 'cc:state2.txt:0.5:CC component x0.5'
```

The original `--models`, `--scales`, `--labels`, and `--state-files` interface
remains available for the simpler one-curve-per-model case.

### Curve-label details

The fourth `--curve` field is used directly as the legend label:

```bash
--curve 'cc:state2.txt:1.0:core 2+ coupled to s1/2'
```

Quote the complete argument when the label contains spaces, parentheses, or
shell-sensitive characters. A non-unit scale is also shown automatically in the
legend, so a label of `2d3/2` with scale `10` is displayed as `2d3/2 × 10`.

## Configuration file
If using namelist version of Fresco (for example if one is using Frescox) the output files are named ".out". In the configuration file, add `output_glob: "*.out"` to the reaction model specification. Example: 
```bash
    models:
      dwba:
        directory: 12Cdp_dwba
        default_state_file: state1.txt
      cc:
        directory: 12Cdp_cc
        default_state_file: state1.txt
        output_glob: "*.out"
```

## Cool Fresco Things (in my opinion)
Fresco old-school input file to namelist converter:
```bash
frnl.f
```
To see the output live while saving:
```bash
~/fresco < input.in | tee output.out
```
For debugging:
```bash
fresco < input.in > output.out 2>&1
```
