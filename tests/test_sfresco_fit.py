from pathlib import Path

import pytest

from jcefresco.fitting.sfresco import (
    ExperimentalPoint,
    NumberedCFP,
    ScanPoint,
    amplitude_squared_scale_bounds,
    automatic_scan_range,
    best_scan_point,
    parabolic_scan_estimate,
    calculate_curve_chisq,
    channel_for_state_file,
    parse_fit_result,
    parse_scan_fit_result,
    relevant_cfps,
    refinement_scan_range,
    scan_point_count,
    validate_curve_chisq,
    validate_amplitude_squared_scaling,
    validate_input_cfp_order,
    validate_reported_amplitude,
    write_best_fit_input,
    write_curve_envelope,
    write_command_file,
    write_final_scan_command_file,
    write_search_file,
    write_scaled_amplitude_band,
)
from jcefresco.parser.xsec_map_parser import CFPInfo
from jcefresco.cli_fit import _select_cfp


FORT16 = '''
@ s0 legend "Partition=  1 Excit=  1 near/far= 1"
projectile
0.0 100.0
&
@ s1 legend "Partition=  2 Excit=  1 near/far= 1"
projectile
10.0 9.0
&
'''

FRESCO_INPUT = '''test transfer
NAMELIST
&FRESCO thmin=0 thmax=60 thinc=1 /
&COUPLING icto=2 icfrom=1 kind=7 /
&cfp in=1 ib=1 ia=1 kn=1 a=0.8307 /
&cfp in=-2 ib=1 ia=1 kn=2 a=4.960 /
'''

FRESCO_INPUT_WITH_TERMINATOR = """test transfer
NAMELIST
&FRESCO thmin=0 thmax=60 thinc=1 /
&COUPLING icto=2 icfrom=1 kind=7 /
&cfp in=1 ib=1 ia=1 kn=1 a=0.8307 /
&cfp in=2 ib=1 ia=1 kn=2 a=4.960 /
&cfp in=0 ib=0 ia=0 kn=0 a=0.000 /
"""


def test_negative_in_matches_target_partition(tmp_path: Path):
    fort16 = tmp_path / "fort.16"
    fort16.write_text(FORT16)
    channel = channel_for_state_file(fort16, "state1.txt")

    cfps = [
        NumberedCFP(1, CFPInfo(1, 1, 1, 1, 0.8307)),
        NumberedCFP(2, CFPInfo(-2, 1, 1, 2, 4.960)),
    ]
    matches = relevant_cfps(cfps, channel)
    assert [match.number for match in matches] == [2]
    assert matches[0].physical_in == 2


def test_validate_realistic_negative_in_order(tmp_path: Path):
    inp = tmp_path / "calc.nin"
    inp.write_text(FRESCO_INPUT)
    cfps = [
        NumberedCFP(1, CFPInfo(1, 1, 1, 1, 0.8307)),
        NumberedCFP(2, CFPInfo(-2, 1, 1, 2, 4.960)),
    ]
    validate_input_cfp_order(inp, cfps)


def test_write_search_file_kind2(tmp_path: Path):
    selected = NumberedCFP(2, CFPInfo(-2, 1, 1, 2, 4.960))
    points = [
        ExperimentalPoint(10.0, 1.48, 0.15),
        ExperimentalPoint(12.0, 1.66, 0.17),
    ]
    path = write_search_file(
        tmp_path / "search.in",
        fresco_input="calc.nin",
        fresco_output="fit.out",
        cfp=selected,
        points=points,
        partition=2,
        excitation=1,
        energy=32.0,
    )
    text = path.read_text()
    assert "kind=2" in text
    assert "nafrac=2" in text
    assert "afrac=4.96" in text
    assert "ic=2 ia=1" in text
    assert "abserr=T" in text
    assert "iscale=2" in text
    assert "energy=32" in text
    assert "10 1.48 0.15" in text


def test_write_best_fit_changes_only_selected_cfp(tmp_path: Path):
    source = tmp_path / "calc.nin"
    source.write_text(FRESCO_INPUT)
    destination = tmp_path / "bestfit.nin"

    write_best_fit_input(source, destination, cfp_number=2, amplitude=1.8717)
    text = destination.read_text()
    assert "a=0.8307" in text
    assert "A=1.8717" in text
    assert "a=4.960" not in text


