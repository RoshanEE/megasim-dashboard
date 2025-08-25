# pages/1_player_stats.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
from pathlib import Path

st.set_page_config(page_title="Player Stats", layout="wide", initial_sidebar_state="expanded")


# ----------------------------
# Config / Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "data" / "latest.xlsx"

st.caption(f"Looking for data file at: `{DATA_FILE}`")


# ----------------------------
# Helpers: robust, case-insensitive column handling
# ----------------------------
def _find_col(df: pd.DataFrame, candidates):
    """Return the actual column name in df that matches any candidate (case-insensitive substring or exact).
    candidates: list of strings to try (lowercase recommended). Returns None if not found.
    """
    cols_l = {c.lower(): c for c in df.columns}
    for cand in candidates:
        # exact match
        if cand.lower() in cols_l:
            return cols_l[cand.lower()]
    # substring match
    for cand in candidates:
        for low, orig in cols_l.items():
            if cand.lower() in low:
                return orig
    return None

def _normalize_sheetnames(dfs: dict):
    """Return new dict with lowercase keys for sheet names, preserving DataFrames."""
    return {k.strip().lower(): v.copy() for k, v in dfs.items()}

def _lowercase_cols(dfs: dict):
    """Lowercase column names for every sheet (in-place style; returns new dict)."""
    out = {}
    for k, df in dfs.items():
        df2 = df.copy()
        df2.columns = [str(c).strip() for c in df2.columns]  # strip first
        # keep original column names accessible via mapping if needed, but normalize to lower
        df2.columns = [c.lower() for c in df2.columns]
        out[k] = df2
    return out

def _name_key(s):
    """Normalize player name for joining: remove parentheses and lower-case."""
    if pd.isna(s):
        return ""
    # remove parentheses block e.g. "John Doe (CB)" -> "John Doe"
    no_pos = re.sub(r"\s*\(.*?\)\s*$", "", str(s)).strip()
    return no_pos.lower()

def _extract_position(s):
    """Extract position from 'Name (POS)' if present. Return '' if not."""
    if pd.isna(s):
        return ""
    m = re.search(r"\((.*?)\)\s*$", str(s))
    return m.group(1).strip() if m else ""

