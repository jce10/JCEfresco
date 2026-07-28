from pathlib import Path

from jcefresco.config import load_config
from jcefresco.reactions import get_reaction, normalize_model


def test_load_default_config() -> None:
    repo = Path(__file__).resolve().parents[1]
    config = load_config(repo=repo)
    reaction = get_reaction(config, "9Be6Lid")
    assert reaction.key == "6lid"
    assert normalize_model(config, reaction, "dwba") == "dwba"


def test_repeated_curve_specs() -> None:
    from jcefresco.cli_plot import parse_curve_spec
    from jcefresco.config import load_config
    from jcefresco.reactions import get_reaction

    repo = Path(__file__).resolve().parents[1]
    config = load_config(repo=repo)
    reaction = get_reaction(config, "dp")

    first = parse_curve_spec(
        "cc:state1.txt:1.0:component one",
        config=config,
        reaction=reaction,
        state_keV=6864,
    )
    second = parse_curve_spec(
        "cc:state4.txt:10:component four",
        config=config,
        reaction=reaction,
        state_keV=6864,
    )

    assert first.model == second.model == "cc"
    assert first.state_file == "state1.txt"
    assert second.state_file == "state4.txt"
    assert second.scale == 10.0
    assert second.label == "component four"
    assert second.plot_label() == "component four × 10"