def test_parse_fit_result_requires_converged_migrad(tmp_path: Path):
    plot = tmp_path / "search.plot"
    log = tmp_path / "sfrescox.log"
    plot.write_text("# Var 1=A2 value 4.959988, step 0.0100, error 0.0000\n")
    log.write_text(
        "MIGRAD TERMINATED WITHOUT CONVERGENCE.\n"
        "Var 1=A2 value 4.959988, step 0.0100, error 0.0000\n"
        "Total ChiSq = 205.1: 29.293 per dof from dof = 7\n"
    )
    with pytest.raises(RuntimeError, match="did not converge"):
        parse_fit_result(plot, log_file=log, n_points=8)


def test_parse_fit_result_uses_chi_command_total(tmp_path: Path):
    plot = tmp_path / "search.plot"
    log = tmp_path / "sfrescox.log"
    plot.write_text("# Var 1=A2 value 4.0123, step 0.04, error 0.05\n")
    log.write_text(
        "MIGRAD MINIMIZATION HAS CONVERGED.\n"
        "Var 1=A2 value 4.0123, step 0.04, error 0.05\n"
        "Total ChiSq = 25.2000: 3.6000 per dof from dof = 7\n"
    )
    result = parse_fit_result(plot, log_file=log, n_points=8)
    assert result.amplitude == pytest.approx(4.0123)
    assert result.amplitude_error == pytest.approx(0.05)
    assert result.sfresco_chisq == pytest.approx(25.2)
    assert result.sfresco_reduced_chisq == pytest.approx(3.6)
    assert result.dof == 7


def test_scan_parser_finds_best_point():
    text = """
Variable 1:A2 = 3.7500 : ChiSq/df= 5.274
Variable 1:A2 = 4.0000 : ChiSq/df= 3.633
Variable 1:A2 = 4.2500 : ChiSq/df= 6.082
"""
    point = best_scan_point(text)
    assert point.amplitude == pytest.approx(4.0)
    assert point.reduced_chisq == pytest.approx(3.633)


def test_automatic_scan_range_for_positive_amplitude():
    lo, hi, step = automatic_scan_range(4.96)
    assert lo == pytest.approx(0.0)
    assert hi == pytest.approx(9.92)
    assert step == pytest.approx(9.92 / 20.0)


def test_command_file_seeds_minuit_and_requests_chi(tmp_path: Path):
    path = write_command_file(
        tmp_path / "commands",
        search_file="search.in",
        initial_value=4.0,
    )
    text = path.read_text().lower()
    assert "set 1 4" in text
    assert text.count("chi") == 2
    assert "migrad" in text


def test_independent_curve_chisq(tmp_path: Path):
    curve = tmp_path / "state1.txt"
    curve.write_text("0 5\n10 2\n20 1\n30 0.5\n")
    points = [
        ExperimentalPoint(10.0, 2.0, 0.2),
        ExperimentalPoint(20.0, 1.2, 0.1),
    ]
    check = calculate_curve_chisq(points, curve)
    assert check.chisq == pytest.approx(4.0)
    assert check.reduced_chisq == pytest.approx(4.0)


def test_curve_chisq_validation_rejects_mismatch(tmp_path: Path):
    plot = tmp_path / "search.plot"
    log = tmp_path / "sfrescox.log"
    plot.write_text("# Var 1=A2 value 4.0, step 0.04, error 0.05\n")
    log.write_text(
        "MIGRAD MINIMIZATION HAS CONVERGED.\n"
        "Var 1=A2 value 4.0, step 0.04, error 0.05\n"
        "Total ChiSq = 25.0: 3.5714 per dof from dof = 7\n"
    )
    result = parse_fit_result(plot, log_file=log, n_points=8)
    from jcefresco.fitting.sfresco import CurveChiSquare
    check = CurveChiSquare(chisq=50.0, reduced_chisq=50/7, n_points=8, max_abs_pull=3.0)
    with pytest.raises(RuntimeError, match="cross-check"):
        validate_curve_chisq(result, check)


def test_split_and_publish_uses_existing_fort16_splitter(tmp_path: Path):
    from jcefresco.fitting.sfresco import split_and_publish_best_curve

    fit_dir = tmp_path / "fit"
    fit_dir.mkdir()
    (fit_dir / "fort.16").write_text(FORT16)
    publish_dir = tmp_path / "original" / "fresco_dists"

    local_curve, published = split_and_publish_best_curve(
        fit_dir=fit_dir,
        state_file="state1.txt",
        publish_dir=publish_dir,
    )

    assert local_curve.is_file()
    assert published.name == "state1_sfresco_fit.txt"
    assert published.read_text() == local_curve.read_text()


