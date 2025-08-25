import pandas as pd
import os

TEAM_MAP = {
    "MC": "Manchester City",
    "NF": "Nottingham Forest",
    "AFC": "Arsenal FC",
    "LF": "Liverpool",
    "MU": "Manchester United",
    "NU": "Newcastle United",
    "IT": "Ipswich Town",
    "TH": "Tottenham Hotspurs",
    "CFC": "Chelsea FC",
    "BR": "Brighton",
    "WV": "Wolves",
    "AVL": "Aston Villa",
}

DATA_FILE = "data/data.xlsx"

def load_data():
    if not os.path.exists(DATA_FILE):
        return None

    xl = pd.ExcelFile(DATA_FILE)

    data = {}
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        df.columns = [c.strip() for c in df.columns]
        # expand team abbreviations
        if "Team" in df.columns:
            df["Team"] = df["Team"].replace(TEAM_MAP)
        if "Opponent" in df.columns:
            df["Opponent"] = df["Opponent"].replace(TEAM_MAP)
        data[sheet] = df

    return data
