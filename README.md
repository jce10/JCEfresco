# JCEfresco

Reusable Python infrastructure for **parsing, plotting, and fitting FRESCO/FRESCOX calculations**.

JCEfresco is organized around three complementary pieces:

1. **Parser** — split FRESCO/FRESCOX output into reusable angular-distribution files.
2. **Plotting** — compare calculations, coupled-channel components, and experimental data.
3. **SFRESCOX fitting** — fit FRESCOX spectroscopic amplitudes directly to experimental angular distributions, verify the result with standalone FRESCOX, and propagate a one-parameter profile-\(\chi^2\) uncertainty band.

The parser and plotting infrastructure remain usable independently of the fitter.

---

## Repository layout

```text
JCEfresco/
├── pyproject.toml
├── config/
│   └── config.yaml
├── scripts/
│   ├── split.py
│   ├── plot.py
│   └── fit.py
├── src/jcefresco/
│   ├── config.py
│   ├── reactions.py
│   ├── cli_fit.py
│   ├── parser/
│   ├── plotting/
│   └── fitting/
│       ├── __init__.py
│       └── sfresco.py
├── tests/
├── workdir/
├── data/
└── figures/
```

The fitting component is additive: it reuses the existing parser, plotting, reaction configuration, and experimental-data loading machinery rather than replacing them.

---

# Installation

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

The editable installation keeps `src/` importable while the package is being developed.

To run the fitter tests:

```bash
python -m pytest -q tests/test_sfresco_fit.py
```

The v7 patch build contained **33 fitting tests**.

---

# Configuration

Reaction/model directory structure is controlled from:

```text
config/config.yaml
```

Add a reaction and its models under `reactions:`. If the calculation follows the configured directory pattern, the parser and plotting code do not need to be edited.

## FRESCO versus FRESCOX output files

Traditional FRESCO calculations commonly produce `.fro` output files, while namelist FRESCOX calculations commonly produce `.out` files.

For FRESCOX models, specify the output glob explicitly:

```yaml
models:
  dwba:
    directory: 12Cdp_dwba
    default_state_file: state1.txt

  cc:
    directory: 12Cdp_cc
    default_state_file: state1.txt
    output_glob: "*.out"
```

---

# Parsing calculations

## Preview one reaction

```bash
split-fresco --reaction 6Lid --dry-run
```

## Parse all configured models

```bash
split-fresco --reaction 6Lid
```

## Parse selected models and states

```bash
split-fresco \
    --reaction 6Lid \
    --models dwba cdcc \
    --states 6860 8220 10753
```

## Rebuild existing `fresco_dists/` directories

```bash
split-fresco --reaction 6Lid --overwrite
```

The development wrapper also works after installation:

```bash
python scripts/split.py --reaction 6Lid --dry-run
```

## Important parser limitation

`split.py` currently assumes that the relevant FRESCO output contains **cross sections only**. Analyzing powers are not presently supported by this parser path.

In practice, keep:

```text
kqmax=0
```

when generating output intended for this workflow.

---

# Plotting calculations

A standard one-curve-per-model plot can be made with:

```bash
plot-fresco \
    --reaction 6Lid \
    --state 10753 \
    --models dwba cdcc \
    --scales cdcc=0.5 \
    --theta-max 60
```

To save a publication figure with explicit bounds:

```bash
plot-fresco \
    --reaction 6Lid \
    --state 10753 \
    --models dwba cdcc \
    --x-min 0 --x-max 60 \
    --y-min 1e-5 --y-max 1e2 \
    --out figures/9Be6Lid_10753keV.png
```

---

# Plotting multiple curves from one model

Use repeated `--curve` arguments when several parsed `state*.txt` files from the **same model directory** should appear on one figure.

The syntax is:

```text
MODEL:STATE_FILE[:SCALE[:LABEL[:LINESTYLE]]]
```

At minimum:

```text
MODEL:STATE_FILE
```

A scale, custom legend label, and line style may be supplied when needed.

## Example: several coupled-channel components