def test_validate_ignores_zeroed_cfp_terminator(tmp_path: Path):
    inp = tmp_path / "calc.nin"
    inp.write_text(FRESCO_INPUT_WITH_TERMINATOR)
    cfps = [
        NumberedCFP(1, CFPInfo(1, 1, 1, 1, 0.8307)),
        NumberedCFP(2, CFPInfo(2, 1, 1, 2, 4.960)),
    ]
    validate_input_cfp_order(inp, cfps)


def test_write_best_fit_ignores_zeroed_terminator(tmp_path: Path):
    source = tmp_path / "calc.nin"
    source.write_text(FRESCO_INPUT_WITH_TERMINATOR)
    destination = tmp_path / "bestfit.nin"

    write_best_fit_input(source, destination, cfp_number=2, amplitude=1.2345)
    text = destination.read_text()
    assert "A=1.2345" in text
    assert "a=0.8307" in text
    assert "a=0.000" in text


def test_explicit_cfp_is_authoritative_even_if_not_outgoing_candidate():
    all_cfps = [
        NumberedCFP(1, CFPInfo(1, 1, 1, 1, 0.8307)),
        NumberedCFP(2, CFPInfo(2, 1, 1, 2, 4.960)),
    ]
    candidates = [all_cfps[1]]
    selected = _select_cfp(all_cfps, candidates, requested=1)
    assert selected.number == 1



def test_scan_point_count_inclusive():
    assert scan_point_count(3.0, 5.0, 0.25) == 9


def test_refinement_scan_brackets_discrete_minimum():
    points = [
        ScanPoint(3.75, 5.274),
        ScanPoint(4.00, 3.633),
        ScanPoint(4.25, 6.082),
    ]
    lo, hi, step = refinement_scan_range(points, factor=5)
    assert lo == pytest.approx(3.75)
    assert hi == pytest.approx(4.25)
    assert step == pytest.approx(0.05)


def test_parabolic_scan_estimate_matches_real_coarse_scan():
    points = [
        ScanPoint(3.50, 9.014),
        ScanPoint(3.75, 5.274),
        ScanPoint(4.00, 3.633),
        ScanPoint(4.25, 6.082),
        ScanPoint(4.50, 10.015),
    ]
    estimate = parabolic_scan_estimate(points, dof=7)
    assert estimate.amplitude == pytest.approx(3.98, abs=0.05)
    assert estimate.amplitude_error is not None
    assert 0.03 < estimate.amplitude_error < 0.12


def test_final_scan_command_has_no_migrad(tmp_path: Path):
    path = write_final_scan_command_file(
        tmp_path / "commands",
        search_file="search.in",
        plot_file="search.plot",
        amplitude=3.98,
    )
    text = path.read_text().lower()
    assert "set 1 3.98" in text
    assert "chi" in text
    assert "show" in text
    assert "plot search.plot" in text
    assert "migrad" not in text
    assert "min\n" not in text


def test_parse_scan_fit_result_does_not_require_migrad(tmp_path: Path):
    plot = tmp_path / "search.plot"
    log = tmp_path / "sfrescox.log"
    plot.write_text("# Var 1=A2 value 3.981, step 0.04, error 0.0000\n")
    log.write_text(
        "Var 1=A2 value 3.981, step 0.04, error 0.0000\n"
        "Total ChiSq= 24.500: 3.5000 per dof from dof = 7\n"
    )
    result = parse_scan_fit_result(
        plot,
        log_file=log,
        n_points=8,
        amplitude_error=0.06,
    )
    assert result.method == "scan"
    assert result.amplitude == pytest.approx(3.981)
    assert result.amplitude_error == pytest.approx(0.06)
    assert result.sfresco_chisq == pytest.approx(24.5)
    assert result.sfresco_reduced_chisq == pytest.approx(3.5)


def test_validate_reported_amplitude_accepts_rounding():
    validate_reported_amplitude(4.0, 4.0000004)


def test_validate_reported_amplitude_rejects_wrong_handoff():
    with pytest.raises(RuntimeError, match="handoff mismatch"):
        validate_reported_amplitude(4.0, 4.006)


