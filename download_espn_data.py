import pandas as pd
from espn_data.get_espn_data import get_season_data
from espn_api.football import League
import toml

YEAR = 2022
secrets = toml.load(".streamlit/secrets.toml")
league = League(league_id=443750, year=YEAR, espn_s2=secrets["espn_s2"], swid=secrets["swid"])
all_data = get_season_data(YEAR, league)

all_data.to_csv(f"./fantasy/fantasy_data_{YEAR}.csv", index=False)
