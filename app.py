"""A Vizro dashboard over the population panel of "Disagreement Without a Price".

Reads the paper's committed outputs, pinned in `data/SOURCE.md`. Run with `python app.py`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import vizro.models as vm
import vizro.plotly.express as px
from vizro import Vizro
from vizro.figures import kpi_card
from vizro.models.types import capture
from vizro.tables import dash_ag_grid

DATA = Path(__file__).resolve().parent / "data"

PAPER_URL = "https://ssrn.com/abstract=7016178"
REPO_URL = "https://github.com/mkzung/unicorn-valuation-disagreement"

CLASS_NAMES = {
    "venture": "Venture-backed",
    "listed": "Listed",
    "private_nonventure": "Private, not venture",
    "unclassified": "Unclassified",
}

# The paper's Table 11 buckets, from its `src/population.py`.
BUCKET_EDGES = [0.0, 1e-9, 10.0, 24.0, 50.0, 100.0, np.inf]
BUCKET_LABELS = ["identical", "0-10%", "10-24%", "24-50%", "50-100%", ">100%"]

# The paper's reference line: the median spread of its ten broadly held names.
WIDE = 24.0


def load_cells() -> pd.DataFrame:
    """The guarded company-date cells, with each company's class and name."""
    cells = pd.read_csv(DATA / "population_cells.csv", parse_dates=["dt"])
    cells = cells[cells.guarded].copy()
    classes = pd.read_csv(DATA / "company_classification.csv", usecols=["company", "issuer", "label"])
    cells = cells.merge(classes, on="company", how="left", validate="many_to_one")
    cells["company_class"] = cells.label.map(CLASS_NAMES)
    cells["nav_bn"] = cells.nav / 1e9
    cells["unanimous"] = (cells.spread_pct <= 1e-9).astype(float)
    cells["wide"] = (cells.spread_pct > WIDE).astype(float)
    cells["nav_wide_bn"] = cells.nav_bn.where(cells.spread_pct > WIDE, 0.0)
    cells["one"] = 1
    return cells.drop(columns=["guarded", "label"])


def load_companies(cells: pd.DataFrame) -> pd.DataFrame:
    """One row per company cluster."""
    by = cells.sort_values("dt").groupby("company")
    return pd.DataFrame(
        {
            "issuer": by.issuer.first(),
            "company_class": by.company_class.first(),
            "cells": by.size(),
            "first_date": by.dt.min().dt.date,
            "last_date": by.dt.max().dt.date,
            "median_spread_pct": by.spread_pct.median(),
            "widest_spread_pct": by.spread_pct.max(),
            "peak_nav_m": by.nav.max() / 1e6,
            "max_houses": by.n_fams.max(),
        }
    ).reset_index()


def load_exits() -> pd.DataFrame:
    """The ten listings of the paper's §7, scored as its `src/validation.py` does: error = signal / IPO - 1."""
    exits = pd.read_csv(DATA / "ipo_validation.csv")
    exits["headline_err_pct"] = (exits.last_private_val_busd / exits.ipo_val_busd - 1) * 100
    fund_mark = exits.preipo_signal_type == "fund_mark"
    implied = np.where(
        fund_mark, exits.ipo_val_busd * exits.preipo_signal_pps / exits.ipo_pps, exits.preipo_signal_busd
    )
    exits["signal_err_pct"] = (implied / exits.ipo_val_busd - 1) * 100
    exits["signal"] = exits.preipo_signal_type.map({"fund_mark": "Fund mark", "down_round": "Interim round"})
    exits["least_wrong"] = np.where(
        exits.signal_err_pct.notna() & (exits.signal_err_pct.abs() < exits.headline_err_pct.abs()),
        exits.signal,
        np.where(exits.signal_err_pct.notna(), "Headline", "No interim signal"),
    )
    return exits


