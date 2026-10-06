from __future__ import annotations

"""CLI for JCEfresco's third component: SFRESCOX amplitude fitting."""

import argparse
from pathlib import Path
import shlex
import shutil

from .config import load_config
from .fitting import (
    NumberedCFP,
    validate_amplitude_squared_scaling,
    automatic_scan_range,
    beam_energy_for_channel,
    best_scan_point,
    parabolic_scan_estimate,
    profile_interval_from_scan,
    plot_chisq_profile,
    calculate_curve_chisq,
    channel_for_state_file,
    choose_fresco_input,
    load_experimental_points,
    numbered_cfps_from_fort3,
    parse_fit_result,
    parse_scan_fit_result,
    parse_scan_results,
    relevant_cfps,
    refinement_scan_range,
    run_frescox,
    run_frescox_curve_at_amplitude,
    run_sfrescox,
    scan_point_count,
    split_and_publish_best_curve,
    validate_curve_chisq,
    validate_input_cfp_order,
    validate_reported_amplitude,
    write_best_fit_input,
    write_command_file,
    write_final_scan_command_file,
    write_scan_command_file,
    write_search_file,
    write_curve_envelope,
    write_scaled_amplitude_band,
    write_summary_json,
    write_chisq_profile_csv,
)
from .reactions import experimental_path, get_reaction, model_directory, normalize_model
from .utils.repo import resolve_repo_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fit one FRESCOX &CFP spectroscopic amplitude to an experimental "
            "angular distribution. The default is a derivative-free SFRESCOX "
            "scan/refinement minimizer; MINUIT/MIGRAD remains available as an "
            "optional method. The exact best-fit card can then be run and "
            "published for plot.py."
        )
    )
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--reaction", required=True)
    parser.add_argument("--state", type=int, required=True, help="State energy in keV.")
    parser.add_argument("--model", required=True, help="Configured model, e.g. dwba or cc.")
    parser.add_argument(
        "--state-file",
        default=None,
        help="Curve to fit, e.g. state1.txt. Default: model's configured state file.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Original namelist FRESCOX input. Auto-discovered if unambiguous.",
    )
    parser.add_argument(
        "--exp",
        type=Path,
        default=None,
        help="Experimental angle/xsec/xsec_err CSV. Default: configured reaction data.",
    )
    parser.add_argument(
        "--cfp",
        type=int,
        default=None,
        help=(
            "1-based physical &CFP order (SFRESCOX nafrac). Explicit --cfp is "
            "authoritative and may select any physical CFP. Zeroed CFP terminators "
            "do not count. Without --cfp, JCEfresco auto-selects only when exactly "
            "one CFP feeds the requested outgoing partition/state."
        ),
    )
    parser.add_argument(
        "--fit-method",
        choices=("scan", "migrad"),
        default="scan",
        help=(
            "Minimization method. Default: scan (native SFRESCOX coarse scan + "
            "local refined scan + quadratic minimum). Use migrad to request the "
            "legacy derivative-based MINUIT/MIGRAD path."
        ),
    )
    parser.add_argument("--theta-min", type=float, default=None)
    parser.add_argument("--theta-max", type=float, default=None)
    parser.add_argument(
        "--step",
        type=float,
        default=None,
        help=(
            "Initial MINUIT derivative step for --fit-method migrad. Ignored by "
            "the default scan minimizer. Default: automatic (~1%% of A)."
        ),
    )
    parser.add_argument("--min", dest="valmin", type=float, default=None, help="Lower bound on A.")
    parser.add_argument("--max", dest="valmax", type=float, default=None, help="Upper bound on A.")
    parser.add_argument(
        "--no-scan",
        action="store_true",
        help="Skip the coarse scan when using --fit-method migrad. Not valid for scan fitting.",
    )
    parser.add_argument(
        "--scan-min",
        type=float,
        default=None,
        help="Coarse scan lower bound. Must be supplied with --scan-max.",
    )
    parser.add_argument(
        "--scan-max",
        type=float,
        default=None,
        help="Coarse scan upper bound. Must be supplied with --scan-min.",
    )
    parser.add_argument(
        "--scan-step",
        type=float,
        default=None,
        help="Coarse SFRESCOX scan step. Default: ~20 intervals across the scan range.",
    )
    parser.add_argument(
        "--no-refine",
        action="store_true",
        help="For scan fitting, use only the coarse scan and local quadratic estimate.",
    )
    parser.add_argument(
        "--refine-factor",
        type=int,
        default=5,
        help=(
            "For scan fitting, divide the coarse bracket spacing by this factor "
            "for the local refinement scan. Default: 5."
        ),
    )
    parser.add_argument(
        "--delta-chisq",
        type=float,
        default=1.0,
        help=(
            "Profile-chi-square threshold above the minimum used for the amplitude "
            "confidence interval. Default: 1.0 (one fitted parameter, 1 sigma)."
        ),
    )
    parser.add_argument(
        "--no-uncertainty-band",
        action="store_true",
        help=(
            "Calculate/report the profile interval but skip uncertainty-band "
            "curve generation."
        ),
    )
    parser.add_argument(
        "--band-propagation",
        choices=("auto", "scale", "sampled"),
        default="auto",
        help=(
            "How to propagate the amplitude interval into an angular-distribution "
            "band. Default: auto. Auto verifies sigma~A^2 using the original and "
            "best-fit FRESCOX curves and uses exact constant-fractional scaling "
            "when valid; otherwise it falls back to a sampled FRESCOX envelope. "
            "Use scale to require the A^2 behavior, or sampled to force the "
            "nonlinear envelope."
        ),
    )
    parser.add_argument(
        "--band-samples",
        type=int,
        default=7,
        help=(
            "Number of amplitudes across the profile interval for sampled band "
            "propagation. The exact best fit is always included. Default: 7."
        ),
    )
    parser.add_argument(
        "--lab",
        action="store_true",
        help="Experimental angles/cross sections are laboratory-frame. Default: CM.",
    )
    parser.add_argument(
        "--iscale",
        type=int,
        default=2,
        choices=(-1, 0, 1, 2, 3),
        help="SFRESCOX units: -1 dimensionless, 0 fm^2/sr, 1 b/sr, 2 mb/sr, 3 ub/sr.",
    )
    parser.add_argument(
        "--sfresco-exe",
        default="sfrescox",
        help="SFRESCOX executable name/path. Default: sfrescox.",
    )
    parser.add_argument(
        "--fresco-exe",
        default="frescox",
        help="FRESCOX executable for the final exact best-fit run. Default: frescox.",
    )
    parser.add_argument(
        "--fit-dir",
        type=Path,
        default=None,
        help="Isolated output directory. Default: <calculation>/sfresco_fit/<state>_cfpN.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Write/validate search files but do not invoke sfrescox.",
    )
    parser.add_argument(
        "--no-final-run",
        action="store_true",
        help="Stop after SFRESCOX fit; do not run frescox with the best-fit amplitude.",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Keep the exact best-fit curve only inside the fit directory.",
    )
    parser.add_argument(
        "--publish-name",
        default=None,
        help="Filename placed in normal fresco_dists. Default: stateN_sfresco_fit.txt.",
    )
    parser.add_argument(
        "--quiet-progress",
        action="store_true",
        help="Disable live scan progress and subprocess heartbeat messages.",
    )
    parser.add_argument(
        "--verbose-subprocess",
        action="store_true",
        help="Mirror raw SFRESCOX/FRESCOX stdout to the terminal as well as log files.",
    )
    parser.add_argument("--timeout", type=float, default=None, help="Optional subprocess timeout (s).")
    return parser


