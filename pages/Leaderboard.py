
import streamlit as st
import pandas as pd
from pathlib import Path

st.title("🏆 Leaderboards")

# Resolve data file path
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR/"data"/"latest.xlsx"

def load_leaderboard_tables(path):
    # Read the TABLE sheet, skip blank rows, and split into Group A and Group B
    xl = pd.ExcelFile(path)
    df = xl.parse("TABLE", header=None)
    # Find group headers
    group_a_idx = df[df.apply(lambda row: row.astype(str).str.contains("GROUP A").any(), axis=1)].index[0]
    group_b_idx = df[df.apply(lambda row: row.astype(str).str.contains("GROUP B").any(), axis=1)].index[0]
    # Group A table: from group_a_idx+1 to group_b_idx-1
    group_a = df.iloc[group_a_idx+1:group_b_idx, :9].dropna(how="all")
    group_a.columns = group_a.iloc[0]
    group_a = group_a[1:]
    group_a = group_a.reset_index(drop=True)
    # Group B table: from group_b_idx+1 to end (or next blank)
    group_b = df.iloc[group_b_idx+1:, :9].dropna(how="all")
    group_b.columns = group_b.iloc[0]
    group_b = group_b[1:]
    group_b = group_b.reset_index(drop=True)
    # Convert all columns to native Python types for Streamlit compatibility
    # Try to convert all columns to native Python types, fallback to string if needed
    for df in [group_a, group_b]:
        for col in df.columns:
            try:
                df[col] = df[col].apply(lambda x: x.item() if hasattr(x, 'item') else x)
            except Exception:
                df[col] = df[col].astype(str)
    return group_a, group_b

if not DATA_FILE.exists():
	st.error("No leaderboard data file found. Please upload 'latest.xlsx' from the Admin Panel.")
	st.stop()
 
try:
        group_a, group_b = load_leaderboard_tables(DATA_FILE)
        # Ensure all column names are strings and reset column metadata
        group_a.columns = [str(c) for c in group_a.columns]
        group_b.columns = [str(c) for c in group_b.columns]
        group_a = group_a.copy()
        group_b = group_b.copy()
        st.subheader("Group A")
        st.dataframe(group_a, use_container_width=True, hide_index=True)
        st.subheader("Group B")
        st.dataframe(group_b, use_container_width=True, hide_index=True)
except Exception as e:
	st.error(f"Failed to load leaderboard tables: {e}")