@capture("graph")
def cells_and_dollars(data_frame: pd.DataFrame) -> go.Figure:
    """Share of company-dates, and of the dollars booked in them, in each spread bucket."""
    bucket = pd.cut(data_frame.spread_pct, BUCKET_EDGES, labels=BUCKET_LABELS, right=False)
    shares = pd.DataFrame(
        {
            "Company-dates": data_frame.groupby(bucket, observed=False).size(),
            "Booked value": data_frame.groupby(bucket, observed=False).nav.sum(),
        }
    )
    shares = shares / shares.sum() * 100
    long = shares.reset_index(names="bucket").melt(id_vars="bucket", var_name="weighted by", value_name="share")
    fig = px.bar(long, x="bucket", y="share", color="weighted by", barmode="group", text_auto=".0f")
    fig.update_layout(xaxis_title="spread between the highest and lowest house mark", yaxis_title="share (%)")
    return fig


@capture("graph")
def spread_over_time(data_frame: pd.DataFrame) -> go.Figure:
    """Median spread in each calendar quarter, against how many company-dates it rests on."""
    # Funds report on different month ends, so single dates hold different companies.
    quarter = data_frame.dt.dt.to_period("Q").dt.start_time
    by_quarter = data_frame.groupby(quarter).agg(median=("spread_pct", "median"), cells=("one", "sum")).reset_index()
    fig = go.Figure()
    fig.add_bar(x=by_quarter.dt, y=by_quarter.cells, name="company-dates", yaxis="y2", opacity=0.35)
    fig.add_scatter(x=by_quarter.dt, y=by_quarter["median"], name="median spread (%)", mode="lines+markers")
    fig.update_layout(
        yaxis={"title": "median spread (%)", "rangemode": "tozero"},
        yaxis2={"title": "company-dates", "overlaying": "y", "side": "right", "showgrid": False},
        legend={"orientation": "h", "y": -0.2},
    )
    return fig


@capture("graph")
def company_map(data_frame: pd.DataFrame) -> go.Figure:
    """Each company cluster's median spread against the most it was booked at, sized by its dates."""
    fig = px.scatter(
        data_frame,
        x="peak_nav_m",
        y="median_spread_pct",
        size="cells",
        size_max=30,
        color="company_class",
        hover_name="issuer",
        log_x=True,
        labels={
            "peak_nav_m": "largest value booked on one date ($M, log)",
            "median_spread_pct": "median spread (%)",
            "company_class": "class",
        },
    )
    fig.update_layout(legend={"orientation": "h", "y": 1.08, "title": None})
    return fig


@capture("graph")
def house_range(data_frame: pd.DataFrame) -> go.Figure:
    """The lowest and highest house mark per share on each report date, for one company."""
    df = data_frame.sort_values("dt")
    fig = go.Figure()
    fig.add_scatter(x=df.dt, y=df.hi, name="highest house mark", mode="lines+markers")
    fig.add_scatter(x=df.dt, y=df.lo, name="lowest house mark", mode="lines+markers", fill="tonexty")
    fig.update_layout(yaxis_title="value per share ($)", legend={"orientation": "h", "y": -0.2})
    return fig


@capture("graph")
def exit_errors(data_frame: pd.DataFrame) -> go.Figure:
    """Each listing's headline error beside its pre-IPO signal's, as a share of the IPO valuation."""
    df = data_frame.sort_values("headline_err_pct")
    fig = go.Figure()
    fig.add_bar(y=df.company, x=df.headline_err_pct, name="last headline round", orientation="h")
    fig.add_bar(y=df.company, x=df.signal_err_pct, name="pre-IPO signal", orientation="h")
    fig.update_layout(
        barmode="group",
        xaxis_title="error against the IPO valuation (%)",
        legend={"orientation": "h", "y": -0.15},
    )
    return fig