def test_curve_chisq_validation_allows_small_numerical_difference(tmp_path: Path):
    plot = tmp_path / "search.plot"
    log = tmp_path / "sfrescox.log"
    plot.write_text("# Var 1=A2 value 4.0, step 0.04, error 0.05\n")
    log.write_text(
        "MIGRAD MINIMIZATION HAS CONVERGED.\n"
        "Var 1=A2 value 4.0, step 0.04, error 0.05\n"
        "Total ChiSq = 26.62: 3.8029 per dof from dof = 7\n"
    )
    result = parse_fit_result(plot, log_file=log, n_points=8)
    from jcefresco.fitting.sfresco import CurveChiSquare
    check = CurveChiSquare(chisq=25.7398, reduced_chisq=25.7398/7, n_points=8, max_abs_pull=3.0)
    relative = validate_curve_chisq(result, check)
    assert relative == pytest.approx(abs(26.62 - 25.7398) / 26.62)


def test_curve_chisq_validation_rejects_large_difference(tmp_path: Path):
    plot = tmp_path / "search.plot"
    log = tmp_path / "sfrescox.log"
    plot.write_text("# Var 1=A2 value 4.0, step 0.04, error 0.05\n")
    log.write_text(
        "MIGRAD MINIMIZATION HAS CONVERGED.\n"
        "Var 1=A2 value 4.0, step 0.04, error 0.05\n"
        "Total ChiSq = 25.0: 3.5714 per dof from dof = 7\n"
    )
    result = parse_fit_result(plot, log_file=log, n_points=8)
    from jcefresco.fitting.sfresco import CurveChiSquare
    check = CurveChiSquare(chisq=30.0, reduced_chisq=30/7, n_points=8, max_abs_pull=3.0)
    with pytest.raises(RuntimeError, match="cross-check"):
        validate_curve_chisq(result, check)


def test_profile_interval_delta_chisq_one_matches_real_refine_scan():
    from jcefresco.fitting.sfresco import profile_interval_from_scan

    points = [
        ScanPoint(3.75, 5.274),
        ScanPoint(3.80, 4.796),
        ScanPoint(3.85, 4.198),
        ScanPoint(3.90, 4.034),
        ScanPoint(3.95, 3.935),
        ScanPoint(4.00, 3.633),
        ScanPoint(4.05, 3.818),
        ScanPoint(4.10, 3.852),
        ScanPoint(4.15, 4.161),
        ScanPoint(4.20, 4.791),
        ScanPoint(4.25, 6.082),
    ]
    interval = profile_interval_from_scan(points, dof=7, delta_chisq=1.0)
    assert interval.best_amplitude == pytest.approx(4.0)
    assert interval.lower_amplitude == pytest.approx(3.97635, abs=1e-4)
    assert interval.upper_amplitude == pytest.approx(4.03861, abs=1e-4)
    assert interval.chi2_threshold - interval.chi2_min == pytest.approx(1.0)


def test_profile_interval_requires_both_crossings():
    from jcefresco.fitting.sfresco import profile_interval_from_scan

    points = [
        ScanPoint(3.95, 3.70),
        ScanPoint(4.00, 3.63),
        ScanPoint(4.05, 3.70),
    ]
    with pytest.raises(ValueError, match="Could not bracket"):
        profile_interval_from_scan(points, dof=7, delta_chisq=1.0)


def test_write_chisq_profile_csv(tmp_path: Path):
    from jcefresco.fitting.sfresco import profile_interval_from_scan, write_chisq_profile_csv

    points = [
        ScanPoint(3.95, 3.935),
        ScanPoint(4.00, 3.633),
        ScanPoint(4.05, 3.818),
    ]
    interval = profile_interval_from_scan(points, dof=7, delta_chisq=1.0)
    path = write_chisq_profile_csv(tmp_path / "chi2_profile.csv", points, dof=7, interval=interval)
    text = path.read_text()
    assert "amplitude,reduced_chisq,chisq,delta_chisq" in text
    assert "4,3.633" in text


