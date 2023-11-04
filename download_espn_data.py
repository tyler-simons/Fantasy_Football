import pandas as pd
from espn_data.get_espn_data import get_season_data
from espn_api.football import League
import toml
import pickle

YEAR = 2023
secrets = toml.load(".streamlit/secrets.toml")
league = League(league_id=443750, year=YEAR, espn_s2=secrets["espn_s2"], swid=secrets["swid"])


# all_data = get_season_data(YEAR, league)

# all_data.to_csv(f"./fantasy/fantasy_data_{YEAR}.csv", index=False)

# Download the waiver data
ra = league.recent_activity(2000)
print(len(ra))
filename = f"./wd_{YEAR}.pickle"
with open(filename, "wb") as handle:
    pickle.dump(ra, handle, protocol=pickle.HIGHEST_PROTOCOL)
# logging.info("Waiver data saved")