```bash
python scripts/plot.py \
    --reaction dp \
    --state 6864 \
    --curve 'cc:state1.txt:1.0:0d5/2' \
    --curve 'cc:state2.txt:1.0:2s1/2' \
    --curve 'cc:state3.txt:1.0:2d5/2' \
    --curve 'cc:state4.txt:10.0:2d3/2 component' \
    --theta-max 90
```

The same model may therefore be repeated with different state files, scale factors, labels, and line styles.

## Example: mix model directories

```bash
python scripts/plot.py \
    --reaction dp \
    --state 6864 \
    --curve 'dwba:state1.txt:1.0:DWBA' \
    --curve 'cc:state1.txt:1.0:CC total' \
    --curve 'cc:state2.txt:0.5:CC component'
```

## Example: choose a solid total curve

```bash
python scripts/plot.py \
    --reaction dp \
    --state 3089 \
    --exp-label "This Work" \
    --curve 'cc:state2.txt:1.0:total:solid' \
    --curve 'cc:state3.txt:1.0:0s1/2' \
    --curve 'cc:state4.txt:1.0:2d5/2' \
    --theta-max 60
```

## Curve-label details

The custom label field is used directly in the legend:

```bash
--curve 'cc:state2.txt:1.0:core 2+ coupled to s1/2'
```

Quote the complete argument when the label contains spaces, parentheses, or other shell-sensitive characters.

Non-unit scale factors are appended to the displayed label automatically. For example, a label of `2d3/2` with scale `10` is displayed as approximately:

```text
2d3/2 × 10
```

The original `--models`, `--scales`, `--labels`, and `--state-files` interface remains available for the simpler one-curve-per-model case.

Do not mix repeated `--curve` specifications with the older model-keyed curve options in the same command.

---

# SFRESCOX spectroscopic-amplitude fitting

The fitter is designed to compare a FRESCOX angular distribution with an experimental dataset and minimize the cross-section \(\chi^2\) with respect to a selected FRESCO CFP/spectroscopic amplitude.

It reuses existing JCEfresco infrastructure for:

- reaction/model/work-directory configuration;
- loading experimental CSV files with the contract

  ```text
  angle,xsec,xsec_err
  ```

- CFP bookkeeping from `fort.3`;
- mapping parsed `stateN.txt` files to FRESCO partition/state information from `fort.16`;
- splitting the exact final best-fit `fort.16` output;
- generating a best-fit `xsec_map.txt` when possible.

The standard executables are expected to be available on `PATH` as:

```text
sfrescox
frescox
```

They may be overridden with:

```text
--sfresco-exe
--fresco-exe
```

---

# Recommended fitting workflow

A typical fit command is:

```bash
python scripts/fit.py \
    --reaction 6lid \
    --state 10753 \
    --model dwba \
    --cfp 2 \
    --scan-min 3.0 \
    --scan-max 5.0 \
    --scan-step 0.25 \
    --theta-max 50
```

For a new calculation, it is useful to begin with a preparation pass:

```bash
python scripts/fit.py \
    --reaction 6lid \
    --state 10753 \
    --model dwba \
    --theta-max 40 \
    --prepare-only
```

This allows the bookkeeping to be inspected before the expensive fitting stage begins.

---

# Conditions that must be satisfied before fitting

The fitting routine depends on several pieces of FRESCOX and JCEfresco bookkeeping agreeing with one another.

## 1. Experimental data must be available

The experimental dataset must be readable using the existing JCEfresco CSV format:

```text
angle,xsec,xsec_err
```

The requested angular range must contain usable experimental points.

## 2. The requested parsed curve must map to a FRESCO outgoing channel

JCEfresco uses `fort.16` information to associate a requested `stateN.txt` file with the corresponding FRESCO partition/state.

## 3. A matching CFP must exist

CFPs are read from `fort.3`.

FRESCOX uses the convention that a negative `IN` marks the last CFP while `abs(IN)` retains the projectile/target bookkeeping meaning. Therefore, for example,

```text
IN=-2
```

is still matched to outgoing partition 2.

## 4. Ambiguous multiple-CFP cases require explicit user selection

If several CFPs feed the requested outgoing state, the fitter refuses to guess which one should be varied because coherent amplitudes may interfere.

