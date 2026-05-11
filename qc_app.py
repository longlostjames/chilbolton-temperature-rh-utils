#!/usr/bin/env python3
"""
QC web interface for HMP155 purge indices.

Allows point-and-click editing of purge_indices_YYYY.csv files via a Plotly
Dash app served locally over SSH local port forwarding.

Run with:
    python qc_app.py [--port 8051] [--host 127.0.0.1]

Access via SSH local port forwarding:
    ssh -L 8051:localhost:8051 <username>@<jasmin-host>
Then open http://localhost:8051 in your browser.

Environment variables (override defaults):
    TRH_DATA_ROOT   Root directory for level1d NetCDF files
    PURGE_CSV_DIR   Directory containing purge_indices_YYYY.csv files
"""

import argparse
import datetime
import glob
import os
import re

import dash
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import xarray as xr
from dash import Input, Output, State, callback, ctx, dcc, html

# ---------------------------------------------------------------------------
# Data roots — override with environment variables
# ---------------------------------------------------------------------------

# NetCDF files searched across multiple roots in priority order.
# Layout "yearly" means <root>/<year>/*.nc
# Layout "monthly" means <root>/<year>/<yearmonth>/*.nc
_GWS = "/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term"
# 2015–2024-03-31: published archive on BADC
_BADC = "/badc/ncas-cao/data/ncas-temperature-rh-1/20150415_longterm/v1.1"
# 2024-04-01 onward: long-term processing on GWS
_GWS_LONG = "/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/20150415_long-term"
TRH_ROOTS = [
    # 2024-04-01 onward: long-term GWS processing (yearly)
    (_GWS_LONG, "yearly"),
    # 2015–2024-03-31: published BADC archive (yearly)
    (_BADC, "yearly"),
]

# Directory containing purge_indices_YYYY.csv files (defaults to this repo)
CSV_DIR = os.environ.get(
    "PURGE_CSV_DIR",
    os.path.dirname(os.path.abspath(__file__)),
)

# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------

INDEX_KEYS = [
    "purge1_start_idx",
    "purge1_end_idx",
    "recovery1_start_idx",
    "recovery1_end_idx",
]

BOUNDARY_OPTIONS = [
    {"label": " Drag to set purge period", "value": "drag_purge"},
    {"label": " Drag to set recovery period", "value": "drag_recovery"},
    {"label": " Set purge start", "value": "purge1_start_idx"},
    {"label": " Set purge end", "value": "purge1_end_idx"},
    {"label": " Set recovery start", "value": "recovery1_start_idx"},
    {"label": " Set recovery end", "value": "recovery1_end_idx"},
    {"label": " Browse (no action)", "value": "none"},
]

BOUNDARY_META = {
    "purge1_start_idx":    {"label": "Purge start",    "colour": "darkred"},
    "purge1_end_idx":      {"label": "Purge end",      "colour": "red"},
    "recovery1_start_idx": {"label": "Recovery start", "colour": "darkorange"},
    "recovery1_end_idx":   {"label": "Recovery end",   "colour": "orange"},
}


def _version_key(path):
    m = re.search(r"_v(\d+)\.(\d+)\.nc$", path, re.IGNORECASE)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _best_file(candidates):
    if not candidates:
        return None
    return max(candidates, key=lambda p: (_version_key(p), os.path.getmtime(p)))


def _glob_day_files(roots, year, month, day):
    date_str = f"{year}{month:02d}{day:02d}"
    candidates = []
    for root, layout in roots:
        if not os.path.isdir(root):
            continue
        if layout == "yearly":
            d = os.path.join(root, str(year))
        else:
            d = os.path.join(root, str(year), f"{year}{month:02d}")
        candidates += glob.glob(os.path.join(d, f"*{date_str}*.nc"))
    # From 2024-04-01 onwards the STFC instrument supersedes the NCAS one
    if datetime.date(year, month, day) >= datetime.date(2024, 4, 1):
        stfc = [c for c in candidates if os.path.basename(c).startswith("stfc-")]
        if stfc:
            candidates = stfc
    return _best_file(candidates)


def available_years():
    years = set()
    for root, _ in TRH_ROOTS:
        if not os.path.isdir(root):
            continue
        for entry in os.listdir(root):
            if entry.isdigit() and len(entry) == 4:
                years.add(int(entry))
    # Also include years that have existing CSV files
    for fname in glob.glob(os.path.join(CSV_DIR, "purge_indices_????.csv")):
        m = re.search(r"purge_indices_(\d{4})\.csv$", fname)
        if m:
            years.add(int(m.group(1)))
    today_year = datetime.date.today().year
    years.add(today_year)
    return sorted(years)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_day_trh(year, month, day):
    """Load a single day's NetCDF file and return an in-memory xr.Dataset, or None."""
    f = _glob_day_files(TRH_ROOTS, year, month, day)
    if not f:
        print(f"DEBUG load_day_trh: no file found for {year}-{month:02d}-{day:02d}")
        return None
    print(f"DEBUG load_day_trh: loading {f}")
    try:
        ds = xr.open_dataset(f)
        if "time" not in ds or ds.time.size == 0:
            print(f"DEBUG load_day_trh: file has no time data ({ds.time.size if 'time' in ds else 'no time var'})")
            ds.close()
            return None
        ds.load()
        print(f"DEBUG load_day_trh: loaded {ds.time.size} samples, vars={list(ds.data_vars)}")
        # Convert temperature from K to °C if stored in Kelvin
        if "air_temperature" in ds:
            if ds["air_temperature"].attrs.get("units", "").upper() in ("K", "KELVIN") \
                    or float(ds["air_temperature"].values.mean()) > 200:
                # Use .copy() to ensure a plain numpy array (not a memory map)
                # before modifying in-place, then close the file.
                arr = ds["air_temperature"].values.copy()
                arr -= 273.15
                ds["air_temperature"] = xr.Variable(
                    ds["air_temperature"].dims, arr,
                    {**ds["air_temperature"].attrs, "units": "degC"},
                )
        ds.close()
        return ds
    except Exception as e:
        print(f"ERROR loading {f}: {e}")
        return None