def _compute_total_series(df: pd.DataFrame, exclude_cols=None):
    """If a 'total' column exists, return it; else sum all numeric columns excluding exclude_cols."""
    exclude_cols = set([c.lower() for c in (exclude_cols or [])])
    # prefer explicit 'total' column
    if "total" in df.columns:
        return pd.to_numeric(df["total"], errors="coerce").fillna(0)
    # else sum numeric columns (ignore non-numeric and exclude list)
    numeric_cols = [c for c in df.columns if c not in exclude_cols and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        # fallback: try any column that looks like gw or fo (e.g., gw1, fo2)
        gw_like = [c for c in df.columns if re.match(r'^(gw|fo|g)\d+', str(c))]
        numeric_cols = [c for c in gw_like if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        # return zeros
        return pd.Series([0] * len(df), index=df.index)
    return df[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)


# ----------------------------
# Load Excel -> dict of DataFrames (columns lowered)
# ----------------------------
@st.cache_data(show_spinner=False)
def load_excel_as_dfs(path: str):
    p = Path(path)
    if not p.exists():
        return None
    try:
        # read all sheets
        dfs_raw = pd.read_excel(p, sheet_name=None)
        # normalize sheet names to lowercase keys
        dfs_norm_keys = _normalize_sheetnames(dfs_raw)
        # lowercase columns in each sheet
        dfs = _lowercase_cols(dfs_norm_keys)
        return dfs
    except Exception as e:
        raise RuntimeError(f"Failed to read Excel: {e}")


# ----------------------------
# Build unified player dataframe
# ----------------------------
def build_player_df(dfs: dict):
    """Takes dict of sheets (with lowercase columns and keys) and returns unified player DataFrame."""
    if dfs is None:
        raise ValueError("No sheets passed to build_player_df()")

    # ratings sheet (base truth) - try common keys
    ratings = None
    for key in ("ratings", "rating"):
        if key in dfs:
            ratings = dfs[key]
            break
    if ratings is None:
        raise ValueError("Ratings sheet not found. Expected sheet named 'Ratings' (case-insensitive).")

    # find essential columns in ratings
    # possible name columns: 'name', 'player', etc.
    name_col = _find_col(ratings, ["name", "player", "player_name"])
    if name_col is None:
        raise ValueError("No name/player column found in Ratings sheet.")
    team_col = _find_col(ratings, ["team", "club", "squad"])
    # rating total column maybe named 'total' or 'rating' or 'overall'
    rating_col = _find_col(ratings, ["total", "rating", "overall"])
    mp_col = _find_col(ratings, ["mp", "matches_played", "matches", "appearances"])

    # prepare base dataframe
    base = ratings.copy()
    # keep original display name as provided in ratings sheet
    base["player"] = base[name_col].apply(_name_key)  # key for joins (lowercase, no pos)
    base["name_orig"] = base["player"]
    base["position"] = base[name_col].apply(_extract_position).astype(str)
    base["team"] = base[team_col].astype(str).fillna("").str.strip() if team_col else ""
    base["team_key"] = base["team"].astype(str).str.lower() if team_col else ""

    # numeric rating & matches
    base["rating"] = pd.to_numeric(base[rating_col], errors="coerce") if rating_col else 0
    base["matches_played"] = pd.to_numeric(base[mp_col], errors="coerce") if mp_col else 0

    # Initialize stat columns with zeros
    stat_cols = {
        "goals": 0,
        "assists": 0,
        "saves": 0,
        "clean_sheet": 0,
        "yellow": 0,
        "red": 0,
        "motm": 0,
        "lotm": 0
    }

    # Helper to merge a stat sheet into base
    def merge_stat(sheet_key, want_total_name, extra_cols=None):
        if sheet_key.lower() not in dfs:
            return pd.Series([0] * len(base), index=base.index)
        df = dfs[sheet_key].copy()

        nm = _find_col(df, ["name", "player", "player_name"])
        if nm is None:
            return pd.Series([0] * len(base), index=base.index)

        df["player_key"] = df[nm].astype(str).apply(_name_key)

        # Try explicit total column first
        total_col = _find_col(df, [want_total_name, "total", "count", "number"])
        if total_col:
            total = pd.to_numeric(df[total_col], errors="coerce").fillna(0)
        else:
            # Fallback: compute from all numeric cols except name
            total = _compute_total_series(df, exclude_cols=[nm])
        mapping = pd.Series(total.values, index=df["player_key"]).to_dict()
        return base["player"].map(mapping).fillna(0)


    # Merge primary totals
    base["goals"] = merge_stat("goals", "goals")
    base["assists"] = merge_stat("assists", "assists")
    base["saves"] = merge_stat("saves", "saves")
    # For clean sheets specifically, try to find an explicit column in 'saves' sheet
    if "saves" in dfs:
        s = dfs["saves"]
        nm = _find_col(s, ["name", "player"])
        cs_col = _find_col(s, ["clean sheet", "clean_sheet", "cs"])
        if nm and cs_col:
            s["player_key"] = s[nm].astype(str).apply(_name_key)
            mapping_cs = pd.Series(pd.to_numeric(s[cs_col], errors="coerce").fillna(0).values, index=s["player_key"]).to_dict()
            base["clean_sheet"] = base["player"].map(mapping_cs).fillna(0)
        else:
            # fallback: zeros or if 'saves' sheet had a 'clean sheet' as part of compute_total fallback it was ignored above
            base["clean_sheet"] = 0
    else:
        base["clean_sheet"] = 0

    base["yellow"] = merge_stat("yellow", "total")
    base["red"] = merge_stat("red", "total")
    base["motm"] = merge_stat("motm", "total")
    base["lotm"] = merge_stat("lotm", "total")

    # numeric conversions & fillna
    for c in ["rating", "matches_played", "goals", "assists", "saves", "clean_sheet", "yellow", "red", "motm", "lotm"]:
        if c in base.columns:
            base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0)

    # tidy display columns: keep name_orig (original display), team (as present in Ratings), position (as extracted)
    out_cols = ["name_orig", "player", "position", "team", "rating", "matches_played",
                "goals", "assists", "saves", "clean_sheet", "yellow", "red", "motm", "lotm"]
    for c in out_cols:
        if c not in base.columns:
            base[c] = 0
    # rename for nicer display
    base = base.rename(columns={"name_orig": "Name", "team": "Team", "position": "Position",
                                "rating": "Rating", "matches_played": "Matches Played",
                                "clean_sheet": "Clean Sheet", "motm": "MOTM", "lotm": "LOTM"})

    final_cols = [
        "Name", "player", "Position", "Team", "Rating", "Matches Played",
        "goals", "assists", "saves", "Clean Sheet", "yellow", "red", "MOTM", "LOTM"
    ]
    return base[final_cols]



# ----------------------------
# Radar chart function
# ----------------------------
def radar_chart_for_player(row: pd.Series):
    # Use percentiles for normalization
    labels = ["Matches Played", "Rating", "Goals", "Assists", "Saves", "Clean Sheet", "Yellow", "Red"]
    keys = ["Matches Played", "Rating", "goals", "assists", "saves", "Clean Sheet", "Yellow", "Red"]
    # Access the global players DataFrame for percentiles
    global players
    vals = []
    for label in keys:
        col = label
        if col in players.columns:
            series = players[col]
            value = row.get(col, 0)
            # Calculate percentile
            percentile = (series < value).mean() * 100 if series.notna().any() else 0
            vals.append(percentile)
        else:
            vals.append(0)
    # close loop
    labels = labels + [labels[0]]
    vals = vals + [vals[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=vals, theta=labels, fill="toself", name=row.get("Name", "Player")))
    fig.update_layout(
        template="plotly_dark",
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickvals=[0, 25, 50, 75, 100], ticktext=["0%","25%","50%","75%","100%"])),
        title="Percentile-normalized Crab Chart"
    )
    return fig


