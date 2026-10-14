"""The dashboard builds, renders every figure, and reproduces the paper's headline numbers."""

import hashlib
import warnings

import pytest
from vizro import Vizro
from vizro.managers import model_manager

import app

# The SHA-256 of each file as committed at the paper repository's pinned commit (data/SOURCE.md).
PINNED = {
    "population_cells.csv": "742fe431e36c75ed44e071c9e013ee8566c806c4143e4bfa1115537366bdf8f1",
    "company_classification.csv": "0483e7104c37107fe49c2683a203cbfb51453e5b30553f30c0a930d7d071b6a1",
    "ipo_validation.csv": "4f64c6a1c6dda8c07f62ec1b095964f6ea351897a245455765cc1e1c35bca37a",
}


@pytest.fixture
def dashboard():
    Vizro._reset()
    yield app.build_dashboard()
    Vizro._reset()


@pytest.mark.parametrize("name", sorted(PINNED))
def test_data_is_the_pinned_copy(name):
    assert hashlib.sha256((app.DATA / name).read_bytes()).hexdigest() == PINNED[name]


def test_builds_without_deprecated_vizro_api(dashboard):
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        warnings.simplefilter("error", DeprecationWarning)
        Vizro().build(dashboard)


def test_every_figure_renders(dashboard):
    Vizro().build(dashboard)
    figures = [model for model in model_manager._get_models() if hasattr(model, "figure")]
    assert figures
    for model in figures:
        model()


def test_population_numbers_match_the_paper():
    cells = app.load_cells()
    assert len(cells) == 4271
    assert cells.company.nunique() == 656
    assert round(cells.spread_pct.median(), 1) == 12.1
    assert round(cells.unanimous.mean() * 100, 1) == 17.0
    assert round(cells.wide.mean() * 100, 1) == 40.2
    assert round(cells.nav_wide_bn.sum(), 1) == 180.0
    assert round(cells.nav_bn.sum(), 1) == 517.3


def test_venture_numbers_match_the_paper():
    venture = app.load_cells().query("company_class == 'Venture-backed'")
    assert len(venture) == 2113
    assert round(venture.spread_pct.median(), 1) == 10.1
    assert round(venture.wide.mean() * 100, 1) == 37.0
    assert round(venture.nav_bn.sum(), 1) == 402.2
    assert round(venture.nav_wide_bn.sum(), 1) == 152.8


def test_exit_numbers_match_the_paper():
    exits = app.load_exits()
    fund_held = exits[exits.signal == "Fund mark"]
    assert len(fund_held) == 7
    assert (fund_held.least_wrong == "Fund mark").sum() == 5
    assert round(fund_held.signal_err_pct.abs().median()) == 11
    assert round(fund_held.headline_err_pct.abs().median()) == 48
    instacart = exits.set_index("company").loc["Instacart"]
    assert (round(instacart.signal_err_pct), round(instacart.headline_err_pct)) == (8, 294)