def _select_cfp(
    all_cfps: list[NumberedCFP],
    candidates: list[NumberedCFP],
    requested: int | None,
) -> NumberedCFP:
    if requested is not None:
        if requested < 1 or requested > len(all_cfps):
            raise ValueError(
                f"--cfp {requested} is out of range; fort.3 contains {len(all_cfps)} physical CFP entries"
            )
        # An explicit --cfp is authoritative.  This intentionally allows fitting
        # projectile-side or otherwise non-final-state amplitudes when the user
        # wants to test them; JCEfresco only auto-selects by outgoing channel.
        return all_cfps[requested - 1]

    if len(candidates) == 1:
        return candidates[0]

    if not candidates:
        details = "\n".join("  " + cfp.short_label() for cfp in all_cfps)
        raise ValueError(
            "No &CFP entry matches the selected outgoing partition/state. "
            "Available entries:\n" + details
        )

    details = "\n".join("  " + cfp.short_label() for cfp in candidates)
    raise ValueError(
        "More than one &CFP entry feeds the selected state. Because those components "
        "may interfere coherently, JCEfresco will not guess which amplitude to vary. "
        "Choose explicitly with --cfp N:\n" + details
    )


def _plot_command(
    *,
    reaction: str,
    state_keV: int,
    model: str,
    original_state_file: str,
    published_name: str,
    theta_max: float | None,
    sigma_low_name: str | None = None,
    sigma_high_name: str | None = None,
) -> str:
    original = f"{model}:{original_state_file}:1.0:{model.upper()}:dashed"
    fitted = f"{model}:{published_name}:1.0:SFRESCOX fit:solid"
    parts = [
        "python",
        "scripts/plot.py",
        "--reaction",
        reaction,
        "--state",
        str(state_keV),
        "--curve",
        original,
        "--curve",
        fitted,
    ]
    if sigma_low_name is not None and sigma_high_name is not None:
        parts.extend([
            "--band",
            f"{model}:{sigma_low_name}:{sigma_high_name}:SFRESCOX 1sigma",
        ])
    if theta_max is not None:
        parts.extend(["--theta-max", f"{theta_max:g}"])
    return " ".join(shlex.quote(part) for part in parts)


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config, repo=args.repo)
    reaction = get_reaction(config, args.reaction)
    model_key = normalize_model(config, reaction, args.model)
    model = reaction.models[model_key]

    state_file = args.state_file or model.default_state_file
    calc_dir = model_directory(config, model) / f"{args.state}keV"
    if not calc_dir.is_dir():
        raise FileNotFoundError(f"Calculation directory not found: {calc_dir}")

    fort3 = calc_dir / str(config.parsing.get("fort3_name", "fort.3"))
    fort16 = calc_dir / str(config.parsing.get("fort16_name", "fort.16"))
    channel = channel_for_state_file(fort16, state_file)
    beam_energy = beam_energy_for_channel(fort3, channel)

    if args.input is None:
        fresco_input = choose_fresco_input(calc_dir)
    else:
        fresco_input = resolve_repo_path(args.input, config.repo)
        if not fresco_input.is_file():
            raise FileNotFoundError(f"FRESCOX input not found: {fresco_input}")

    exp_path = (
        experimental_path(config, reaction, args.state)
        if args.exp is None
        else resolve_repo_path(args.exp, config.repo)
    )
    points = load_experimental_points(
        exp_path,
        theta_min=args.theta_min,
        theta_max=args.theta_max,
    )

    all_cfps = numbered_cfps_from_fort3(fort3)
    validate_input_cfp_order(fresco_input, all_cfps)
    candidates = relevant_cfps(all_cfps, channel)
    selected = _select_cfp(all_cfps, candidates, args.cfp)
    minuit_step = (
        args.step
        if args.step is not None
        else max(abs(selected.info.amplitude) * 0.01, 0.01)
    )

    fit_dir = (
        calc_dir / "sfresco_fit" / f"{Path(state_file).stem}_cfp{selected.number}"
        if args.fit_dir is None
        else resolve_repo_path(args.fit_dir, config.repo)
    )
    fit_dir.mkdir(parents=True, exist_ok=True)

    local_input = fit_dir / fresco_input.name
    if fresco_input.resolve() != local_input.resolve():
        shutil.copy2(fresco_input, local_input)

    search_file = fit_dir / "search.in"
    scan_command_file = fit_dir / "sfrescox_scan.commands"
    scan_log = fit_dir / "sfrescox_scan.log"
    command_file = fit_dir / "sfrescox.commands"
    sfresco_log = fit_dir / "sfrescox.log"
    search_plot = fit_dir / "search.plot"
    sfresco_output = fit_dir / "sfresco_fit.out"

    write_search_file(
        search_file,
        fresco_input=local_input.name,
        fresco_output=sfresco_output.name,
        cfp=selected,
        points=points,
        partition=channel.partition,
        excitation=channel.excitation,
        step=minuit_step,
        valmin=args.valmin,
        valmax=args.valmax,
        lab=args.lab,
        iscale=args.iscale,
        energy=beam_energy,
    )

    print(f"[repo]       {config.repo}")
    print(f"[config]     {config.source}")
    print(f"[reaction]   {reaction.key}")
    print(f"[model]      {model_key}")
    print(f"[state]      {args.state} keV")
    print(f"[state-file] {state_file}")
    print(f"[channel]    partition={channel.partition} state={channel.excitation}")
    print(f"[input]      {fresco_input}")
    print(f"[fort.3]     {fort3}")
    print(f"[fort.16]    {fort16}")
    print(f"[experiment] {exp_path} ({len(points)} point(s))")
    print(f"[energy]     {beam_energy:g} MeV lab")
    print(f"[vary]       {selected.short_label()}")
    print(f"[sfrescox]   {args.sfresco_exe}")
    print(f"[frescox]    {args.fresco_exe}")
    print(f"[fit-dir]    {fit_dir}")
    print(f"[search]     {search_file}")

    if args.fit_method == "scan" and args.no_scan:
        raise ValueError("--no-scan cannot be used with --fit-method scan")
    if args.refine_factor < 2:
        raise ValueError("--refine-factor must be at least 2")
    if args.delta_chisq <= 0.0:
        raise ValueError("--delta-chisq must be positive")
    if args.band_samples < 3:
        raise ValueError("--band-samples must be at least 3")

    show_progress = not args.quiet_progress
    scan_best = None
    scan_estimate = None
    start_amplitude = selected.info.amplitude
    scan_points = []
    fit_points = []
    profile_points = []
    profile_interval = None
    chi2_profile_csv = None
    chi2_profile_plot = None
    sigma_low_local = sigma_high_local = None
    sigma_low_published = sigma_high_published = None
    uncertainty_band_method = None
    amplitude_scaling_check = None
    scan_min = scan_max = scan_step = None

    if not args.no_scan:
        scan_min, scan_max, scan_step = automatic_scan_range(
            selected.info.amplitude,
            scan_min=args.scan_min,
            scan_max=args.scan_max,
            scan_step=args.scan_step,
            valmin=args.valmin,
            valmax=args.valmax,
        )
        write_scan_command_file(
            scan_command_file,
            search_file=search_file.name,
            variable_number=1,
            scan_min=scan_min,
            scan_max=scan_max,
            scan_step=scan_step,
        )
        print(
            f"[scan]       A={scan_min:g}..{scan_max:g} step={scan_step:g} "
            f"({scan_command_file.name})"
        )
    else:
        print("[scan]       disabled (--no-scan)")

    print(f"[fit-method] {args.fit_method}")
    if args.fit_method == "scan":
        print(
            f"[refine]     {'disabled' if args.no_refine else f'factor={args.refine_factor}'}"
        )
    else:
        print(f"[minuit-step] {minuit_step:g}")

    if args.prepare_only:
        if args.fit_method == "scan":
            write_final_scan_command_file(
                command_file,
                search_file=search_file.name,
                plot_file=search_plot.name,
                amplitude=start_amplitude,
            )
        else:
            write_command_file(
                command_file,
                search_file=search_file.name,
                plot_file=search_plot.name,
                initial_value=start_amplitude,
            )
        print("[prepared] Validation/search generation succeeded; --prepare-only requested.")
        return

    if not args.no_scan:
        assert scan_min is not None and scan_max is not None and scan_step is not None
        coarse_expected = scan_point_count(scan_min, scan_max, scan_step)
        run_sfrescox(
            executable=args.sfresco_exe,
            command_file=scan_command_file,
            cwd=fit_dir,
            log_file=scan_log,
            timeout=args.timeout,
            stage="coarse-scan",
            expected_scan_points=coarse_expected,
            show_progress=show_progress,
            verbose=args.verbose_subprocess,
        )
        coarse_text = scan_log.read_text(encoding="utf-8", errors="replace")
        scan_points = parse_scan_results(coarse_text)
        scan_best = best_scan_point(coarse_text)
        start_amplitude = scan_best.amplitude
        print(
            f"[scan-best]  A={scan_best.amplitude:.8g}, "
            f"ChiSq/dof={scan_best.reduced_chisq:.6g}"
        )

    if args.fit_method == "scan":
        fit_points = list(scan_points)
        if not args.no_refine:
            refine_min, refine_max, refine_step = refinement_scan_range(
                scan_points,
                factor=args.refine_factor,
            )
            refine_command_file = fit_dir / "sfrescox_refine.commands"
            refine_log = fit_dir / "sfrescox_refine.log"
            write_scan_command_file(
                refine_command_file,
                search_file=search_file.name,
                variable_number=1,
                scan_min=refine_min,
                scan_max=refine_max,
                scan_step=refine_step,
            )
            refine_expected = scan_point_count(refine_min, refine_max, refine_step)
            print(
                f"[refine]     A={refine_min:g}..{refine_max:g} step={refine_step:g} "
                f"({refine_expected} point(s))"
            )
            run_sfrescox(
                executable=args.sfresco_exe,
                command_file=refine_command_file,
                cwd=fit_dir,
                log_file=refine_log,
                timeout=args.timeout,
                stage="refine-scan",
                expected_scan_points=refine_expected,
                show_progress=show_progress,
                verbose=args.verbose_subprocess,
            )
            fit_points = parse_scan_results(
                refine_log.read_text(encoding="utf-8", errors="replace")
            )

        scan_estimate = parabolic_scan_estimate(
            fit_points,
            dof=len(points) - 1,
        )

        # Combine coarse and refined SFRESCOX evaluations for the profile.
        # The nearest evaluated brackets around the minimum define the
        # Delta-chi-square crossing; the quadratic remains only a diagnostic.
        profile_points = [*scan_points, *fit_points]
        try:
            profile_interval = profile_interval_from_scan(
                profile_points,
                dof=len(points) - 1,
                delta_chisq=args.delta_chisq,
            )
            print(
                f"[1sigma]     A={profile_interval.best_amplitude:.8g} "
                f"-{profile_interval.minus:.3g}/+{profile_interval.plus:.3g} "
                f"(DeltaChiSq={profile_interval.delta_chisq:g})"
            )
        except ValueError as exc:
            print(f"[1sigma]     warning: {exc}")
            profile_interval = None

        chi2_profile_csv = write_chisq_profile_csv(
            fit_dir / "chi2_profile.csv",
            profile_points,
            dof=len(points) - 1,
            interval=profile_interval,
        )
        chi2_profile_plot = plot_chisq_profile(
            fit_dir / "chi2_vs_A.png",
            profile_points,
            dof=len(points) - 1,
            interval=profile_interval,
        )
        print(f"[chi2-profile] {chi2_profile_csv}")
        print(f"[chi2-plot]    {chi2_profile_plot}")

        # The published fit must be an amplitude that SFRESCOX actually
        # evaluated.  A local parabola is useful for estimating the curvature
        # and uncertainty, but the FRESCOX objective can show small numerical
        # jitter at sub-grid displacements.  Therefore the discrete refinement
        # minimum is the source of truth for the final card.
        start_amplitude = scan_estimate.discrete_best.amplitude
        err_text = (
            f" +/- {scan_estimate.amplitude_error:.3g}"
            if scan_estimate.amplitude_error is not None
            else ""
        )
        print(
            f"[scan-min]   A={start_amplitude:.8g}, "
            f"ChiSq/dof={scan_estimate.discrete_best.reduced_chisq:.6g} "
            "(evaluated point)"
        )
        print(
            f"[quadratic]  A~{scan_estimate.amplitude:.8g}{err_text}, "
            f"ChiSq/dof~{scan_estimate.reduced_chisq_estimate:.6g} "
            "(uncertainty diagnostic)"
        )

        write_final_scan_command_file(
            command_file,
            search_file=search_file.name,
            plot_file=search_plot.name,
            amplitude=start_amplitude,
        )
        search_plot.unlink(missing_ok=True)
        run_sfrescox(
            executable=args.sfresco_exe,
            command_file=command_file,
            cwd=fit_dir,
            log_file=sfresco_log,
            timeout=args.timeout,
            stage="final-sfrescox",
            expected_scan_points=None,
            show_progress=show_progress,
            verbose=args.verbose_subprocess,
        )
        result = parse_scan_fit_result(
            search_plot,
            log_file=sfresco_log,
            n_points=len(points),
            amplitude_error=scan_estimate.amplitude_error,
        )
        validate_reported_amplitude(start_amplitude, result.amplitude)
    else:
        write_command_file(
            command_file,
            search_file=search_file.name,
            plot_file=search_plot.name,
            initial_value=start_amplitude,
        )
        search_plot.unlink(missing_ok=True)
        run_sfrescox(
            executable=args.sfresco_exe,
            command_file=command_file,
            cwd=fit_dir,
            log_file=sfresco_log,
            timeout=args.timeout,
            stage="migrad",
            expected_scan_points=None,
            show_progress=show_progress,
            verbose=args.verbose_subprocess,
        )
        result = parse_fit_result(
            search_plot,
            log_file=sfresco_log,
            n_points=len(points),
        )


    # For scan fitting, ``start_amplitude`` is the exact evaluated refinement
    # minimum and is the single source of truth for both the final SFRESCOX
    # verification and the standalone best-fit FRESCOX card.
    final_amplitude = start_amplitude if result.method == "scan" else result.amplitude
    best_input = write_best_fit_input(
        local_input,
        fit_dir / f"bestfit_{fresco_input.name}",
        cfp_number=selected.number,
        amplitude=final_amplitude,
    )

    local_curve: Path | None = None
    published_curve: Path | None = None
    fresco_log: Path | None = None
    curve_validation = None

    if not args.no_final_run:
        fresco_log = fit_dir / "bestfit_frescox.out"
        run_frescox(
            executable=args.fresco_exe,
            input_file=best_input,
            cwd=fit_dir,
            log_file=fresco_log,
            timeout=args.timeout,
            show_progress=show_progress,
            verbose=args.verbose_subprocess,
        )

        output_directory = str(config.parsing.get("output_directory", "fresco_dists"))
        publish_dir = calc_dir / output_directory
        # Split into the isolated fit directory first, calculate an independent
        # chi-square against the exact final FRESCOX curve, and only publish if
        # that cross-check agrees with SFRESCOX's own CHI result.
        local_curve, generated_publish_curve = split_and_publish_best_curve(
            fit_dir=fit_dir,
            state_file=state_file,
            publish_dir=publish_dir,
            publish_name=args.publish_name,
        )
        curve_validation = calculate_curve_chisq(points, local_curve)
        try:
            chi2_relative_difference = validate_curve_chisq(result, curve_validation)
        except Exception:
            generated_publish_curve.unlink(missing_ok=True)
            raise
        print(
            f"[chi2-check] SFRESCOX={result.sfresco_chisq:.6g}, "
            f"final FRESCOX/JCEfresco={curve_validation.chisq:.6g}, "
            f"difference={100.0 * chi2_relative_difference:.2f}%"
        )
        if chi2_relative_difference > 0.02:
            print(
                "[chi2-check] warning: small numerical disagreement exceeds 2%; "
                "the standalone final FRESCOX curve is retained as the published "
                "artifact. A disagreement above 10% is treated as fatal."
            )
        if args.no_publish:
            generated_publish_curve.unlink(missing_ok=True)
        else:
            published_curve = generated_publish_curve

        if profile_interval is not None and not args.no_uncertainty_band:
            output_directory = str(
                config.parsing.get("output_directory", "fresco_dists")
            )
            local_band_dir = fit_dir / "fresco_dists"
            local_band_dir.mkdir(parents=True, exist_ok=True)
            stem = Path(state_file).stem
            sigma_low_local = (
                local_band_dir / f"{stem}_sfresco_1sigma_low.txt"
            )
            sigma_high_local = (
                local_band_dir / f"{stem}_sfresco_1sigma_high.txt"
            )

            # For a single isolated transfer amplitude, the angular
            # distribution must obey sigma(theta;A) proportional to A^2.  In
            # auto/scale mode we *verify* that behavior from two independent
            # FRESCOX calculations before constructing a constant-fractional
            # band from the exact best-fit curve.
            original_curve = calc_dir / output_directory / Path(state_file).name
            if args.band_propagation in {"auto", "scale"}:
                if original_curve.is_file():
                    amplitude_scaling_check = validate_amplitude_squared_scaling(
                        original_curve,
                        local_curve,
                        reference_amplitude=selected.info.amplitude,
                        best_amplitude=final_amplitude,
                    )
                    print(
                        f"[band-check] sigma~A^2: "
                        f"rms={100.0 * amplitude_scaling_check.rms_relative_difference:.3f}% "
                        f"max={100.0 * amplitude_scaling_check.max_relative_difference:.3f}% "
                        f"-> {'PASS' if amplitude_scaling_check.passed else 'FAIL'}"
                    )
                else:
                    print(
                        f"[band-check] original parsed curve not found: "
                        f"{original_curve}"
                    )

                if (
                    amplitude_scaling_check is not None
                    and amplitude_scaling_check.passed
                ):
                    write_scaled_amplitude_band(
                        local_curve,
                        sigma_low_local,
                        sigma_high_local,
                        best_amplitude=final_amplitude,
                        lower_amplitude=profile_interval.lower_amplitude,
                        upper_amplitude=profile_interval.upper_amplitude,
                    )
                    uncertainty_band_method = "A2-scale"
                    print(
                        "[1sigma-band] analytic A^2 propagation from exact "
                        "best-fit curve; no extra FRESCOX runs"
                    )
                elif args.band_propagation == "scale":
                    raise RuntimeError(
                        "--band-propagation scale requested, but the original "
                        "and best-fit curves do not validate sigma proportional "
                        "to A^2. Use auto or sampled."
                    )

            # If changing A alters the shape (for example through interference),
            # sample the full allowed profile interval with real FRESCOX runs
            # and project that 1D parameter interval into a pointwise envelope.
            # The exact best-fit curve is included explicitly, so the band can
            # never exclude the best-fit prediction.
            if uncertainty_band_method is None:
                uncertainty_band_method = "sampled-envelope"
                lower = profile_interval.lower_amplitude
                upper = profile_interval.upper_amplitude
                sample_values = [
                    lower
                    + index * (upper - lower) / (args.band_samples - 1)
                    for index in range(args.band_samples)
                ]
                sample_values.append(final_amplitude)
                sample_values = sorted(
                    set(round(value, 12) for value in sample_values)
                )
                sampled_curves = [local_curve]
                values_to_run = [
                    value
                    for value in sample_values
                    if abs(value - final_amplitude) > 1.0e-10
                ]
                print(
                    f"[1sigma-band] sampled FRESCOX envelope with "
                    f"{len(sample_values)} amplitude point(s) over "
                    f"[{lower:.8g}, {upper:.8g}]"
                )
                for index, amplitude in enumerate(values_to_run, start=1):
                    _, _, sampled_curve = run_frescox_curve_at_amplitude(
                        source_input=local_input,
                        cfp_number=selected.number,
                        amplitude=amplitude,
                        run_dir=(
                            fit_dir
                            / "sigma_samples"
                            / f"sample_{index:02d}"
                        ),
                        state_file=state_file,
                        executable=args.fresco_exe,
                        timeout=args.timeout,
                        show_progress=show_progress,
                        verbose=args.verbose_subprocess,
                        stage_label=f"band-{index:02d}-of-{len(values_to_run):02d}",
                    )
                    sampled_curves.append(sampled_curve)

                write_curve_envelope(
                    sampled_curves,
                    sigma_low_local,
                    sigma_high_local,
                    reference_curve=local_curve,
                )

            if not args.no_publish:
                publish_dir = calc_dir / output_directory
                publish_dir.mkdir(parents=True, exist_ok=True)
                sigma_low_published = (
                    publish_dir / f"{stem}_sfresco_1sigma_low.txt"
                )
                sigma_high_published = (
                    publish_dir / f"{stem}_sfresco_1sigma_high.txt"
                )
                shutil.copy2(sigma_low_local, sigma_low_published)
                shutil.copy2(sigma_high_local, sigma_high_published)
                print(f"[1sigma-band] method={uncertainty_band_method}")
                print(f"[1sigma-band] low  -> {sigma_low_published}")
                print(f"[1sigma-band] high -> {sigma_high_published}")

    summary_json = write_summary_json(
        fit_dir / "fit_summary.json",
        result=result,
        selected_cfp=selected,
        reaction=reaction.key,
        model=model_key,
        state_keV=args.state,
        state_file=state_file,
        experimental_file=exp_path,
        published_curve=published_curve,
        sfresco_executable=args.sfresco_exe,
        fresco_executable=args.fresco_exe,
        scan_best=scan_best,
        curve_validation=curve_validation,
        profile_interval=profile_interval,
        chi2_profile_csv=chi2_profile_csv,
        chi2_profile_plot=chi2_profile_plot,
        sigma_low_curve=sigma_low_published or sigma_low_local,
        sigma_high_curve=sigma_high_published or sigma_high_local,
        uncertainty_band_method=uncertainty_band_method,
        amplitude_scaling_check=amplitude_scaling_check,
    )

    print("\n" + "=" * 72)
    print(" JCEFRESCO / SFRESCOX SPECTROSCOPIC-AMPLITUDE FIT")
    print("=" * 72)
    print(f" CFP (nafrac)          : {selected.number}")
    print(f" Initial amplitude A   : {selected.info.amplitude:.8g}")
    if result.method == "scan" or result.amplitude_error is None:
        print(f" Best amplitude A      : {result.amplitude:.8g}")
    else:
        print(f" Best amplitude A      : {result.amplitude:.8g} +/- {result.amplitude_error:.3g}")
    if result.method == "scan" or result.spectroscopic_factor_error is None:
        print(f" A^2                   : {result.spectroscopic_factor:.8g}")
    else:
        print(
            f" A^2                   : {result.spectroscopic_factor:.8g} "
            f"+/- {result.spectroscopic_factor_error:.3g}"
        )
    print(f" Experimental points   : {result.n_points}")
    print(f" Degrees of freedom    : {result.dof}")
    if result.method == "migrad":
        print(" Fit method            : MINUIT/MIGRAD (converged)")
    else:
        print(" Fit method            : SFRESCOX profile scan (evaluated minimum)")
    if scan_best is not None:
        print(
            f" Coarse-scan seed      : A={scan_best.amplitude:.8g}, "
            f"ChiSq/dof={scan_best.reduced_chisq:.6g}"
        )
    if scan_estimate is not None:
        print(
            f" Quadratic diagnostic  : A~{scan_estimate.amplitude:.8g}, "
            f"ChiSq/dof~{scan_estimate.reduced_chisq_estimate:.6g}"
        )
    if profile_interval is not None:
        print(
            f" Profile 1sigma A      : {profile_interval.best_amplitude:.8g} "
            f"-{profile_interval.minus:.3g}/+{profile_interval.plus:.3g}"
        )
        print(f" DeltaChiSq threshold  : {profile_interval.delta_chisq:g}")
    if result.sfresco_chisq is not None:
        print(f" SFRESCOX ChiSq        : {result.sfresco_chisq:.6g}")
    if result.sfresco_reduced_chisq is not None:
        print(f" SFRESCOX ChiSq/dof    : {result.sfresco_reduced_chisq:.6g}")
    if curve_validation is not None:
        print(f" JCEfresco ChiSq check : {curve_validation.chisq:.6g}")
        print(f" JCEfresco ChiSq/dof   : {curve_validation.reduced_chisq:.6g}")
    print(f" Best-fit input        : {best_input}")
    print(f" search.plot           : {search_plot}")
    print(f" SFRESCOX log          : {sfresco_log}")
    if fresco_log is not None:
        print(f" Final FRESCOX log     : {fresco_log}")
    if local_curve is not None:
        print(f" Best-fit local curve  : {local_curve}")
    if published_curve is not None:
        print(f" plot.py curve         : {published_curve}")
    if chi2_profile_csv is not None:
        print(f" ChiSq profile CSV     : {chi2_profile_csv}")
    if chi2_profile_plot is not None:
        print(f" ChiSq vs A plot       : {chi2_profile_plot}")
    if sigma_low_published is not None and sigma_high_published is not None:
        print(f" 1sigma band method    : {uncertainty_band_method}")
        print(f" 1sigma lower curve    : {sigma_low_published}")
        print(f" 1sigma upper curve    : {sigma_high_published}")
    print(f" Summary JSON          : {summary_json}")
    print("=" * 72)

    if published_curve is not None:
        print("\n[plot-next]")
        print(
            _plot_command(
                reaction=reaction.key,
                state_keV=args.state,
                model=model_key,
                original_state_file=state_file,
                published_name=published_curve.name,
                theta_max=args.theta_max,
                sigma_low_name=sigma_low_published.name if sigma_low_published is not None else None,
                sigma_high_name=sigma_high_published.name if sigma_high_published is not None else None,
            )
        )
        print("\n")


if __name__ == "__main__":
    main()
