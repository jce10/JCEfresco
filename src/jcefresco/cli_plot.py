from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from .config import load_config
from .plotting import FrescoCurve, plot_angular_distribution
from .reactions import experimental_path, get_reaction, normalize_model
from .utils.repo import resolve_repo_path


def parse_key_value_floats(items: Iterable[str] | None) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in items or []:
        key, value = item.split("=", maxsplit=1)
        result[key.strip().lower()] = float(value)
    return result


def parse_key_value_strings(items: Iterable[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items or []:
        key, value = item.split("=", maxsplit=1)
        result[key.strip().lower()] = value.strip()
    return result


def parse_curve_spec(
    spec: str,
    *,
    config,
    reaction,
    state_keV: int,
) -> FrescoCurve:
    """Parse MODEL:STATE_FILE[:SCALE[:LABEL]] into one FRESCO curve."""
    parts = spec.split(":", maxsplit=3)
    if len(parts) < 2:
        raise ValueError(
            f"Invalid --curve value {spec!r}. Expected "
            "MODEL:STATE_FILE[:SCALE[:LABEL]]."
        )

    model = normalize_model(config, reaction, parts[0])
    state_file = parts[1].strip()
    if not state_file:
        raise ValueError(f"Invalid --curve value {spec!r}: STATE_FILE is empty")

    scale = 1.0
    if len(parts) >= 3 and parts[2].strip():
        scale = float(parts[2])

    label = None
    if len(parts) == 4 and parts[3].strip():
        label = parts[3].strip()

    return FrescoCurve(
        model=model,
        state_keV=state_keV,
        state_file=state_file,
        scale=scale,
        label=label,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plot experimental angular distributions with parsed FRESCO curves."
    )
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--reaction", required=True)
    parser.add_argument("--state", type=int, required=True)
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument(
        "--curve",
        action="append",
        default=None,
        metavar="MODEL:STATE_FILE[:SCALE[:LABEL]]",
        help=(
            "Add one explicit FRESCO curve. Repeat this option to plot multiple "
            "state*.txt files from the same model calculation. Example: "
            "--curve 'cc:state1.txt:1.0:0d5/2'."
        ),
    )
    parser.add_argument("--scales", nargs="*", default=None)
    parser.add_argument("--labels", nargs="*", default=None)
    parser.add_argument("--state-files", nargs="*", default=None)
    parser.add_argument("--exp", nargs="*", default=None)
    parser.add_argument("--no-exp", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--title", default=None)
    parser.add_argument("--linear-y", action="store_true")
    parser.add_argument("--thin", type=int, default=3)
    parser.add_argument("--theta-max", type=float, default=None)
    parser.add_argument("--x-min", type=float, default=None)
    parser.add_argument("--x-max", type=float, default=None)
    parser.add_argument("--y-min", type=float, default=None)
    parser.add_argument("--y-max", type=float, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config, repo=args.repo)
    reaction = get_reaction(config, args.reaction)

    if args.curve:
        conflicting = {
            "--models": args.models,
            "--scales": args.scales,
            "--labels": args.labels,
            "--state-files": args.state_files,
        }
        used = [name for name, value in conflicting.items() if value is not None]
        if used:
            raise ValueError(
                "--curve cannot be combined with " + ", ".join(used) + ". "
                "Describe every requested curve with a separate --curve option."
            )

        curves = [
            parse_curve_spec(
                spec,
                config=config,
                reaction=reaction,
                state_keV=args.state,
            )
            for spec in args.curve
        ]
        models = [curve.model for curve in curves]
    else:
        requested_models = args.models or list(reaction.models)
        models = [normalize_model(config, reaction, model) for model in requested_models]
        scales = parse_key_value_floats(args.scales)
        labels = parse_key_value_strings(args.labels)
        state_files = parse_key_value_strings(args.state_files)

        curves = [
            FrescoCurve(
                model=model,
                state_keV=args.state,
                scale=scales.get(model, 1.0),
                label=labels.get(model),
                state_file=state_files.get(model),
            )
            for model in models
        ]

    if args.no_exp:
        exp_paths: list[Path] = []
    elif args.exp is None:
        exp_paths = [experimental_path(config, reaction, args.state)]
    else:
        exp_paths = [resolve_repo_path(path, config.repo) for path in args.exp]

    output = resolve_repo_path(args.out, config.repo) if args.out else None

    print(f"[repo] {config.repo}")
    print(f"[config] {config.source}")
    print(f"[reaction] {reaction.key}")
    print(f"[state] {args.state} keV")
    print(f"[models] {' '.join(models)}")
    for curve in curves:
        print(
            f"[curve] model={curve.model} file={curve.state_file or '(default)'} "
            f"scale={curve.scale:g} label={curve.label or '(default)'}"
        )

    plot_angular_distribution(
        config,
        reaction,
        args.state,
        curves,
        exp_paths,
        output=output,
        title=args.title,
        logy=not args.linear_y,
        thin=args.thin,
        theta_max=args.theta_max,
        x_min=args.x_min,
        x_max=args.x_max,
        y_min=args.y_min,
        y_max=args.y_max,
    )


if __name__ == "__main__":
    main()