Select the desired CFP explicitly:

```bash
--cfp N
```

This keeps the fitting inside the full FRESCOX calculation rather than treating a multi-component distribution as a simple post-hoc normalization.

## 5. SFRESCOX must return a valid \(\chi^2\)

The experimental data block passed to SFRESCOX includes the real incident laboratory energy so that `SHOW` and `CHI` associate the data with the correct calculated energy.

The final \(\chi^2\) is taken from SFRESCOX `CHI` output rather than relying on a potentially misleading `SHOW` value.

## 6. The selected best-fit amplitude must be explicitly evaluated

The final published amplitude is not accepted merely because a polynomial interpolation predicts a minimum there. It must correspond to an amplitude actually evaluated by SFRESCOX.

## 7. The amplitude handed from JCEfresco to SFRESCOX must agree with what SFRESCOX reports

Before publication, JCEfresco checks that the final SFRESCOX amplitude matches the amplitude that JCEfresco requested.

## 8. The standalone FRESCOX result must agree with the fitting result

The exact final best-fit card is run with ordinary FRESCOX. JCEfresco then independently evaluates the resulting calculated distribution against the experimental data.

Small differences between the SFRESCOX and independently calculated \(\chi^2\) values are treated diagnostically:

- difference above roughly **2%**: warning;
- difference above roughly **10%**: abort publication.

The standalone FRESCOX curve is the actual artifact that is ultimately plotted.

---

# Current default minimization method

The current default is a **derivative-free native SFRESCOX scan/refinement workflow**.

This replaced MIGRAD as the default because small point-to-point numerical jitter in repeated FRESCOX evaluations can make finite-difference derivatives unreliable at the tiny parameter displacements used by MIGRAD.

MINUIT/MIGRAD has **not** been removed. It remains available as an optional legacy path:

```bash
python scripts/fit.py ... --fit-method migrad
```

---

# Scan/refinement algorithm

For the default scan fit, JCEfresco performs the following sequence.

## 1. Coarse SFRESCOX scan

A native SFRESCOX scan samples \(\chi^2(A)\) over a broad amplitude range.

If no explicit range is supplied, the automatic scan is centered on the starting amplitude and spans approximately

```text
A0 ± |A0|
```

or `[-1,1]` for amplitudes near zero.

The coarse scan can be controlled with:

```text
--scan-min
--scan-max
--scan-step
```

## 2. Local refinement scan

A second, finer scan is built around the best coarse point.

For example, if the coarse scan uses

```text
3.0 ... 5.0 in steps of 0.25
```

and the best point is \(A=4.0\), the default refinement factor of 5 produces a local scan approximately from

```text
3.75 ... 4.25 in steps of 0.05
```

## 3. Discrete minimum selection

The **lowest explicitly evaluated refinement point** is the final fit amplitude.

This is intentionally different from blindly adopting the minimum of a fitted parabola when the underlying FRESCOX objective contains small numerical jitter.

## 4. Local quadratic diagnostic

A local quadratic fit is still used to describe the curvature near the minimum and to provide a useful continuous-minimum diagnostic.

However, the parabola is not the authoritative source of the final published amplitude.

## 5. Final SFRESCOX verification

The chosen amplitude is re-evaluated with SFRESCOX using the equivalent of:

```text
SET + CHI + SHOW
```

## 6. Exact standalone FRESCOX calculation

A best-fit input card is written and run through ordinary FRESCOX.

## 7. Independent JCEfresco cross-check

The exact final FRESCOX curve is compared directly with the experimental points.

Only after these checks does JCEfresco publish the fitted curve.

---

# Conceptual fitting flow

```text
existing config + fort.3 + fort.16 + experimental CSV
                        |
                        v
                  generate search.in
                        |
                        v
                 native SFRESCOX scan
                        |
                        v
                 coarse minimum basin
                        |
                        v
                  refinement scan
                        |
                        v
            lowest evaluated amplitude
                        |
                        v
           final SFRESCOX SET/CHI/SHOW
                        |
                        v
              write best-fit .nin card
                        |
                        v
                     FRESCOX
                        |
                        v
                     fort.16
                        |
                        v
          existing JCEfresco split_fort16()
                        |
                        v
             stateN_sfresco_fit.txt
                        |
                        v
             independent chi-square check
                        |
                        v
                  existing plot.py
```

