from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .config import ProjectConfig


@dataclass(frozen=True)
class ModelConfig:
    key: str
    directory: str
    default_state_file: str


@dataclass(frozen=True)
class ReactionConfig:
    key: str
    display: str
    aliases: tuple[str, ...]
    experimental: Mapping[str, str]
    models: Mapping[str, ModelConfig]


def _clean(value: str) -> str:
    return value.strip().lower()


def reaction_alias_map(config: ProjectConfig) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for canonical, raw in config.reactions.items():
        candidates = [canonical, *raw.get("aliases", [])]
        for alias in candidates:
            cleaned = _clean(str(alias))
            previous = aliases.get(cleaned)
            if previous is not None and previous != canonical:
                raise ValueError(
                    f"Reaction alias {alias!r} is assigned to both "
                    f"{previous!r} and {canonical!r}"
                )
            aliases[cleaned] = canonical
    return aliases


def normalize_reaction(config: ProjectConfig, value: str) -> str:
    aliases = reaction_alias_map(config)
    try:
        return aliases[_clean(value)]
    except KeyError as exc:
        allowed = ", ".join(sorted(config.reactions))
        raise ValueError(f"Unknown reaction {value!r}. Configured reactions: {allowed}") from exc


def get_reaction(config: ProjectConfig, value: str) -> ReactionConfig:
    key = normalize_reaction(config, value)
    raw = config.reactions[key]

    raw_models = raw.get("models")
    if not isinstance(raw_models, dict) or not raw_models:
        raise ValueError(f"Reaction {key!r} has no configured models")

    models = {
        _clean(model_key): ModelConfig(
            key=_clean(model_key),
            directory=str(model_raw["directory"]),
            default_state_file=str(model_raw.get("default_state_file", "state1.txt")),
        )
        for model_key, model_raw in raw_models.items()
    }

    return ReactionConfig(
        key=key,
        display=str(raw.get("display", key)),
        aliases=tuple(str(alias) for alias in raw.get("aliases", [])),
        experimental=raw.get("experimental", {}),
        models=models,
    )


def normalize_model(config: ProjectConfig, reaction: ReactionConfig, value: str) -> str:
    cleaned = _clean(value)
    cleaned = _clean(config.model_aliases.get(cleaned, cleaned))
    if cleaned not in reaction.models:
        allowed = ", ".join(sorted(reaction.models))
        raise ValueError(
            f"Model {value!r} is not configured for reaction {reaction.key!r}. "
            f"Configured models: {allowed}"
        )
    return cleaned


def model_directory(config: ProjectConfig, model: ModelConfig) -> Path:
    return config.project_path("workdir") / model.directory


def experimental_path(
    config: ProjectConfig,
    reaction: ReactionConfig,
    state_keV: int,
) -> Path:
    meta = reaction.experimental
    prefix = str(meta.get("prefix", reaction.key))
    template = str(meta.get("filename", "{prefix}_{state_keV}keV_ang_dist.csv"))
    filename = template.format(prefix=prefix, state_keV=state_keV, reaction=reaction.key)
    return config.project_path("data") / str(meta.get("subdirectory", reaction.key)) / filename


def parsed_state_path(
    config: ProjectConfig,
    reaction: ReactionConfig,
    model_key: str,
    state_keV: int,
    state_file: str | None = None,
) -> Path:
    model = reaction.models[model_key]
    output_directory = str(config.parsing.get("output_directory", "fresco_dists"))
    filename = state_file or model.default_state_file
    return model_directory(config, model) / f"{state_keV}keV" / output_directory / filename
