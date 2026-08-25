from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from ..config import ProjectConfig
from ..reactions import ReactionConfig, model_directory, normalize_model
from .fort16 import split_fort16
from .fro import extract_cross_section_map
from .xsec_map_parser import build_cross_section_map


STATE_DIRECTORY_PATTERN = re.compile(r"^(?P<energy>\d+)keV$", re.IGNORECASE)


@dataclass
class BatchSummary:
    processed: int = 0
    skipped: int = 0
    failed: int = 0


def state_sort_key(path: Path) -> tuple[int, str]:
    match = STATE_DIRECTORY_PATTERN.match(path.name)
    return (int(match.group("energy")) if match else 10**12, path.name)


def state_energy(path: Path) -> int | None:
    match = STATE_DIRECTORY_PATTERN.match(path.name)
    return int(match.group("energy")) if match else None


def choose_output_file(state_dir: Path, pattern: str) -> Path | None:
    matches = sorted(path for path in state_dir.glob(pattern) if path.is_file())
    if not matches:
        return None
    if len(matches) > 1:
        print(
            f"[warn] {state_dir}: found {len(matches)} files matching {pattern!r}; "
            f"using {matches[0].name}"
        )
    return matches[0]


def process_state_directory(
    state_dir: Path,
    config: ProjectConfig,
    *,
    output_glob: str | None = None,
    overwrite: bool,
    skip_map: bool,
    dry_run: bool,
) -> bool:
    parsing = config.parsing
    fort3_name = str(parsing.get("fort3_name", "fort.3"))
    fort13_name = str(parsing.get("fort13_name", "fort.13"))
    fort16_name = str(parsing.get("fort16_name", "fort.16"))

    if output_glob is None:
        # Backward-compatible fallback: prefer the new generic name, then the
        # old fro_glob setting, then default to standard FRESCO .fro output.
        output_glob = str(
            parsing.get("output_glob", parsing.get("fro_glob", "*.fro"))
        )
    output_name = str(parsing.get("output_directory", "fresco_dists"))

    fort16 = state_dir / fort16_name
    output_dir = state_dir / output_name

    if not fort16.is_file():
        print(f"[skip] {state_dir}: missing {fort16_name}")
        return False

    if output_dir.exists() and not overwrite:
        print(f"[skip] {state_dir}: {output_name}/ already exists; use --overwrite")
        return False

    output_file = None if skip_map else choose_output_file(state_dir, output_glob)

    if dry_run:
        print(f"[dry-run] split      {fort16} -> {output_dir}")
        if not skip_map:
            print(
                f"[dry-run] xsec map   {state_dir / fort3_name}, "
                f"{state_dir / fort13_name}, {fort16}"
            )
            print(
                f"[dry-run] output map "
                f"{output_file or f'[no file matched {output_glob!r}]'}"
            )
        return True

    if output_dir.exists():
        shutil.rmtree(output_dir)

    split_fort16(fort16, output_dir)

    if not skip_map:
        # Primary physics-focused map:
        #   fort.3  -> input/bookkeeping
        #   fort.13 -> integrated cross sections
        #   fort.16 -> curve/state mapping
        try:
            build_cross_section_map(
                state_dir,
                (output_dir / "xsec_map.txt").resolve(),
                fort3_name=fort3_name,
                fort13_name=fort13_name,
                fort16_name=fort16_name,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"[warn] {state_dir}: xsec_map.txt not written: {exc}")

        # Keep the original .fro/.out-driven summary as a secondary diagnostic
        # while the new mapper is being validated.
        if output_file is None:
            print(
                f"[warn] {state_dir}: no file matched {output_glob!r}; "
                "output_map.txt not written"
            )
        else:
            try:
                extract_cross_section_map(
                    output_file,
                    output_dir / "output_map.txt",
                )
            except (FileNotFoundError, ValueError) as exc:
                print(f"[warn] {state_dir}: output_map.txt not written: {exc}")

    return True


def split_reaction(
    config: ProjectConfig,
    reaction: ReactionConfig,
    *,
    models: list[str] | None = None,
    states: set[int] | None = None,
    overwrite: bool = False,
    skip_map: bool = False,
    dry_run: bool = False,
    keep_going: bool = False,
) -> BatchSummary:
    """Split all configured calculation directories for one reaction."""
    selected = models or list(reaction.models)
    selected = [normalize_model(config, reaction, model) for model in selected]
    state_glob = str(config.parsing.get("state_directory_glob", "*keV"))
    summary = BatchSummary()

    for model_key in selected:
        model = reaction.models[model_key]
        root = model_directory(config, model)

        # Allow an individual model to override the output-file pattern, e.g.
        # output_glob: "*.out" for namelist Frescox calculations.  Reading the
        # raw model mapping here keeps this feature local to the batch parser and
        # avoids requiring output_glob to become part of ModelConfig.
        raw_model = config.reactions[reaction.key]["models"][model_key]
        output_glob = str(
            raw_model.get(
                "output_glob",
                config.parsing.get(
                    "output_glob", config.parsing.get("fro_glob", "*.fro")
                ),
            )
        )

        print(f"\n[model] {reaction.key}/{model_key}: {root}")
        print(f"[output] {output_glob}")

        if not root.is_dir():
            print("[skip] model directory does not exist")
            summary.skipped += 1
            continue

        state_dirs = sorted(
            (path for path in root.glob(state_glob) if path.is_dir()),
            key=state_sort_key,
        )
        if states is not None:
            state_dirs = [path for path in state_dirs if state_energy(path) in states]

        if not state_dirs:
            print(f"[skip] no state directories matched {state_glob!r}")
            summary.skipped += 1
            continue

        for state_dir in state_dirs:
            try:
                changed = process_state_directory(
                    state_dir,
                    config,
                    output_glob=output_glob,
                    overwrite=overwrite,
                    skip_map=skip_map,
                    dry_run=dry_run,
                )
                if changed:
                    summary.processed += 1
                else:
                    summary.skipped += 1
            except Exception as exc:
                summary.failed += 1
                print(f"[error] {state_dir}: {exc}")
                if not keep_going:
                    raise

    return summary