---

# Profile-\(\chi^2\) uncertainty interval

For a one-parameter fit, the default uncertainty interval is obtained from the profile condition

\[
\chi^2(A) = \chi^2_{\min} + \Delta\chi^2,
\]

with

\[
\Delta\chi^2 = 1
\]

for the default one-parameter 1\(\sigma\) interval.

JCEfresco:

1. combines the coarse and refined SFRESCOX scan points;
2. treats the discrete evaluated SFRESCOX minimum as the best-fit amplitude;
3. locates the nearest evaluated brackets around the lower and upper \(\Delta\chi^2=1\) crossings;
4. linearly interpolates each crossing;
5. writes the profile table;
6. writes a diagnostic \(\chi^2\)-versus-amplitude plot.

Generated files include:

```text
chi2_profile.csv
chi2_vs_A.png
```

The confidence threshold can be changed with:

```bash
--delta-chisq VALUE
```

The default is:

```text
--delta-chisq 1.0
```

---

# Uncertainty-band propagation — v7 behavior

The v7 fitter repairs the uncertainty-band propagation used by the earlier v6 implementation.

The central issue is that independent FRESCOX reruns at the lower and upper amplitude limits may introduce small run-to-run numerical jitter. In a simple one-CFP DWBA case where the fitted amplitude acts only as a multiplicative transfer amplitude,

\[
\sigma(\theta;A) \propto A^2,
\]

so the relative band width should be angle-independent and the exact best-fit curve should lie inside the band at every angle.

## Default mode

```text
--band-propagation auto
```

In `auto` mode, JCEfresco first tests whether the calculation truly obeys \(A^2\) scaling.

It compares the original FRESCOX curve at the original CFP amplitude with the exact final best-fit curve and checks whether

\[
\sigma_{\mathrm{initial}}(\theta)
\left(\frac{A_{\mathrm{best}}}{A_{\mathrm{initial}}}\right)^2
\]

reproduces the final best-fit curve within numerical tolerance.

### If the \(A^2\) test passes

The uncertainty band is generated directly from the single exact best-fit curve:

\[
\sigma_{\mathrm{low}}(\theta)
=
\sigma_{\mathrm{best}}(\theta)
\frac{\min(A^2\;\mathrm{on\ interval})}{A_{\mathrm{best}}^2},
\]

\[
\sigma_{\mathrm{high}}(\theta)
=
\sigma_{\mathrm{best}}(\theta)
\frac{\max(A^2\;\mathrm{on\ interval})}{A_{\mathrm{best}}^2}.
\]

No additional FRESCOX runs are required.

Typical terminal output is similar to:

```text
[band-check] sigma~A^2: rms=...% max=...% -> PASS
[1sigma-band] analytic A^2 propagation from exact best-fit curve; no extra FRESCOX runs
[1sigma-band] method=A2-scale
```

### If the \(A^2\) test fails

`auto` falls back to a **sampled FRESCOX envelope**.

Several amplitudes across the accepted profile interval are calculated explicitly. The exact best-fit curve is included, and the pointwise minimum/maximum over those curves defines the band.

This mode is intended for cases where the cross-section response is not a pure normalization change, such as coherent multi-component interference or other angle-dependent/nonlinear amplitude dependence.

---

# Band-propagation controls

```text
--band-propagation auto
```

Default. Validate \(A^2\) scaling; otherwise fall back to a sampled envelope.

```text
--band-propagation scale
```

Require validated \(A^2\) scaling. Fail if the test does not pass.

```text
--band-propagation sampled
```

Always generate the uncertainty band from a sampled FRESCOX envelope.

```text
--band-samples 7
```

Set the number of amplitudes sampled across the interval in sampled mode.

```text
--no-uncertainty-band
```

Still calculate and report the profile interval, but skip the uncertainty-band curves.

---