def build_dashboard() -> vm.Dashboard:
    cells = load_cells()
    companies = load_companies(cells)
    exits = load_exits()
    fund_held = exits[exits.signal == "Fund mark"].assign(
        fund_mark_least_wrong=lambda d: (d.least_wrong == "Fund mark").astype(int),
        abs_signal_err_pct=lambda d: d.signal_err_pct.abs(),
        abs_headline_err_pct=lambda d: d.headline_err_pct.abs(),
    )

    class_filter = vm.Filter(column="company_class", selector=vm.Checklist(title="Company class"))

    overview = vm.Page(
        title="The population",
        description="Every company-date on which five or more funds from two or more houses report a mark",
        layout=vm.Grid(grid=[[0, 1, 2, 3, 4], [5, 5, 5, 6, 6], [5, 5, 5, 6, 6], [5, 5, 5, 6, 6]]),
        components=[
            vm.Figure(figure=kpi_card(cells, "one", title="Company-dates", value_format="{value:,.0f}")),
            vm.Figure(
                figure=kpi_card(
                    cells, "spread_pct", agg_func="median", title="Median spread", value_format="{value:.1f}%"
                )
            ),
            vm.Figure(
                figure=kpi_card(cells, "unanimous", agg_func="mean", title="Unanimous", value_format="{value:.1%}")
            ),
            vm.Figure(figure=kpi_card(cells, "wide", agg_func="mean", title="Above 24%", value_format="{value:.1%}")),
            vm.Figure(figure=kpi_card(cells, "nav_wide_bn", title="Booked above 24%", value_format="${value:,.1f}B")),
            vm.Graph(
                title="How far apart the houses are",
                figure=cells_and_dollars(cells),
            ),
            vm.Graph(title="Median spread by quarter", figure=spread_over_time(cells)),
        ],
        controls=[
            class_filter,
            vm.Filter(column="dt", selector=vm.DatePicker(title="Report dates")),
            vm.Filter(column="n_fams", selector=vm.Slider(range=True, step=1, title="Independent houses")),
        ],
    )

    company_page = vm.Page(
        title="Companies",
        description="Each company cluster's spread across all its report dates",
        layout=vm.Grid(grid=[[0], [0], [0], [1], [1], [1]]),
        components=[
            vm.Graph(title="Median spread against value booked", figure=company_map(companies)),
            vm.Table(
                figure=dash_ag_grid(
                    companies.drop(columns="company").sort_values("peak_nav_m", ascending=False),
                    columnDefs=[
                        {"field": "issuer", "headerName": "Issuer as filed", "pinned": "left", "minWidth": 280},
                        {"field": "company_class", "headerName": "Class", "minWidth": 150},
                        {"field": "cells", "headerName": "Dates"},
                        {"field": "first_date", "headerName": "From", "minWidth": 120},
                        {"field": "last_date", "headerName": "To", "minWidth": 120},
                        {
                            "field": "median_spread_pct",
                            "headerName": "Median (%)",
                            "valueFormatter": {"function": "d3.format('.1f')(params.value)"},
                        },
                        {
                            "field": "widest_spread_pct",
                            "headerName": "Widest (%)",
                            "valueFormatter": {"function": "d3.format('.1f')(params.value)"},
                        },
                        {
                            "field": "peak_nav_m",
                            "headerName": "Peak booked ($M)",
                            "valueFormatter": {"function": "d3.format(',.1f')(params.value)"},
                        },
                        {"field": "max_houses", "headerName": "Houses"},
                    ],
                    defaultColDef={"flex": 1, "minWidth": 100},
                ),
            ),
        ],
        controls=[
            vm.Filter(column="company_class", selector=vm.Checklist(title="Company class")),
            vm.Filter(column="cells", selector=vm.Slider(range=True, step=1, title="Company-dates")),
        ],
    )

    one_company = vm.Page(
        title="One company",
        description="The lowest and highest house mark, and the spread between them, on each report date",
        layout=vm.Grid(grid=[[0, 1, 2], [3, 3, 3], [3, 3, 3], [4, 4, 4], [4, 4, 4]], row_min_height="150px"),
        components=[
            vm.Figure(figure=kpi_card(cells, "one", title="Company-dates", value_format="{value:,.0f}")),
            vm.Figure(
                figure=kpi_card(
                    cells, "spread_pct", agg_func="median", title="Median spread", value_format="{value:.1f}%"
                )
            ),
            vm.Figure(
                figure=kpi_card(
                    cells, "n_fams", agg_func="max", title="Most houses on one date", value_format="{value}"
                )
            ),
            vm.Graph(title="Lowest and highest house mark", figure=house_range(cells)),
            vm.Graph(
                title="Spread between them",
                figure=px.bar(cells, x="dt", y="spread_pct", labels={"dt": "report date", "spread_pct": "spread (%)"}),
            ),
        ],
        controls=[
            vm.Filter(
                column="issuer",
                selector=vm.Dropdown(multi=False, value="DATABRICKS INC", title="Issuer as filed"),
            ),
        ],
    )

    exits_page = vm.Page(
        title="Marks against IPOs",
        description="Ten 2023-26 listings: was the last headline round or the last fund mark closer to the IPO?",
        layout=vm.Grid(grid=[[0, 1, 2], [3, 3, 3], [3, 3, 3], [3, 3, 3], [4, 4, 4], [4, 4, 4]], row_min_height="150px"),
        components=[
            vm.Figure(
                figure=kpi_card(
                    fund_held, "fund_mark_least_wrong", title="Fund mark least wrong", value_format="{value:.0f} of 7"
                )
            ),
            vm.Figure(
                figure=kpi_card(
                    fund_held,
                    "abs_signal_err_pct",
                    agg_func="median",
                    title="Median fund-mark error",
                    value_format="{value:.0f}%",
                )
            ),
            vm.Figure(
                figure=kpi_card(
                    fund_held,
                    "abs_headline_err_pct",
                    agg_func="median",
                    title="Median headline error",
                    value_format="{value:.0f}%",
                )
            ),
            vm.Graph(title="Error against the IPO valuation", figure=exit_errors(exits)),
            vm.Table(
                figure=dash_ag_grid(
                    exits[
                        [
                            "company",
                            "sector",
                            "ipo_date",
                            "ipo_val_busd",
                            "last_private_val_busd",
                            "headline_err_pct",
                            "signal",
                            "signal_err_pct",
                            "least_wrong",
                            "preipo_signal_source",
                        ]
                    ],
                    columnDefs=[
                        {"field": "company", "headerName": "Company", "pinned": "left", "minWidth": 140},
                        {"field": "sector", "headerName": "Sector"},
                        {"field": "ipo_date", "headerName": "IPO"},
                        {"field": "ipo_val_busd", "headerName": "IPO value ($B)"},
                        {"field": "last_private_val_busd", "headerName": "Headline ($B)"},
                        {
                            "field": "headline_err_pct",
                            "headerName": "Headline error (%)",
                            "valueFormatter": {"function": "d3.format('+.0f')(params.value)"},
                        },
                        {"field": "signal", "headerName": "Pre-IPO signal"},
                        {
                            "field": "signal_err_pct",
                            "headerName": "Signal error (%)",
                            "valueFormatter": {
                                "function": "params.value == null ? '' : d3.format('+.0f')(params.value)"
                            },
                        },
                        {"field": "least_wrong", "headerName": "Least wrong"},
                        {"field": "preipo_signal_source", "headerName": "Source", "minWidth": 400},
                    ],
                    defaultColDef={"flex": 1, "minWidth": 110},
                ),
            ),
        ],
    )

    about = vm.Page(
        title="About",
        components=[
            vm.Text(
                text=f"""
A private company has no price between funding rounds, yet every US fund that holds it reports a
value for it. This dashboard compares what different fund houses report for the same company on
the same date, from the SEC's N-PORT filings, 2019 to 2026.

A company-date is one company on one report date with at least five funds from at least two
independent houses. The spread is how far the highest house mark is above the lowest.

The data are the paper's own outputs. Names are issuer strings as filed; the paper merges a few
split clusters, so it counts 137 venture-backed issuers where the filter shows 142.

[Paper]({PAPER_URL}) · [Code and data]({REPO_URL})
"""
            ),
        ],
    )

    return vm.Dashboard(
        title="Disagreement Without a Price",
        pages=[overview, company_page, one_company, exits_page, about],
        navigation=vm.Navigation(nav_selector=vm.NavBar()),
    )


if __name__ == "__main__":
    Vizro().build(build_dashboard()).run()
