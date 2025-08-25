import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="Team Stats", layout="wide", initial_sidebar_state="expanded")

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "data" / "latest.xlsx"

@st.cache_data(show_spinner=False)
def load_team_sheets(path: str):
    p = Path(path)
    if not p.exists():
        return None
    try:
        sheets = ["xg", "possesion %", "shots", "passes", "tackles", "interceptions"]
        dfs = pd.read_excel(p, sheet_name=None)
        out = {}
        for s in sheets:
            for k, df in dfs.items():
                if k.strip().lower() == s:
                    df2 = df.copy()
                    df2.columns = [str(c).strip().lower() for c in df2.columns]
                    out[s] = df2
        return out
    except Exception as e:
        raise RuntimeError(f"Failed to read Excel: {e}")

def build_team_df(dfs: dict):
    if dfs is None:
        raise ValueError("No sheets passed to build_team_df()")
    base = dfs["xg"].copy()
    base["team"] = base["teams"].astype(str)
    base["matches played"] = pd.to_numeric(base["matches played"], errors="coerce").fillna(0)
    for metric in ["xg", "possesion %", "shots", "passes", "tackles", "interceptions"]:
        if metric in dfs:
            df = dfs[metric]
            total_col = "total" if "total" in df.columns else None
            if total_col:
                base[metric] = pd.to_numeric(df[total_col], errors="coerce").fillna(0)
            else:
                cols = [c for c in df.columns if c.startswith("gw") or c.startswith("fo")]
                base[metric] = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        else:
            base[metric] = 0
    return base[["team", "matches played", "xg", "possesion %", "shots", "passes", "tackles", "interceptions"]]

def radar_chart_for_team(row: pd.Series, teams_df: pd.DataFrame):
    labels = ["Matches Played", "XG", "Possesion %", "Shots", "Passes", "Tackles", "Interceptions"]
    keys = ["matches played", "xg", "possesion %", "shots", "passes", "tackles", "interceptions"]
    vals = []
    for col in keys:
        if col in teams_df.columns:
            series = teams_df[col]
            value = row.get(col, 0)
            percentile = (series < value).mean() * 100 if series.notna().any() else 0
            vals.append(percentile)
        else:
            vals.append(0)
    labels = labels + [labels[0]]
    vals = vals + [vals[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=vals, theta=labels, fill="toself", name=row.get("team", "Team")))
    fig.update_layout(
        template="plotly_dark",
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickvals=[0, 25, 50, 75, 100], ticktext=["0%","25%","50%","75%","100%"])),
        title="Percentile-normalized Crab Chart"
    )
    return fig

st.title("🏟️ Team Stats")

if st.button("🔄 Reload Data", help="Clear cache and reload all data"):
    st.cache_data.clear()
    st.rerun()

dfs = load_team_sheets(str(DATA_FILE))
if dfs is None:
    st.error("No data file found. Please upload 'latest.xlsx' from the Admin Panel into the `data/` folder.")
    st.stop()

try:
    teams_df = build_team_df(dfs)
except Exception as e:
    st.exception(e)
    st.stop()

# Filters
teams = sorted(teams_df["team"].astype(str).fillna("").unique(), key=lambda x: str(x).lower())
team_sel = st.sidebar.selectbox("Team", ["All"] + teams)
search_team = st.sidebar.text_input("Search team")

min_matches = 0
max_matches = 20
# Ensure default_min is always >= min_matches
default_min = min_matches if min_matches > 0 else 0
min_matches_played = st.sidebar.number_input(
    "Minimum Matches Played (>",
    min_value=min_matches,
    max_value=max_matches,
    value=default_min,
    step=1,
    help="Show only teams with more than this number of matches played."
)

df_view = teams_df.copy()
if team_sel and team_sel != "All":
    df_view = df_view[df_view["team"].str.lower() == str(team_sel).lower()]
if search_team:
    df_view = df_view[df_view["team"].str.lower().str.contains(search_team.lower(), na=False)]
df_view = df_view[df_view["matches played"] > min_matches_played]

display_cols = ["team", "matches played", "xg", "possesion %", "shots", "passes", "tackles", "interceptions"]
custom_cols = {
    "team": "Team",
    "matches played": "Matches Played",
    "xg": "xG",
    "possesion %": "Possesion %",
    "shots": "Shots",
    "passes": "Passes",
    "tackles": "Tackles",
    "interceptions": "Interceptions"
}
per_match = st.checkbox("Show per match stats", value=False, help="Display stats per match (except Team, Matches Played)")
df_display = df_view.copy()
if per_match:
    exclude_cols = ["team", "matches played"]
    for col in display_cols:
        if col not in exclude_cols:
            df_display[col] = df_display.apply(lambda row: row[col] / row["matches played"] if row["matches played"] else 0, axis=1)

st.subheader("Team table")
final_df = df_display.copy()
final_df = final_df.rename(columns=custom_cols)
st.dataframe(final_df[list(custom_cols.values())], use_container_width=True)

selected_teams = st.multiselect(
    "Select team(s) for Crab Chart comparison (exact)",
    teams,
    default=[]
)
if selected_teams:
    st.subheader(f"🕸 Crab chart comparison — {', '.join(selected_teams)}")
    print(df_view)
    labels = ["Matches Played", "XG", "Possesion %", "Shots", "Passes", "Tackles", "Interceptions"]
    keys = ["matches played", "xg", "possesion %", "shots", "passes", "tackles", "interceptions"]
    labels_closed = labels + [labels[0]]
    fig = go.Figure()
    for selected in selected_teams:
        sel_row = df_view[df_view["team"].str.lower() == selected.lower()]
        if not sel_row.empty:
            row = sel_row.iloc[0]
            vals = []
            for col in keys:
                if col in teams_df.columns:
                    series = teams_df[col]
                    value = row.get(col, 0)
                    percentile = (series < value).mean() * 100 if series.notna().any() else 0
                    vals.append(percentile)
                else:
                    vals.append(0)
            vals_closed = vals + [vals[0]]
            fig.add_trace(go.Scatterpolar(r=vals_closed, theta=labels_closed, fill="toself", name=row.get("team", "Team")))
    fig.update_layout(
        template="plotly_dark",
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickvals=[0, 25, 50, 75, 100], ticktext=["0%","25%","50%","75%","100%"])),
        title="Percentile-normalized Crab Chart Comparison"
    )
    st.plotly_chart(fig, use_container_width=True)
elif selected_teams == []:
    st.info("Select one or more teams to view crab chart comparison.")