from __future__ import annotations

from pathlib import Path


def find_repo_root(start: str | Path | None = None) -> Path:
    """Find the nearest parent containing ``pyproject.toml``."""
    candidate = Path(start).expanduser().resolve() if start else Path(__file__).resolve()
    directories = [candidate] if candidate.is_dir() else list(candidate.parents)

    for directory in directories:
        if (directory / "pyproject.toml").is_file():
            return directory

    raise FileNotFoundError(
        "Could not find the JCEfresco repository root containing pyproject.toml. "
        "Pass --repo /path/to/JCEfresco if running outside the repository."
    )


def resolve_repo_path(path: str | Path, repo: Path) -> Path:
    """Resolve an absolute path or a path relative to the repository root."""
    candidate = Path(path).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (repo / candidate).resolve()