# Fitter outputs

Each fit is isolated in a directory such as:

```text
<calculation>/sfresco_fit/state1_cfp2/
```

Typical contents include:

```text
search.in
sfrescox.commands
sfrescox.log
search.plot
bestfit_<input>.nin
bestfit_frescox.out
fort.3
fort.13
fort.16
fresco_dists/
fit_summary.json
chi2_profile.csv
chi2_vs_A.png
```

`fort.13` is included when produced by the local FRESCOX build.

The final exact best-fit distribution is published into the ordinary JCEfresco curve directory with a name such as:

```text
workdir/9Be6Lid_dwba/10753keV/fresco_dists/state1_sfresco_fit.txt
```

so that the existing plotting machinery can consume it directly.

When uncertainty-band curves are generated, they are written as:

```text
stateN_sfresco_1sigma_low.txt
stateN_sfresco_1sigma_high.txt
```

---

# `fit_summary.json`

The fit summary records quantities including:

- initial amplitude;
- final best-fit amplitude;
- amplitude uncertainty information;
- \(A^2\);
- SFRESCOX `ChiSq/N` information;
- total \(\chi^2\);
- conventional reduced \(\chi^2\) for the one-parameter fit, using the appropriate \(N-1\) degree-of-freedom count;
- bookkeeping needed to reproduce the selected CFP and final fit.

---

# Plotting the fitted curve and uncertainty band

The plotting interface accepts:

```text
--band MODEL:LOW_FILE:HIGH_FILE[:LABEL]
```

For example:

```bash
python scripts/plot.py \
    --reaction 6lid \
    --state 10753 \
    --curve 'dwba:state1.txt:1.0:DWBA:dashed' \
    --curve 'dwba:state1_sfresco_fit.txt:1.0:SFRESCOX fit:solid' \
    --band 'dwba:state1_sfresco_1sigma_low.txt:state1_sfresco_1sigma_high.txt:SFRESCOX 1sigma' \
    --theta-max 50
```

Existing plotting commands without `--band` continue to behave normally.

---

# Terminal progress and logs

The default scan/refinement path prints live progress for expensive calculations.

Typical output resembles:

```text
[coarse-scan] [####--------------]  2/9  A=3.25  chi2/dof=15.086  elapsed=... ETA~...
[refine-scan] [########----------]  5/11 A=3.95  chi2/dof=...     elapsed=... ETA~...
[scan-fit]   A=... +/- ..., quadratic ChiSq/dof~...
[final-sfrescox] starting SFRESCOX...
[final-frescox] starting exact best-fit FRESCOX calculation...
```

Long individual subprocesses also emit a heartbeat so the terminal does not appear frozen.

Raw subprocess output is saved to log files.

Use:

```text
--verbose-subprocess
```

to mirror raw subprocess output live to the terminal.

Use:

```text
--quiet-progress
```

to suppress progress messages.

---

# Historical behavior and why it changed

The fitter evolved through several safeguards that are now folded into the current workflow.

## Early implementation

The first fitter used SFRESCOX with MINUIT/MIGRAD to optimize the selected CFP amplitude, then wrote a final FRESCOX card and published the resulting parsed curve.

## v3 safeguards

The fitter was strengthened to:

- supply the actual incident laboratory energy to the SFRESCOX data block;
- run a coarse native SFRESCOX scan before MIGRAD;
- seed MIGRAD near the best scan basin;
- require explicit MIGRAD convergence;
- read final \(\chi^2\) from `CHI` output;
- independently compare the final standalone FRESCOX curve against the experiment;
- choose a MINUIT finite-difference step relative to the starting amplitude rather than always using a hard-coded 0.01.

## v4 default-method change

Because the FRESCOX objective exhibited small numerical jitter at the tiny parameter displacements relevant to finite-difference derivatives, the scan/refinement method became the default and MIGRAD became optional.

## v5 final-amplitude policy

The final published fit amplitude was restricted to an amplitude actually evaluated by SFRESCOX. The local quadratic remained a curvature/uncertainty diagnostic rather than the authority for the final card.

## v6 profile interval