# ----------------------------
# Main App UI
# ----------------------------
st.title("⚽ Player Stats")

# reload button that clears st.cache_data

# Single column for reload button, shorter text
if st.button("🔄 Reload Data", help="Clear cache and reload all data"):
    st.cache_data.clear()
    st.experimental_rerun()

dfs = load_excel_as_dfs(str(DATA_FILE))
if dfs is None:
    st.error("No data file found. Please upload 'latest.xlsx' from the Admin Panel into the `data/` folder.")
    st.stop()

# Build players df (cached behavior relies on load_excel caching; build quickly)
try:
    players = build_player_df(dfs)
except Exception as e:
    st.exception(e)
    st.stop()

# Filters (case-insensitive)
teams = sorted(players["Team"].astype(str).fillna("").unique(), key=lambda x: str(x).lower())
positions = sorted(players["Position"].astype(str).fillna("").unique(), key=lambda x: str(x).lower())
names = sorted(players["Name"].astype(str).fillna("").unique(), key=lambda x: str(x).lower())

st.sidebar.header("Filters (case-insensitive)")

team_sel = st.sidebar.selectbox("Team", ["All"] + teams)
pos_sel = st.sidebar.selectbox("Position", ["All"] + positions)
search_name = st.sidebar.text_input("Search player (partial, case-insensitive)")

# Matches Played filter (minimum)
min_matches = int(players["Matches Played"].min())
max_matches = int(players["Matches Played"].max())
default_min = min(0, max_matches) if max_matches >= 0 else min_matches
min_matches_played = st.sidebar.number_input(
    "Minimum Matches Played (>",
    min_value=min_matches,
    max_value=max_matches,
    value=default_min,
    step=1,
    help="Show only players with more than this number of matches played."
)

df_view = players.copy()

if team_sel and team_sel != "All":
    df_view = df_view[df_view["Team"].str.lower() == str(team_sel).lower()]

if pos_sel and pos_sel != "All":
    df_view = df_view[df_view["Position"].str.lower() == str(pos_sel).lower()]

if search_name:

    df_view = df_view[df_view["Name"].str.lower().str.contains(search_name.lower(), na=False)]

# Apply matches played filter (strictly greater than)
df_view = df_view[df_view["Matches Played"] > min_matches_played]

# Columns to display (present and friendly)
display_cols = ["Name", "Team", "Position", "Matches Played", "Rating", "goals", "assists", "saves", "Clean Sheet", "yellow", "red", "MOTM", "LOTM"]
# show dataframe

# Per Match toggle
per_match = st.checkbox("Show per match stats", value=False, help="Display stats per match (except Name, Team, Position, Matches Played)")

df_display = df_view.copy()
if per_match:
    # Columns to convert to per match (exclude these)
    exclude_cols = ["Name", "Team", "Position", "Matches Played", "MOTM", "LOTM", "Rating"]
    for col in display_cols:
        if col not in exclude_cols:
            # Avoid division by zero
            df_display[col] = df_display.apply(lambda row: row[col] / row["Matches Played"] if row["Matches Played"] else 0, axis=1)

st.subheader("Player table")
st.dataframe(df_display[display_cols].fillna(0).sort_values(by="Rating", ascending=False), use_container_width=True)

# Select single player to show crab chart
selected = st.selectbox("Select player for Crab Chart (exact)", ["None"] + names)
if selected and selected != "None":
    sel_row = df_view[df_view["Name"].str.lower() == selected.lower()]
    if not sel_row.empty:
        st.subheader(f"🕸 Crab chart — {selected}")
        st.plotly_chart(radar_chart_for_player(sel_row.iloc[0]), use_container_width=True)
    else:
        st.info("Selected player not found in current filtered view.")
