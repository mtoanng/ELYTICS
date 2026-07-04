from pathlib import Path
import sys

import pandas as pd

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from spaces.elytics.reporting.data_provider import ElyticsDataProvider
from spaces.elytics.reporting.tabs.standard_reports import _drop_alias_duplicate_columns, _query_columns_for_report
from spaces.elytics.reporting.visualization import rgb_to_rgba

def test_expand_requested_columns_replaces_derived_outputs_with_sources():
    assert ElyticsDataProvider._expand_requested_columns(
        ["Anolyte inlet pressure", "Δp Anolyte", "Stack Voltage"]
    ) == [
        "Anolyte inlet pressure",
        "Anolyte outlet pressure",
        "Stack Voltage",
    ]


def test_expand_requested_columns_canonicalizes_original_aliases():
    assert ElyticsDataProvider._expand_requested_columns(
        ["ΔpGas inlet - Gas outlet", "Stack Voltage"]
    ) == [
        "Δp Gas inlet - Gas outlet",
        "Stack Voltage",
    ]


def test_pivot_timeseries_keeps_rows_with_null_timestamps():
    df = pd.DataFrame(
        [
            {
                "timestamp": None,
                "elapsed_time_s": 60.0,
                "std_channel": "Stack Voltage",
                "value_mean": 14.2,
                "value_min": 14.0,
                "value_max": 14.4,
            },
            {
                "timestamp": None,
                "elapsed_time_s": 120.0,
                "std_channel": "Stack Voltage",
                "value_mean": 14.3,
                "value_min": 14.1,
                "value_max": 14.5,
            },
        ]
    )

    wide = ElyticsDataProvider._pivot_timeseries(df, resolution="agg")

    assert list(wide.columns) == [
        "time",
        "Elapsed time",
        "Stack Voltage_mean",
        "Stack Voltage_min",
        "Stack Voltage_max",
    ]
    assert len(wide) == 2
    assert wide["time"].isna().all()
    assert wide["Elapsed time"].tolist() == [60.0, 120.0]
    assert wide["Stack Voltage_mean"].tolist() == [14.2, 14.3]


def test_pivot_timeseries_falls_back_to_channel_name():
    df = pd.DataFrame(
        [
            {
                "timestamp": "2026-07-03T00:00:00Z",
                "elapsed_time_s": 1.0,
                "std_channel": None,
                "channel_name": "Current density",
                "value": 400.0,
            }
        ]
    )

    wide = ElyticsDataProvider._pivot_timeseries(df, resolution="raw")

    assert "Current density" in wide.columns
    assert wide.loc[0, "Current density"] == 400.0


def test_pivot_timeseries_derives_anolyte_delta_pressure():
    df = pd.DataFrame(
        [
            {
                "timestamp": None,
                "elapsed_time_s": 60.0,
                "std_channel": "Anolyte inlet pressure",
                "value_mean": 2.5,
                "value_min": 2.0,
                "value_max": 3.0,
            },
            {
                "timestamp": None,
                "elapsed_time_s": 60.0,
                "std_channel": "Anolyte outlet pressure",
                "value_mean": 1.5,
                "value_min": 1.0,
                "value_max": 2.0,
            },
        ]
    )

    wide = ElyticsDataProvider._pivot_timeseries(df, resolution="agg")

    assert wide.loc[0, "Δp Anolyte_mean"] == 1.0
    assert wide.loc[0, "Δp Anolyte_min"] == 0.0
    assert wide.loc[0, "Δp Anolyte_max"] == 2.0


def test_pivot_timeseries_adds_original_alias_columns():
    df = pd.DataFrame(
        [
            {
                "timestamp": None,
                "elapsed_time_s": 60.0,
                "std_channel": "Δp Gas inlet - Gas outlet",
                "value_mean": 0.4,
                "value_min": 0.3,
                "value_max": 0.5,
            },
        ]
    )

    wide = ElyticsDataProvider._pivot_timeseries(df, resolution="agg")

    assert wide.loc[0, "ΔpGas inlet - Gas outlet_mean"] == 0.4
    assert wide.loc[0, "ΔpGas inlet - Gas outlet_min"] == 0.3
    assert wide.loc[0, "ΔpGas inlet - Gas outlet_max"] == 0.5


def test_all_report_resolves_to_full_channel_catalog():
    class FakeDataManager:
        def list_channels(self, series):
            return [
                {"std_channel": "Stack Voltage"},
                {"std_channel": None, "channel_name": "Current"},
            ]

    report = {"y1_cols": [], "y2_cols": []}
    assert _query_columns_for_report(report, object(), FakeDataManager()) == [
        "Stack Voltage",
        "Current",
    ]


def test_all_report_drops_alias_duplicates_before_auto_plotting():
    df = pd.DataFrame(
        {
            "Elapsed time": [60.0],
            "Δp Gas inlet - Gas outlet_mean": [0.4],
            "ΔpGas inlet - Gas outlet_mean": [0.4],
            "Stack Voltage_mean": [14.0],
        }
    )

    cleaned = _drop_alias_duplicate_columns(df)

    assert "Δp Gas inlet - Gas outlet_mean" in cleaned.columns
    assert "ΔpGas inlet - Gas outlet_mean" not in cleaned.columns
    assert "Stack Voltage_mean" in cleaned.columns


def test_rgb_to_rgba_converts_plotly_hex_colors():
    assert rgb_to_rgba("#636EFA", 0.5) == "rgba(99,110,250,0.5)"


def test_pivot_timeseries_uses_elapsed_bin_for_aggregate_rows():
    df = pd.DataFrame(
        [
            {
                "timestamp": None,
                "elapsed_time_s": 43.0,
                "elapsed_bin_s": 0.0,
                "std_channel": "Stack Voltage",
                "value_mean": 14.2,
                "value_min": 14.0,
                "value_max": 14.4,
            },
            {
                "timestamp": None,
                "elapsed_time_s": 102.0,
                "elapsed_bin_s": 60.0,
                "std_channel": "Stack Voltage",
                "value_mean": 14.3,
                "value_min": 14.1,
                "value_max": 14.5,
            },
        ]
    )

    wide = ElyticsDataProvider._pivot_timeseries(df, resolution="agg")

    assert wide["Elapsed time"].tolist() == [0.0, 60.0]


def test_pivot_timeseries_applies_percent_plausibility_limits():
    df = pd.DataFrame(
        [
            {
                "timestamp": None,
                "elapsed_time_s": 60.0,
                "elapsed_bin_s": 60.0,
                "std_channel": "Energy Efficiency",
                "value_mean": 250.0,
                "value_min": -20.0,
                "value_max": 500.0,
            },
        ]
    )

    wide = ElyticsDataProvider._pivot_timeseries(df, resolution="agg")

    assert wide.loc[0, "Energy Efficiency_mean"] == 100.0
    assert wide.loc[0, "Energy Efficiency_min"] == 0.0
    assert wide.loc[0, "Energy Efficiency_max"] == 100.0
