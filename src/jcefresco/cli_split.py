from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .parser import split_reaction
from .reactions import get_reaction


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split fort.16 files and map .fro cross-section sections."
    )
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--reaction", required=True)
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--states", nargs="+", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-map", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config, repo=args.repo)
    reaction = get_reaction(config, args.reaction)

    print(f"[repo] {config.repo}")
    print(f"[config] {config.source}")
    print(f"[reaction] {reaction.key}")

    summary = split_reaction(
        config,
        reaction,
        models=args.models,
        states=set(args.states) if args.states else None,
        overwrite=args.overwrite,
        skip_map=args.skip_map,
        dry_run=args.dry_run,
        keep_going=args.keep_going,
    )
    print(
        f"\n[done] processed={summary.processed} "
        f"skipped={summary.skipped} failed={summary.failed}"
    )


if __name__ == "__main__":
    main()