A profile-\(\chi^2\) interval and corresponding uncertainty-band curves were added.

## v7 band propagation

The band machinery was revised so that simple one-amplitude normalization fits use validated \(A^2\) propagation from the exact best-fit curve, avoiding artificial angle dependence caused by independent reruns. More complicated cases automatically use a sampled FRESCOX envelope.

---

# Useful FRESCO/FRESCOX commands

## Convert an old-style FRESCO input to namelist format

A legacy converter may be used for old input cards, for example:

```text
frnl.f
```

## Watch FRESCO output live while saving it

```bash
~/fresco < input.in | tee output.out
```

## Capture stdout and stderr for debugging

```bash
fresco < input.in > output.out 2>&1
```

---

# Recommended first sanity check

For the 10.753-MeV test case used during development:

```bash
python scripts/fit.py \
    --reaction 6lid \
    --state 10753 \
    --model dwba \
    --cfp 2 \
    --scan-min 3.0 \
    --scan-max 5.0 \
    --scan-step 0.25 \
    --theta-max 50
```

A successful run should:

1. identify the requested outgoing state and CFP;
2. complete the coarse and refinement scans;
3. choose the lowest evaluated scan point as the fit amplitude;
4. calculate the profile-\(\chi^2\) interval;
5. verify the final amplitude with SFRESCOX;
6. run the exact standalone best-fit FRESCOX card;
7. independently compare that curve to the experimental data;
8. publish `stateN_sfresco_fit.txt`;
9. generate the uncertainty band using validated \(A^2\) scaling or a sampled envelope;
10. print a ready-to-run plotting command.

For the original development scan discussed in the v5/v6 notes, the fitted minimum was near \(A=4.00\); that number should be treated only as a historical sanity check for that specific calculation, not as a universal expected result.

---

# Design philosophy

JCEfresco deliberately keeps the fitting layer tied to the **actual FRESCOX calculation**.

The fitted spectroscopic amplitude is not applied as an arbitrary scale factor after the fact. Instead, the selected CFP amplitude is varied inside the FRESCOX/SFRESCOX machinery, the resulting theoretical distribution is evaluated against the experimental data, and the final amplitude is written back into an ordinary FRESCOX input card.

That architecture preserves the full reaction calculation and allows the same infrastructure to remain valid when a fitted amplitude affects more than a simple overall normalization.

---

# Quick command summary

### Parse

```bash
python scripts/split.py --reaction 6Lid
```

### Plot one curve per model

```bash
python scripts/plot.py \
    --reaction 6Lid \
    --state 10753 \
    --models dwba cdcc
```

### Plot several curves/components

```bash
python scripts/plot.py \
    --reaction dp \
    --state 3089 \
    --curve 'cc:state2.txt:1.0:total:solid' \
    --curve 'cc:state3.txt:1.0:0s1/2' \
    --curve 'cc:state4.txt:1.0:2d5/2'
```

### Fit a CFP amplitude

```bash
python scripts/fit.py \
    --reaction 6lid \
    --state 10753 \
    --model dwba \
    --cfp 2 \
    --scan-min 3.0 \
    --scan-max 5.0 \
    --scan-step 0.25 \
    --theta-max 50
```

### Force MIGRAD instead of the default scan method

```bash
python scripts/fit.py ... --fit-method migrad
```

### Skip uncertainty-band curve generation

```bash
python scripts/fit.py ... --no-uncertainty-band
```

### Force sampled band propagation

```bash
python scripts/fit.py ... --band-propagation sampled --band-samples 7
```

---

## Status

The current documented behavior corresponds to the **v7 SFRESCOX fitting workflow**, including:

- evaluated-point best-fit selection;
- derivative-free coarse/refined scan as the default minimizer;
- optional MINUIT/MIGRAD path;
- final SFRESCOX and standalone FRESCOX verification;
- profile-\(\chi^2\) one-parameter intervals;
- validated \(A^2\) uncertainty propagation for pure normalization cases;
- sampled FRESCOX-envelope fallback for nonlinear or interfering cases;
- repeated custom `--curve` plotting with per-curve labels and line styles.