def dataset_to_store(ds):
    """Serialise a Dataset's key arrays into a JSON-safe dict for dcc.Store."""
    if ds is None:
        return None
    times = pd.to_datetime(ds["time"].values)

    def _arr(name):
        if name in ds:
            return ds[name].values.tolist()
        return None

    return {
        "times": [t.isoformat() for t in times],
        "air_temperature": _arr("air_temperature"),
        "relative_humidity": _arr("relative_humidity"),
        "qc_flag_air_temperature": _arr("qc_flag_air_temperature"),
        "qc_flag_relative_humidity": _arr("qc_flag_relative_humidity"),
    }


# ---------------------------------------------------------------------------
# Purge indices CSV I/O
# ---------------------------------------------------------------------------

def csv_path(year):
    return os.path.join(CSV_DIR, f"purge_indices_{year}.csv")


def load_purge_csv(year):
    """Load purge indices CSV for a year, or return an empty DataFrame."""
    path = csv_path(year)
    if not os.path.exists(path):
        return pd.DataFrame(columns=["date"] + INDEX_KEYS)
    try:
        df = pd.read_csv(path, parse_dates=["date"])
        return df
    except Exception as e:
        print(f"Warning: could not read {path}: {e}")
        return pd.DataFrame(columns=["date"] + INDEX_KEYS)


def save_purge_csv(year, df):
    """Save purge indices DataFrame to CSV, sorted by date."""
    path = csv_path(year)
    df_sorted = df.sort_values("date").copy()
    df_sorted["date"] = pd.to_datetime(df_sorted["date"]).dt.strftime("%Y-%m-%d")
    df_sorted.to_csv(path, index=False)


def csv_to_store(year):
    """Return CSV contents as a list-of-dicts suitable for dcc.Store."""
    df = load_purge_csv(year)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df.to_dict("records")


def store_to_df(records):
    """Re-hydrate a dcc.Store list-of-dicts into a DataFrame."""
    if not records:
        return pd.DataFrame(columns=["date"] + INDEX_KEYS)
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_row_indices(df, date):
    """Return dict of index values for a date, inferring None for missing."""
    date = pd.Timestamp(date).normalize()
    mask = pd.to_datetime(df["date"]).dt.normalize() == date
    empty = {k: None for k in INDEX_KEYS}
    if not mask.any():
        return empty
    row = df[mask].iloc[0]
    result = {}
    for k in INDEX_KEYS:
        v = row.get(k, np.nan)
        result[k] = None if (isinstance(v, float) and np.isnan(v)) else int(v)
    return result


def upsert_row(df, date, indices):
    """Insert or update a row in the DataFrame."""
    date = pd.Timestamp(date).normalize()
    mask = pd.to_datetime(df["date"]).dt.normalize() == date
    new_row = {"date": date}
    for k in INDEX_KEYS:
        v = indices.get(k)
        new_row[k] = int(v) if v is not None else np.nan
    if mask.any():
        for col, val in new_row.items():
            df.loc[mask, col] = val
    else:
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    return df


def delete_row(df, date):
    """Remove a date's row from the DataFrame."""
    date = pd.Timestamp(date).normalize()
    mask = pd.to_datetime(df["date"]).dt.normalize() == date
    return df[~mask].copy()


# ---------------------------------------------------------------------------
# Purge index inference from QC flags
# ---------------------------------------------------------------------------

def infer_indices_from_qc(store_data):
    """Read first purge (flag=3) and recovery (flag=4) intervals from QC arrays."""
    indices = {k: None for k in INDEX_KEYS}
    if store_data is None:
        return indices
    qc_rh = store_data.get("qc_flag_relative_humidity")
    if qc_rh is None:
        return indices
    qc_arr = np.asarray(qc_rh, dtype=float)
    purge_idx = np.where(qc_arr == 3)[0]
    recovery_idx = np.where(qc_arr == 4)[0]
    if len(purge_idx):
        indices["purge1_start_idx"] = int(purge_idx[0])
        indices["purge1_end_idx"] = int(purge_idx[-1])
    if len(recovery_idx):
        indices["recovery1_start_idx"] = int(recovery_idx[0])
        indices["recovery1_end_idx"] = int(recovery_idx[-1])
    return indices


# ---------------------------------------------------------------------------
# Plot building
# ---------------------------------------------------------------------------

def _idx_to_time(times, idx):
    """Convert a sample index to a timestamp string, or None."""
    if idx is None:
        return None
    try:
        idx = int(idx)
        if 0 <= idx < len(times):
            return str(times[idx])
    except (TypeError, ValueError):
        pass
    return None