def test_plot_band_spec_is_additive(tmp_path: Path):
    from jcefresco.config import ProjectConfig
    from jcefresco.reactions import get_reaction
    from jcefresco.cli_plot import parse_band_spec

    config = ProjectConfig(
        repo=tmp_path,
        source=tmp_path / "config.yaml",
        raw={
            "paths": {"workdir": "workdir", "data": "data", "figures": "figures"},
            "parsing": {"output_directory": "fresco_dists"},
            "models": {"aliases": {}},
            "reactions": {
                "6lid": {
                    "models": {"dwba": {"directory": "calc", "default_state_file": "state1.txt"}}
                }
            },
        },
    )
    reaction = get_reaction(config, "6lid")
    band = parse_band_spec(
        "dwba:state1_sfresco_1sigma_low.txt:state1_sfresco_1sigma_high.txt:1 sigma",
        config=config,
        reaction=reaction,
        state_keV=10753,
    )
    assert band.model == "dwba"
    assert band.low_file.endswith("_low.txt")
    assert band.high_file.endswith("_high.txt")
    assert band.label == "1 sigma"


def test_amplitude_squared_band_has_constant_fractional_width(tmp_path: Path):
    best = tmp_path / "best.txt"
    best.write_text("0 10\n10 2\n20 0.5\n30 0.1\n")
    low = tmp_path / "low.txt"
    high = tmp_path / "high.txt"

    write_scaled_amplitude_band(
        best,
        low,
        high,
        best_amplitude=4.0,
        lower_amplitude=3.8,
        upper_amplitude=4.2,
    )

    import numpy as np

    best_data = np.loadtxt(best)
    low_data = np.loadtxt(low)
    high_data = np.loadtxt(high)
    assert np.allclose(low_data[:, 1] / best_data[:, 1], (3.8 / 4.0) ** 2)
    assert np.allclose(high_data[:, 1] / best_data[:, 1], (4.2 / 4.0) ** 2)
    assert np.all(low_data[:, 1] <= best_data[:, 1])
    assert np.all(best_data[:, 1] <= high_data[:, 1])


def test_amplitude_squared_bounds_handle_interval_crossing_zero():
    low, high = amplitude_squared_scale_bounds(
        best_amplitude=1.0,
        lower_amplitude=-0.5,
        upper_amplitude=1.5,
    )
    assert low == pytest.approx(0.0)
    assert high == pytest.approx(2.25)


def test_validate_amplitude_squared_scaling_passes_exact_scaling(tmp_path: Path):
    original = tmp_path / "original.txt"
    best = tmp_path / "best.txt"
    original.write_text("0 15.376\n10 3.0752\n20 0.7688\n")
    # A changes from 4.96 to 4.0, so sigma changes by (4/4.96)^2.
    factor = (4.0 / 4.96) ** 2
    best.write_text(
        "\n".join(
            f"{theta} {xsec * factor:.12g}"
            for theta, xsec in [(0, 15.376), (10, 3.0752), (20, 0.7688)]
        )
        + "\n"
    )
    check = validate_amplitude_squared_scaling(
        original,
        best,
        reference_amplitude=4.96,
        best_amplitude=4.0,
    )
    assert check.passed
    assert check.max_relative_difference < 1e-9


def test_validate_amplitude_squared_scaling_rejects_shape_change(tmp_path: Path):
    original = tmp_path / "original.txt"
    best = tmp_path / "best.txt"
    original.write_text("0 10\n10 2\n20 1\n")
    best.write_text("0 6\n10 1.4\n20 0.4\n")
    check = validate_amplitude_squared_scaling(
        original,
        best,
        reference_amplitude=5.0,
        best_amplitude=4.0,
    )
    assert not check.passed


def test_sampled_envelope_always_contains_best_curve(tmp_path: Path):
    best = tmp_path / "best.txt"
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    low = tmp_path / "low.txt"
    high = tmp_path / "high.txt"
    best.write_text("0 5\n10 2\n20 1\n")
    # Both sampled endpoint curves lie above the best at 10 degrees; the best
    # must still be retained inside the envelope.
    a.write_text("0 4\n10 2.5\n20 0.8\n")
    b.write_text("0 6\n10 2.2\n20 1.4\n")

    write_curve_envelope([a, b], low, high, reference_curve=best)

    import numpy as np

    best_data = np.loadtxt(best)
    low_data = np.loadtxt(low)
    high_data = np.loadtxt(high)
    assert np.all(low_data[:, 1] <= best_data[:, 1])
    assert np.all(best_data[:, 1] <= high_data[:, 1])
