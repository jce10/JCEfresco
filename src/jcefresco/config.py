from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .utils.repo import find_repo_root, resolve_repo_path


@dataclass(frozen=True)
class ProjectConfig:
    repo: Path
    source: Path
    raw: Mapping[str, Any]

    @property
    def paths(self) -> Mapping[str, str]:
        return self.raw["paths"]

    @property
    def parsing(self) -> Mapping[str, str]:
        return self.raw["parsing"]

    @property
    def reactions(self) -> Mapping[str, Mapping[str, Any]]:
        return self.raw["reactions"]

    @property
    def model_aliases(self) -> Mapping[str, str]:
        return self.raw.get("models", {}).get("aliases", {})

    def project_path(self, key: str) -> Path:
        try:
            value = self.paths[key]
        except KeyError as exc:
            raise KeyError(f"Missing paths.{key!s} in {self.source}") from exc
        return resolve_repo_path(value, self.repo)


def load_config(
    config_path: str | Path | None = None,
    *,
    repo: str | Path | None = None,
) -> ProjectConfig:
    """Load and minimally validate ``config/config.yaml``."""
    repo_path = Path(repo).expanduser().resolve() if repo else find_repo_root()
    path = (
        resolve_repo_path(config_path, repo_path)
        if config_path is not None
        else repo_path / "config" / "config.yaml"
    )

    if not path.is_file():
        raise FileNotFoundError(f"Could not find configuration file: {path}")

    with path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)

    if not isinstance(raw, dict):
        raise ValueError(f"Configuration must be a YAML mapping: {path}")

    for section in ("paths", "parsing", "reactions"):
        if not isinstance(raw.get(section), dict):
            raise ValueError(f"Missing or invalid {section!r} section in {path}")

    if not raw["reactions"]:
        raise ValueError(f"No reactions are configured in {path}")

    return ProjectConfig(repo=repo_path, source=path, raw=raw)