def _build_day_fig(store_data, indices, dragmode="zoom"):
    """Build the main two-panel figure (temperature + RH) for a day."""
    if store_data is None:
        fig = go.Figure()
        fig.update_layout(title="No data loaded", height=550)
        return fig

    times = np.asarray(store_data["times"])
    temp = np.asarray(store_data["air_temperature"]) if store_data.get("air_temperature") else None
    rh = np.asarray(store_data["relative_humidity"]) if store_data.get("relative_humidity") else None
    qc_t = np.asarray(store_data["qc_flag_air_temperature"], dtype=float) if store_data.get("qc_flag_air_temperature") else None
    qc_r = np.asarray(store_data["qc_flag_relative_humidity"], dtype=float) if store_data.get("qc_flag_relative_humidity") else None

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=["Air Temperature (°C)", "Relative Humidity (%)"],
        vertical_spacing=0.09,
    )

    # --- Temperature ---
    if temp is not None:
        for flag, colour, name, sym in [
            (1, "steelblue", "Good (1)", "circle"),
            (2, "#888",     "Bad (2)",  "x"),
            (3, "red",      "Purge (3)", "circle"),
            (4, "orange",   "Recovery (4)", "circle"),
        ]:
            mask = (qc_t == flag) if qc_t is not None else (np.ones(len(times), dtype=bool) if flag == 1 else np.zeros(len(times), dtype=bool))
            if not mask.any():
                continue
            fig.add_trace(go.Scatter(
                x=times[mask], y=temp[mask], mode="markers",
                marker=dict(color=colour, size=3, symbol=sym),
                name=name, legendgroup=f"t{flag}", showlegend=(flag in (1, 2, 3, 4)),
                legendgrouptitle_text="Temperature" if flag == 1 else None,
            ), row=1, col=1)

    # --- Relative humidity ---
    if rh is not None:
        for flag, colour, name, sym in [
            (1, "steelblue", "Good (1)", "circle"),
            (2, "#888",     "Bad (2)",  "x"),
            (3, "red",      "Purge (3)", "circle"),
            (4, "darkorange", "Recovery (4)", "circle"),
        ]:
            mask = (qc_r == flag) if qc_r is not None else (np.ones(len(times), dtype=bool) if flag == 1 else np.zeros(len(times), dtype=bool))
            if not mask.any():
                continue
            fig.add_trace(go.Scatter(
                x=times[mask], y=rh[mask], mode="markers",
                marker=dict(color=colour, size=3, symbol=sym),
                name=name, legendgroup=f"rh{flag}", showlegend=False,
            ), row=2, col=1)

    # --- Shaded regions and boundary lines from indices ---
    p1s = _idx_to_time(times, indices.get("purge1_start_idx"))
    p1e = _idx_to_time(times, indices.get("purge1_end_idx"))
    r1s = _idx_to_time(times, indices.get("recovery1_start_idx"))
    r1e = _idx_to_time(times, indices.get("recovery1_end_idx"))

    for row in [1, 2]:
        if p1s and p1e:
            fig.add_vrect(x0=p1s, x1=p1e, fillcolor="red", opacity=0.12,
                          layer="below", line_width=0, row=row, col=1)
        if r1s and r1e:
            fig.add_vrect(x0=r1s, x1=r1e, fillcolor="peachpuff", opacity=0.45,
                          layer="below", line_width=0, row=row, col=1)

    for t_val, colour, dash_style in [
        (p1s, "darkred",    "solid"),
        (p1e, "red",        "dash"),
        (r1s, "darkorange", "solid"),
        (r1e, "orange",     "dash"),
    ]:
        if t_val is None:
            continue
        for row in [1, 2]:
            fig.add_vline(x=t_val, line_color=colour, line_dash=dash_style,
                          line_width=1.5, row=row, col=1)

    fig.update_yaxes(title_text="Temperature (°C)", row=1, col=1)
    fig.update_yaxes(title_text="Relative humidity (%)", row=2, col=1)
    fig.update_xaxes(title_text="Time (UTC)", row=2, col=1)
    fig.update_layout(
        height=580,
        margin=dict(l=70, r=20, t=55, b=50),
        hovermode="x unified" if dragmode == "zoom" else False,
        clickmode="event",
        dragmode=dragmode,
        selectdirection="h" if dragmode == "select" else None,
        legend=dict(orientation="h", y=1.06, x=1, xanchor="right"),
    )
    return fig


def _build_zoom_fig(store_data, indices, buffer_minutes=15, dragmode="zoom"):
    """Build a zoomed figure around the purge/recovery region."""
    if store_data is None:
        return go.Figure(layout={"title": "No data", "height": 380})

    times = np.asarray(store_data["times"])
    p1s = _idx_to_time(times, indices.get("purge1_start_idx"))
    r1e = _idx_to_time(times, indices.get("recovery1_end_idx"))

    fig = _build_day_fig(store_data, indices, dragmode=dragmode)
    fig.update_layout(height=380, title="Zoomed — purge/recovery region")

    if p1s and r1e:
        buf = pd.Timedelta(minutes=buffer_minutes)
        zoom_start = (pd.Timestamp(p1s) - buf).isoformat()
        zoom_end = (pd.Timestamp(r1e) + buf).isoformat()
        fig.update_xaxes(range=[zoom_start, zoom_end])
    elif p1s:
        buf = pd.Timedelta(minutes=buffer_minutes)
        zoom_start = (pd.Timestamp(p1s) - buf).isoformat()
        zoom_end = (pd.Timestamp(p1s) + pd.Timedelta(hours=2)).isoformat()
        fig.update_xaxes(range=[zoom_start, zoom_end])

    return fig


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

app = dash.Dash(__name__, title="HMP155 QC — Purge Indices Editor")

years = available_years()
today = datetime.date.today()
default_year = today.year if today.year in years else (years[-1] if years else today.year)

