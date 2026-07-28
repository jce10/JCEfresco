from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from ..config import ProjectConfig
from ..reactions import ReactionConfig, model_directory, normalize_model
from .fort16 import split_fort16
from .fro import extract_cross_section_map


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


def choose_fro_file(state_dir: Path, pattern: str) -> Path | None:
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
    overwrite: bool,
    skip_map: bool,
    dry_run: bool,
) -> bool:
    parsing = config.parsing
    fort16_name = str(parsing.get("fort16_name", "fort.16"))
    fro_glob = str(parsing.get("fro_glob", "*.fro"))
    output_name = str(parsing.get("output_directory", "fresco_dists"))

    fort16 = state_dir / fort16_name
    output_dir = state_dir / output_name

    if not fort16.is_file():
        print(f"[skip] {state_dir}: missing {fort16_name}")
        return False

    if output_dir.exists() and not overwrite:
        print(f"[skip] {state_dir}: {output_name}/ already exists; use --overwrite")
        return False

    fro_file = None if skip_map else choose_fro_file(state_dir, fro_glob)

    if dry_run:
        print(f"[dry-run] split {fort16} -> {output_dir}")
        if not skip_map:
            print(f"[dry-run] map   {fro_file or '[no .fro found]'}")
        return True

    if output_dir.exists():
        shutil.rmtree(output_dir)

    split_fort16(fort16, output_dir)
    if not skip_map:
        if fro_file is None:
            print(f"[warn] {state_dir}: no file matched {fro_glob!r}; map not written")
        else:
            extract_cross_section_map(fro_file, output_dir / "cross_section_map.txt")

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
        root = model_directory(config, reaction.models[model_key])
        print(f"\n[model] {reaction.key}/{model_key}: {root}")

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