app.layout = html.Div(
    [
        html.H2(
            "HMP155 QC — Purge Indices Editor",
            style={"fontFamily": "sans-serif", "margin": "16px 16px 8px"},
        ),
        # ── Top controls ──────────────────────────────────────────────────
        html.Div(
            [
                html.Label("Year:", style={"marginRight": "6px", "fontFamily": "sans-serif"}),
                dcc.Dropdown(
                    id="year-dropdown",
                    options=[{"label": str(y), "value": y} for y in years],
                    value=default_year,
                    clearable=False,
                    style={"width": "110px", "marginRight": "20px"},
                ),
                html.Label("Date:", style={"marginRight": "6px", "fontFamily": "sans-serif"}),
                dcc.DatePickerSingle(
                    id="day-picker",
                    display_format="YYYY-MM-DD",
                    date=today.isoformat(),
                ),
                html.Button(
                    "◀ Prev",
                    id="prev-day-btn",
                    n_clicks=0,
                    style={"marginLeft": "10px", "cursor": "pointer", "padding": "5px 10px"},
                ),
                html.Button(
                    "Next ▶",
                    id="next-day-btn",
                    n_clicks=0,
                    style={"marginLeft": "4px", "cursor": "pointer", "padding": "5px 10px"},
                ),
                html.Span(
                    id="status-msg",
                    style={
                        "marginLeft": "20px",
                        "fontFamily": "sans-serif",
                        "color": "#555",
                        "fontStyle": "italic",
                        "fontSize": "0.9em",
                    },
                ),
            ],
            style={
                "display": "flex",
                "alignItems": "center",
                "margin": "0 16px 10px",
                "flexWrap": "wrap",
                "gap": "4px",
            },
        ),
        # ── Main body: plots (left) + controls (right) ───────────────────
        html.Div(
            [
                # ── Left: plots ──────────────────────────────────────────
                html.Div(
                    [
                        html.P(
                            "Select a boundary radio button on the right, then click the plot "
                            "to set that index. Use ±1 buttons or type values directly for "
                            "fine adjustment.",
                            style={
                                "fontFamily": "sans-serif",
                                "color": "#555",
                                "margin": "0 0 4px",
                                "fontSize": "0.88em",
                            },
                        ),
                        dcc.Graph(id="day-graph", style={"height": "580px"}),
                        html.H4(
                            "Zoomed view — purge/recovery region",
                            style={"fontFamily": "sans-serif", "margin": "10px 0 4px"},
                        ),
                        dcc.Graph(id="zoom-graph", style={"height": "380px"}),
                    ],
                    style={"flex": "3", "minWidth": "0"},
                ),
                # ── Right: index editor ───────────────────────────────────
                html.Div(
                    [
                        html.H4(
                            "Boundary indices",
                            style={"fontFamily": "sans-serif", "margin": "0 0 6px"},
                        ),
                        html.P(
                            "Choose which boundary to set by clicking:",
                            style={"fontFamily": "sans-serif", "fontSize": "0.88em", "color": "#555", "margin": "0 0 6px"},
                        ),
                        dcc.RadioItems(
                            id="active-boundary",
                            options=BOUNDARY_OPTIONS,
                            value="none",
                            inputStyle={"marginRight": "5px"},
                            labelStyle={
                                "display": "block",
                                "fontFamily": "sans-serif",
                                "marginBottom": "6px",
                                "cursor": "pointer",
                                "fontSize": "0.92em",
                            },
                        ),
                        html.Hr(style={"margin": "12px 0"}),
                        # ── Index value rows ──────────────────────────────
                        *[
                            html.Div(
                                [
                                    html.Label(
                                        meta["label"],
                                        style={
                                            "fontFamily": "sans-serif",
                                            "fontSize": "0.88em",
                                            "color": meta["colour"],
                                            "fontWeight": "bold",
                                            "marginBottom": "2px",
                                            "display": "block",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Button(
                                                "−",
                                                id=f"dec-{key}",
                                                n_clicks=0,
                                                style={
                                                    "padding": "2px 9px",
                                                    "cursor": "pointer",
                                                    "fontSize": "1.1em",
                                                    "lineHeight": "1",
                                                },
                                            ),
                                            dcc.Input(
                                                id=f"idx-{key}",
                                                type="number",
                                                min=0,
                                                step=1,
                                                value=None,
                                                debounce=True,
                                                style={
                                                    "width": "85px",
                                                    "textAlign": "center",
                                                    "margin": "0 4px",
                                                    "fontSize": "0.9em",
                                                },
                                            ),
                                            html.Button(
                                                "+",
                                                id=f"inc-{key}",
                                                n_clicks=0,
                                                style={
                                                    "padding": "2px 9px",
                                                    "cursor": "pointer",
                                                    "fontSize": "1.1em",
                                                    "lineHeight": "1",
                                                },
                                            ),
                                        ],
                                        style={
                                            "display": "flex",
                                            "alignItems": "center",
                                            "marginBottom": "10px",
                                        },
                                    ),
                                ]
                            )
                            for key, meta in BOUNDARY_META.items()
                        ],
                        html.Hr(style={"margin": "12px 0"}),
                        html.Button(
                            "Auto-adjust purge",
                            id="auto-adjust-btn",
                            n_clicks=0,
                            title="Snaps purge start/end to where RH becomes flat (constant)",
                            style={
                                "padding": "6px 12px",
                                "fontSize": "0.88em",
                                "cursor": "pointer",
                                "width": "100%",
                                "marginBottom": "4px",
                            },
                        ),
                        html.Div(
                            id="auto-adjust-status",
                            style={
                                "fontFamily": "sans-serif",
                                "fontSize": "0.82em",
                                "minHeight": "16px",
                                "marginBottom": "4px",
                                "color": "#555",
                            },
                        ),
                        html.Hr(style={"margin": "12px 0"}),
                        html.Div(
                            [
                                html.Button(
                                    "Save to CSV",
                                    id="save-btn",
                                    n_clicks=0,
                                    style={
                                        "padding": "8px 18px",
                                        "fontSize": "0.95em",
                                        "cursor": "pointer",
                                        "backgroundColor": "#2a7fd4",
                                        "color": "white",
                                        "border": "none",
                                        "borderRadius": "4px",
                                        "marginRight": "8px",
                                        "marginBottom": "6px",
                                    },
                                ),
                                html.Button(
                                    "Delete row",
                                    id="delete-btn",
                                    n_clicks=0,
                                    style={
                                        "padding": "8px 14px",
                                        "fontSize": "0.95em",
                                        "cursor": "pointer",
                                        "backgroundColor": "#c0392b",
                                        "color": "white",
                                        "border": "none",
                                        "borderRadius": "4px",
                                        "marginBottom": "6px",
                                    },
                                ),
                            ],
                            style={"display": "flex", "flexWrap": "wrap"},
                        ),
                        html.Div(
                            id="save-status",
                            style={
                                "fontFamily": "sans-serif",
                                "fontSize": "0.88em",
                                "minHeight": "20px",
                                "marginTop": "4px",
                                "color": "green",
                            },
                        ),
                        html.Hr(style={"margin": "12px 0"}),
                        # ── Apply to date range ────────────────────────────
                        html.H4(
                            "Apply to date range",
                            style={"fontFamily": "sans-serif", "margin": "0 0 4px", "fontSize": "0.95em"},
                        ),
                        html.P(
                            "Applies the current indices to every date in the range, "
                            "offset by the drift (samples/day) per day from the selected date.",
                            style={"fontFamily": "sans-serif", "fontSize": "0.82em", "color": "#555", "margin": "0 0 6px"},
                        ),
                        html.Div(
                            [
                                html.Label("From:", style={"fontFamily": "sans-serif", "fontSize": "0.88em", "marginRight": "4px"}),
                                dcc.Input(
                                    id="range-start",
                                    type="text",
                                    placeholder="YYYY-MM-DD",
                                    debounce=True,
                                    style={"width": "105px", "fontSize": "0.88em"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center", "marginBottom": "4px"},
                        ),
                        html.Div(
                            [
                                html.Label("To:", style={"fontFamily": "sans-serif", "fontSize": "0.88em", "marginRight": "4px"}),
                                dcc.Input(
                                    id="range-end",
                                    type="text",
                                    placeholder="YYYY-MM-DD",
                                    debounce=True,
                                    style={"width": "105px", "fontSize": "0.88em"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center", "marginBottom": "4px"},
                        ),
                        html.Div(
                            [
                                html.Label(
                                    "Drift (samples/day):",
                                    style={"fontFamily": "sans-serif", "fontSize": "0.88em", "marginRight": "4px"},
                                ),
                                dcc.Input(
                                    id="range-drift",
                                    type="number",
                                    value=0,
                                    step=0.1,
                                    debounce=True,
                                    style={"width": "70px", "fontSize": "0.88em"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center", "marginBottom": "6px"},
                        ),
                        html.Button(
                            "Apply to range",
                            id="apply-range-btn",
                            n_clicks=0,
                            style={
                                "padding": "7px 14px",
                                "fontSize": "0.92em",
                                "cursor": "pointer",
                                "backgroundColor": "#5a7a2e",
                                "color": "white",
                                "border": "none",
                                "borderRadius": "4px",
                                "marginBottom": "4px",
                            },
                        ),
                        html.Div(
                            id="range-status",
                            style={
                                "fontFamily": "sans-serif",
                                "fontSize": "0.88em",
                                "minHeight": "18px",
                                "marginTop": "4px",
                                "color": "green",
                            },
                        ),
                        html.Hr(style={"margin": "12px 0"}),
                        # ── CSV preview table ──────────────────────────────
                        html.H4(
                            "CSV rows (year)",
                            style={"fontFamily": "sans-serif", "margin": "0 0 6px", "fontSize": "0.95em"},
                        ),
                        html.Div(
                            id="csv-table",
                            style={
                                "fontFamily": "monospace",
                                "fontSize": "0.8em",
                                "maxHeight": "300px",
                                "overflowY": "auto",
                                "backgroundColor": "#fafafa",
                                "border": "1px solid #ddd",
                                "borderRadius": "4px",
                                "padding": "6px",
                            },
                        ),
                    ],
                    style={
                        "flex": "1",
                        "minWidth": "230px",
                        "maxWidth": "290px",
                        "padding": "14px",
                        "backgroundColor": "#f5f5f5",
                        "borderRadius": "6px",
                        "marginLeft": "16px",
                        "alignSelf": "flex-start",
                    },
                ),
            ],
            style={"display": "flex", "alignItems": "flex-start", "margin": "0 16px"},
        ),
        # ── Stores ────────────────────────────────────────────────────────
        dcc.Store(id="dataset-store"),   # serialised arrays for the loaded day
        dcc.Store(id="indices-store"),   # current working boundary indices
        dcc.Store(id="csv-store"),       # year's CSV as list-of-dicts
    ],
    style={"maxWidth": "1400px", "margin": "0 auto"},
)

# ---------------------------------------------------------------------------
# Auto-adjust helper
# ---------------------------------------------------------------------------

def _auto_adjust_purge(store_data, indices, search_buffer=300, flat_thresh=0.05):
    """
    Refine purge1_start_idx / purge1_end_idx by finding where RH transitions
    from varying to constant (purge start) and back again (purge end).

    During a purge the sensor holds RH at the value it had when the purge
    started, so consecutive absolute differences are ≈ 0.  We walk outward
    from the rough indices to find those transition points.
    """
    result = dict(indices) if indices else {}
    if store_data is None:
        return result
    rh = store_data.get("relative_humidity")
    if not rh:
        return result
    rh = np.asarray(rh, dtype=float)
    n = len(rh)

    p_start = indices.get("purge1_start_idx")
    p_end   = indices.get("purge1_end_idx")
    if p_start is None or p_end is None:
        return result
    p_start, p_end = int(p_start), int(p_end)

    # flat[i] is True when |rh[i+1] - rh[i]| < flat_thresh
    diffs = np.abs(np.diff(rh))
    flat  = diffs < flat_thresh          # length n-1

    win_s = max(0, p_start - search_buffer)
    win_e = min(n - 2, p_end + search_buffer)  # n-2 because flat has length n-1

    # Walk backward from p_start: while rh[i-1] ≈ rh[i], extend start leftward
    i = p_start
    while i > win_s and flat[i - 1]:
        i -= 1
    new_start = i

    # Walk forward from p_end: while rh[j] ≈ rh[j+1], extend end rightward
    j = p_end
    while j < win_e and flat[j]:
        j += 1
    new_end = j

    result["purge1_start_idx"] = new_start
    result["purge1_end_idx"]   = new_end
    return result


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


# 1. Load year CSV whenever the year dropdown changes
@callback(
    Output("csv-store", "data"),
    Input("year-dropdown", "value"),
)
def load_csv_for_year(year):
    return csv_to_store(year)


# 2. Navigate prev/next day
@callback(
    Output("day-picker", "date"),
    Input("prev-day-btn", "n_clicks"),
    Input("next-day-btn", "n_clicks"),
    State("day-picker", "date"),
    prevent_initial_call=True,
)
def navigate_day(prev_n, next_n, current_date):
    if not current_date:
        return dash.no_update
    d = datetime.date.fromisoformat(str(current_date)[:10])
    if ctx.triggered_id == "prev-day-btn":
        d -= datetime.timedelta(days=1)
    else:
        d += datetime.timedelta(days=1)
    return d.isoformat()


# 3. Load data and initialise indices when date changes
@callback(
    Output("dataset-store", "data"),
    Output("indices-store", "data"),
    Output("status-msg", "children"),
    Output("idx-purge1_start_idx", "value"),
    Output("idx-purge1_end_idx", "value"),
    Output("idx-recovery1_start_idx", "value"),
    Output("idx-recovery1_end_idx", "value"),
    Input("day-picker", "date"),
    State("year-dropdown", "value"),
    State("csv-store", "data"),
)
def load_day(date_str, year, csv_records):
    if not date_str:
        return None, None, "No date selected.", None, None, None, None
    date = datetime.date.fromisoformat(str(date_str)[:10])
    ds = load_day_trh(date.year, date.month, date.day)
    store_data = dataset_to_store(ds)

    # Get existing indices from CSV; fall back to inferring from QC flags
    df = store_to_df(csv_records)
    indices = get_row_indices(df, date)
    if all(v is None for v in indices.values()) and store_data is not None:
        indices = infer_indices_from_qc(store_data)

    if store_data is None:
        status = f"No NetCDF file found for {date_str}."
    else:
        n = len(store_data["times"])
        in_csv = "in CSV" if not all(v is None for v in get_row_indices(df, date).values()) else "not in CSV"
        status = f"{n} samples — {in_csv}."

    return (
        store_data,
        indices,
        status,
        indices.get("purge1_start_idx"),
        indices.get("purge1_end_idx"),
        indices.get("recovery1_start_idx"),
        indices.get("recovery1_end_idx"),
    )


# 4. Handle plot click → set the active boundary to the nearest sample index
@callback(
    Output("indices-store", "data", allow_duplicate=True),
    Output("idx-purge1_start_idx", "value", allow_duplicate=True),
    Output("idx-purge1_end_idx", "value", allow_duplicate=True),
    Output("idx-recovery1_start_idx", "value", allow_duplicate=True),
    Output("idx-recovery1_end_idx", "value", allow_duplicate=True),
    Input("day-graph", "clickData"),
    State("active-boundary", "value"),
    State("dataset-store", "data"),
    State("indices-store", "data"),
    prevent_initial_call=True,
)
def handle_plot_click(click_data, active_boundary, store_data, indices):
    no_change = (dash.no_update,) * 5
    if not click_data or not active_boundary or active_boundary == "none":
        return no_change
    if not store_data or not store_data.get("times"):
        return no_change

    clicked_x = click_data["points"][0].get("x")
    if not clicked_x:
        return no_change

    times = pd.to_datetime(store_data["times"])
    clicked_ts = pd.Timestamp(clicked_x)
    diffs = np.abs((times - clicked_ts).total_seconds().values)
    nearest_idx = int(np.argmin(diffs))

    indices = dict(indices) if indices else {}
    indices[active_boundary] = nearest_idx

    return (
        indices,
        indices.get("purge1_start_idx"),
        indices.get("purge1_end_idx"),
        indices.get("recovery1_start_idx"),
        indices.get("recovery1_end_idx"),
    )


# 5. Handle ±1 buttons for all four boundaries (single combined callback)
@callback(
    Output("indices-store", "data", allow_duplicate=True),
    Output("idx-purge1_start_idx", "value", allow_duplicate=True),
    Output("idx-purge1_end_idx", "value", allow_duplicate=True),
    Output("idx-recovery1_start_idx", "value", allow_duplicate=True),
    Output("idx-recovery1_end_idx", "value", allow_duplicate=True),
    Input("dec-purge1_start_idx", "n_clicks"),
    Input("inc-purge1_start_idx", "n_clicks"),
    Input("dec-purge1_end_idx", "n_clicks"),
    Input("inc-purge1_end_idx", "n_clicks"),
    Input("dec-recovery1_start_idx", "n_clicks"),
    Input("inc-recovery1_start_idx", "n_clicks"),
    Input("dec-recovery1_end_idx", "n_clicks"),
    Input("inc-recovery1_end_idx", "n_clicks"),
    State("idx-purge1_start_idx", "value"),
    State("idx-purge1_end_idx", "value"),
    State("idx-recovery1_start_idx", "value"),
    State("idx-recovery1_end_idx", "value"),
    State("indices-store", "data"),
    prevent_initial_call=True,
)
def adjust_index(
    _d_ps, _i_ps, _d_pe, _i_pe, _d_rs, _i_rs, _d_re, _i_re,
    val_ps, val_pe, val_rs, val_re,
    indices,
):
    triggered = ctx.triggered_id
    if not triggered:
        return (dash.no_update,) * 5

    # Parse "inc-<key>" or "dec-<key>"
    direction, key = triggered.split("-", 1)
    delta = 1 if direction == "inc" else -1

    vals = {
        "purge1_start_idx":    val_ps,
        "purge1_end_idx":      val_pe,
        "recovery1_start_idx": val_rs,
        "recovery1_end_idx":   val_re,
    }
    current = vals.get(key)
    new_val = max(0, (int(current) if current is not None else 0) + delta)
    vals[key] = new_val

    indices = dict(indices) if indices else {}
    indices[key] = new_val

    return (
        indices,
        vals["purge1_start_idx"],
        vals["purge1_end_idx"],
        vals["recovery1_start_idx"],
        vals["recovery1_end_idx"],
    )


# 6. Sync manually typed index values back to the store
@callback(
    Output("indices-store", "data", allow_duplicate=True),
    Input("idx-purge1_start_idx", "value"),
    Input("idx-purge1_end_idx", "value"),
    Input("idx-recovery1_start_idx", "value"),
    Input("idx-recovery1_end_idx", "value"),
    State("indices-store", "data"),
    prevent_initial_call=True,
)
def sync_inputs_to_store(ps, pe, rs, re, indices):
    # Only process if triggered by one of the idx-* inputs (user typed)
    triggered = ctx.triggered_id
    if not triggered or not str(triggered).startswith("idx-"):
        return dash.no_update

    key = str(triggered)[4:]  # strip "idx-" prefix
    val_map = {
        "purge1_start_idx":    ps,
        "purge1_end_idx":      pe,
        "recovery1_start_idx": rs,
        "recovery1_end_idx":   re,
    }
    v = val_map.get(key)
    if v is None:
        return dash.no_update
    indices = dict(indices) if indices else {}
    indices[key] = int(v)
    return indices


# 6b. Auto-adjust purge boundaries to where RH becomes flat
@callback(
    Output("indices-store", "data", allow_duplicate=True),
    Output("idx-purge1_start_idx", "value", allow_duplicate=True),
    Output("idx-purge1_end_idx", "value", allow_duplicate=True),
    Output("idx-recovery1_start_idx", "value", allow_duplicate=True),
    Output("idx-recovery1_end_idx", "value", allow_duplicate=True),
    Output("auto-adjust-status", "children"),
    Input("auto-adjust-btn", "n_clicks"),
    State("dataset-store", "data"),
    State("indices-store", "data"),
    prevent_initial_call=True,
)
def auto_adjust_purge(n_clicks, store_data, indices):
    if not indices or indices.get("purge1_start_idx") is None or indices.get("purge1_end_idx") is None:
        return (dash.no_update,) * 5 + ("Set rough purge start/end first.",)
    new_indices = _auto_adjust_purge(store_data, indices)
    old_s, old_e = indices.get("purge1_start_idx"), indices.get("purge1_end_idx")
    new_s, new_e = new_indices.get("purge1_start_idx"), new_indices.get("purge1_end_idx")
    msg = f"Adjusted: start {old_s}→{new_s}, end {old_e}→{new_e}."
    return (
        new_indices,
        new_indices.get("purge1_start_idx"),
        new_indices.get("purge1_end_idx"),
        new_indices.get("recovery1_start_idx"),
        new_indices.get("recovery1_end_idx"),
        msg,
    )


# 7. Redraw graphs whenever indices, dataset, or active boundary changes
@callback(
    Output("day-graph", "figure"),
    Output("zoom-graph", "figure"),
    Input("indices-store", "data"),
    Input("dataset-store", "data"),
    Input("active-boundary", "value"),
)
def update_graphs(indices, store_data, active_boundary):
    indices = indices or {}
    dragmode = "select" if active_boundary in ("drag_purge", "drag_recovery") else "zoom"
    day_fig = _build_day_fig(store_data, indices, dragmode=dragmode)
    zoom_fig = _build_zoom_fig(store_data, indices, dragmode=dragmode)
    return day_fig, zoom_fig


# 7b. Handle drag-box selection (from either panel) to set purge or recovery period
@callback(
    Output("indices-store", "data", allow_duplicate=True),
    Output("idx-purge1_start_idx", "value", allow_duplicate=True),
    Output("idx-purge1_end_idx", "value", allow_duplicate=True),
    Output("idx-recovery1_start_idx", "value", allow_duplicate=True),
    Output("idx-recovery1_end_idx", "value", allow_duplicate=True),
    Input("day-graph", "selectedData"),
    Input("zoom-graph", "selectedData"),
    State("active-boundary", "value"),
    State("dataset-store", "data"),
    State("indices-store", "data"),
    prevent_initial_call=True,
)
def handle_drag_select(day_selected, zoom_selected, active_boundary, store_data, indices):
    no_change = (dash.no_update,) * 5
    # Use whichever panel triggered this callback
    selected_data = day_selected if ctx.triggered_id == "day-graph" else zoom_selected
    if not selected_data or active_boundary not in ("drag_purge", "drag_recovery"):
        return no_change
    if not store_data or not store_data.get("times"):
        return no_change

    # Extract the selected x-range.
    # With make_subplots, the range key is "x" for row-1 drags and "x2", "x3" …
    # for lower rows.  Grab whichever x-key is present first.
    range_data = selected_data.get("range") or {}
    x_keys = sorted(k for k in range_data if re.match(r"^x\d*$", k))
    if not x_keys:
        return no_change
    x_range = range_data[x_keys[0]]
    if len(x_range) < 2:
        return no_change
    x0, x1 = str(x_range[0]), str(x_range[1])

    times = pd.to_datetime(store_data["times"])
    ts0, ts1 = pd.Timestamp(x0), pd.Timestamp(x1)
    idx0 = int(np.argmin(np.abs((times - ts0).total_seconds().values)))
    idx1 = int(np.argmin(np.abs((times - ts1).total_seconds().values)))

    indices = dict(indices) if indices else {}
    if active_boundary == "drag_purge":
        indices["purge1_start_idx"] = idx0
        indices["purge1_end_idx"] = idx1
    else:
        indices["recovery1_start_idx"] = idx0
        indices["recovery1_end_idx"] = idx1

    return (
        indices,
        indices.get("purge1_start_idx"),
        indices.get("purge1_end_idx"),
        indices.get("recovery1_start_idx"),
        indices.get("recovery1_end_idx"),
    )


# 7c. Apply current indices to a date range with optional drift
@callback(
    Output("csv-store", "data", allow_duplicate=True),
    Output("range-status", "children"),
    Output("range-status", "style"),
    Input("apply-range-btn", "n_clicks"),
    State("range-start", "value"),
    State("range-end", "value"),
    State("range-drift", "value"),
    State("day-picker", "date"),
    State("year-dropdown", "value"),
    State("indices-store", "data"),
    State("csv-store", "data"),
    prevent_initial_call=True,
)
def apply_to_range(n_clicks, range_start, range_end, drift_per_day,
                   ref_date_str, year, indices, csv_records):
    err_style = {"color": "#c0392b", "fontFamily": "sans-serif", "fontSize": "0.88em", "minHeight": "18px"}
    ok_style  = {"color": "green",   "fontFamily": "sans-serif", "fontSize": "0.88em", "minHeight": "18px"}

    if not indices or all(v is None for v in indices.values()):
        return dash.no_update, "No indices set for reference date.", err_style
    if not range_start or not range_end:
        return dash.no_update, "Enter From and To dates.", err_style
    try:
        d_start = datetime.date.fromisoformat(range_start.strip())
        d_end   = datetime.date.fromisoformat(range_end.strip())
    except ValueError:
        return dash.no_update, "Invalid date format (use YYYY-MM-DD).", err_style
    if d_end < d_start:
        return dash.no_update, "To date must be ≥ From date.", err_style

    ref_date = datetime.date.fromisoformat(str(ref_date_str)[:10])
    drift = float(drift_per_day or 0)

    df = store_to_df(csv_records)
    count = 0
    d = d_start
    while d <= d_end:
        offset = (d - ref_date).days
        shift = round(offset * drift)
        new_indices = {}
        for k in INDEX_KEYS:
            v = indices.get(k)
            if v is not None:
                new_indices[k] = max(0, int(v) + shift)
            else:
                new_indices[k] = None
        df = upsert_row(df, d, new_indices)
        count += 1
        d += datetime.timedelta(days=1)

    save_purge_csv(year, df)
    new_records = csv_to_store(year)
    return new_records, f"Applied to {count} date(s).", ok_style


# 8. Save or delete CSV row
@callback(
    Output("csv-store", "data", allow_duplicate=True),
    Output("save-status", "children"),
    Output("save-status", "style"),
    Input("save-btn", "n_clicks"),
    Input("delete-btn", "n_clicks"),
    State("day-picker", "date"),
    State("year-dropdown", "value"),
    State("indices-store", "data"),
    State("csv-store", "data"),
    prevent_initial_call=True,
)
def save_or_delete(save_n, delete_n, date_str, year, indices, csv_records):
    if not date_str:
        return dash.no_update, "No date selected.", {"color": "red"}

    df = store_to_df(csv_records)

    if ctx.triggered_id == "delete-btn":
        df = delete_row(df, date_str)
        save_purge_csv(year, df)
        new_records = csv_to_store(year)
        return new_records, f"Deleted row for {date_str}.", {"color": "#c0392b"}

    # Save
    if not indices:
        return dash.no_update, "No indices to save.", {"color": "#c0392b"}
    df = upsert_row(df, date_str, indices)
    save_purge_csv(year, df)
    new_records = csv_to_store(year)
    return new_records, f"Saved {date_str}.", {"color": "green"}


# 9. Render the CSV table in the sidebar
@callback(
    Output("csv-table", "children"),
    Input("csv-store", "data"),
    State("day-picker", "date"),
)
def render_csv_table(records, current_date):
    if not records:
        return html.Span("(empty)", style={"color": "#999"})

    df = pd.DataFrame(records)
    if df.empty:
        return html.Span("(empty)", style={"color": "#999"})

    cur_date = str(current_date)[:10] if current_date else None
    rows = []
    for _, row in df.iterrows():
        date_val = str(row.get("date", ""))[:10]
        is_current = date_val == cur_date
        row_style = {
            "backgroundColor": "#d6eaff" if is_current else "transparent",
            "padding": "1px 4px",
            "whiteSpace": "nowrap",
        }
        cols = []
        for col in ["date", "purge1_start_idx", "purge1_end_idx",
                    "recovery1_start_idx", "recovery1_end_idx"]:
            v = row.get(col, "")
            try:
                v_str = str(int(float(v))) if col != "date" and str(v) not in ("", "nan") else str(v)[:10]
            except (ValueError, TypeError):
                v_str = str(v)[:10]
            cols.append(html.Td(v_str, style={"paddingRight": "8px"}))
        rows.append(html.Tr(cols, style=row_style))

    header = html.Tr([
        html.Th(c, style={"paddingRight": "8px", "borderBottom": "1px solid #ccc"})
        for c in ["Date", "P-start", "P-end", "R-start", "R-end"]
    ])
    return html.Table(
        [html.Thead(header), html.Tbody(rows)],
        style={"borderCollapse": "collapse", "width": "100%"},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="HMP155 QC — Purge Indices Editor (Dash web app)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run on default port 8051, bind to localhost only:
  python qc_app.py

  # Custom port:
  python qc_app.py --port 8052

  # Override data root:
  python qc_app.py --data-root /path/to/level1d --csv-dir /path/to/csvs

SSH local port forwarding (run on your local machine):
  ssh -L 8051:localhost:8051 <username>@<jasmin-login-host>
Then open http://localhost:8051 in your browser.
        """,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8051,
        help="Port to serve on (default: 8051)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1 — localhost only, safe for SSH tunnelling)",
    )
    parser.add_argument(
        "--data-root",
        default=None,
        help="Override the NetCDF level1d root directory (also settable via TRH_DATA_ROOT env var)",
    )
    parser.add_argument(
        "--csv-dir",
        default=None,
        help="Directory containing purge_indices_YYYY.csv files (also settable via PURGE_CSV_DIR env var)",
    )
    args = parser.parse_args()

    if args.data_root:
        TRH_ROOTS[0] = (args.data_root, TRH_ROOTS[0][1])
    if args.csv_dir:
        CSV_DIR = args.csv_dir

    print(f"NetCDF root : {TRH_ROOTS[0][0]}")
    print(f"CSV dir     : {CSV_DIR}")
    print(f"Serving on  : http://{args.host}:{args.port}")
    print()
    print("SSH tunnel (run on your local machine):")
    print(f"  ssh -L {args.port}:localhost:{args.port} <username>@<jasmin-host>")
    print(f"Then open http://localhost:{args.port} in your browser.")

    app.run(debug=False, host=args.host, port=args.port)
